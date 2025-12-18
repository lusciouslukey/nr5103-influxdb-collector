# Clean, RAT-aware NR5103 collector (v3)
# --------------------------------
# Goals:
# - One observation per radio context (LTE anchor / NR secondary)
# - No missing-field explosions
# - Avoid "unknown" series and placeholder/sentinel swamp
# - Preserve modem CA context as *fields* (not tags)
# - Stable tags, boring queries, happy dashboards

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional

import rx
from rx import operators as ops
from influxdb_client import Point, WriteOptions
from ping3 import ping

from nr5103.nr5103 import NR5103
from .config import CollectorConfig

logger = logging.getLogger(__name__)

# ----------------------------
# Helpers
# ----------------------------


def split_csv(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [x.strip() for x in value.split(",") if x.strip()]


def safe_float(value) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def safe_int(value) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def valid_pci(value) -> bool:
    v = safe_int(value)
    return v is not None and v > 0


def valid_rsrp(v: Optional[float]) -> bool:
    # Modems often use -140 as "no signal". We treat the floor as invalid.
    return v is not None and -140.0 < v < -40.0


def valid_rsrq(v: Optional[float]) -> bool:
    return v is not None and -30.0 < v < 0.0


def valid_sinr(v: Optional[float]) -> bool:
    # Conservative, avoids obvious placeholders.
    return v is not None and -20.0 < v < 50.0


def parse_band_rfcn_pairs(
    bands_csv: Optional[str], rfcns_csv: Optional[str]
) -> List[Dict[str, str]]:
    bands = split_csv(bands_csv)
    rfcns = split_csv(rfcns_csv)
    pairs: List[Dict[str, str]] = []
    for i, b in enumerate(bands):
        rfcn = rfcns[i] if i < len(rfcns) else ""
        pairs.append({"band": b, "rfcn": rfcn})
    return pairs


# LTE supplemental downlink-only (SDL) bands — not a sensible LTE anchor.
LTE_SDL_ONLY = {"B32", "B29"}


def choose_lte_anchor(pairs: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    # The NR5103 gives a mixed list like: B20,B32,n1 (index-aligned with RFCN list)
    lte = [p for p in pairs if p.get("band", "").startswith("B")]
    if not lte:
        return None
    non_sdl = [p for p in lte if p.get("band") not in LTE_SDL_ONLY]
    # Prefer the first non-SDL LTE band in modem order (usually PCC/anchor in practice).
    return non_sdl[0] if non_sdl else lte[0]


# ----------------------------
# Collector
# ----------------------------


class Collector:
    def __init__(self, nr5103_client: NR5103, influxdb_client, config: CollectorConfig):
        self.nr5103_client = nr5103_client
        self.config = config
        self.write_api = influxdb_client.write_api(
            write_options=WriteOptions(
                batch_size=1,
                retry_interval=config["interval"],
                max_retry_time=config["influxdb_max_retry_time"],
                max_retries=config["influxdb_max_retries"],
                max_retry_delay=config["influxdb_max_retry_delay"],
                exponential_base=config["influxdb_exponential_base"],
            )
        )
        self.session_key = None

    # ------------------------
    # Lifecycle
    # ------------------------

    def run(self):
        self.session_key = self.nr5103_client.login()
        if not self.session_key:
            raise RuntimeError("NR5103 login failed")

        rx.interval(period=timedelta(milliseconds=self.config["interval"])).pipe(
            ops.map(lambda _: self.collect())
        ).run()

    def on_exit(self):
        if self.write_api:
            self.write_api.close()
        if self.session_key:
            self.nr5103_client.logout(self.session_key)

    # ------------------------
    # Core collection
    # ------------------------

    def collect(self):
        status = self._get_status()
        now = datetime.utcnow()

        if not status:
            return

        for p in self._extract_radio_points(status, now):
            self.write_api.write(bucket=self.config["bucket"], record=p)

        ping_point = self._extract_ping_point(now)
        if ping_point:
            self.write_api.write(bucket=self.config["bucket"], record=ping_point)

    # ------------------------
    # Status + Ping
    # ------------------------

    def _get_status(self) -> Optional[dict]:
        try:
            return self.nr5103_client.get_status()
        except Exception as e:
            logger.warning("Failed to fetch NR5103 status", exc_info=e)
            return None

    def _extract_ping_point(self, now: datetime) -> Optional[Point]:
        try:
            latency = ping(
                dest_addr=self.config["ping_host"],
                unit="ms",
                timeout=self.config["ping_timeout"],
            )
        except Exception:
            latency = None

        if latency is None:
            return None

        return (
            Point("network_ping")
            .tag("target", self.config["ping_host"])
            .field("latency_ms", latency)
            .time(now)
        )

    # ------------------------
    # Radio extraction
    # ------------------------

    def _extract_radio_points(self, status: dict, now: datetime) -> List[Point]:
        cell = status.get("cellular", {})
        points: List[Point] = []

        # Parse modem CA/NSA context lists (index-aligned)
        pairs = parse_band_rfcn_pairs(
            cell.get("INTF_Current_Band"), cell.get("INTF_RFCN")
        )
        lte_anchor = choose_lte_anchor(pairs)

        raw_bands = ",".join([p["band"] for p in pairs]) if pairs else None
        raw_rfcns = (
            ",".join([p["rfcn"] for p in pairs if p.get("rfcn")]) if pairs else None
        )

        # ---- LTE / anchor ----
        lte_pci = cell.get("INTF_PhyCell_ID")
        if valid_pci(lte_pci):
            p = self._radio_point(
                rat="LTE",
                role="anchor",
                pci=lte_pci,
                cell_id=cell.get("INTF_Cell_ID"),
                band=lte_anchor["band"] if lte_anchor else None,
                arfcn=(
                    lte_anchor["rfcn"]
                    if lte_anchor and lte_anchor.get("rfcn")
                    else None
                ),
                rsrp=safe_float(cell.get("INTF_RSRP")),
                rsrq=safe_float(cell.get("INTF_RSRQ")),
                sinr=self._clean_sinr(safe_float(cell.get("INTF_SINR"))),
                time=now,
            )
            # Preserve modem context to debug CA/NSA situations later.
            if raw_bands is not None:
                p.field("intf_bands", raw_bands)
            if raw_rfcns is not None:
                p.field("intf_rfcns", raw_rfcns)
            points.append(p)

        # ---- NR (NSA secondary) ----
        # The modem may report placeholder garbage even when keys exist.
        # Gate hard: NSA enabled + valid PCI + band + arfcn + rsrp in sane range.
        if bool(cell.get("NSA_Enable")):
            nr_pci = cell.get("NSA_PhyCellID")
            nr_band = cell.get("NSA_Band")
            nr_arfcn = cell.get("NSA_RFCN")
            nr_rsrp = safe_float(cell.get("NSA_RSRP"))

            if valid_pci(nr_pci) and nr_band and nr_arfcn and valid_rsrp(nr_rsrp):
                points.append(
                    self._radio_point(
                        rat="NR",
                        role="secondary",
                        pci=nr_pci,
                        cell_id=cell.get("NSA_Cell_ID") or cell.get("INTF_Cell_ID"),
                        band=nr_band,
                        arfcn=nr_arfcn,
                        rsrp=nr_rsrp,
                        rsrq=safe_float(cell.get("NSA_RSRQ")),
                        sinr=self._clean_sinr(safe_float(cell.get("NSA_SINR"))),
                        time=now,
                    )
                )

        return points

    def _clean_sinr(self, sinr: Optional[float]) -> Optional[float]:
        # Some firmwares report 0 when SINR is not available.
        if sinr == 0:
            return None
        return sinr

    # ------------------------
    # Point factory
    # ------------------------

    def _radio_point(
        self,
        rat: str,
        role: str,
        pci,
        cell_id,
        band,
        arfcn,
        rsrp,
        rsrq,
        sinr,
        time: datetime,
    ) -> Point:
        # IMPORTANT: Avoid creating zombie series with band/arfcn="unknown".
        # If identity is missing, skip the point at the caller.
        p = (
            Point("cellular_radio_raw")
            .tag("rat", rat)
            .tag("role", role)
            .tag("pci", str(pci) if pci is not None else "unknown")
            .tag("cell_id", str(cell_id) if cell_id is not None else "unknown")
        )

        if band:
            p = p.tag("band", str(band))
        if arfcn:
            p = p.tag("arfcn", str(arfcn))

        # Only write fields when we have a value (prevents _field-based queries from hiding points).
        if rsrp is not None:
            p = p.field("rsrp", rsrp)
        if rsrq is not None:
            p = p.field("rsrq", rsrq)
        if sinr is not None:
            p = p.field("sinr", sinr)

        return p.time(time)
