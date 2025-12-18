#!/usr/bin/env python3
import base64
import json
import logging
from typing import Any, Dict, Optional

import requests
import urllib3

logger = logging.getLogger(__name__)


class NR5103Exception(Exception):
    """Raised when the NR5103 API returns an error response."""

    def __init__(self, error: str):
        super().__init__(error)
        self.error = error


class NR5103:
    """Minimal NR5103 HTTP client used by the collector."""

    def __init__(self, url: str, username: str, password: str, params: Optional[Dict[str, Any]] = None):
        self.url = url
        self.params: Dict[str, Any] = params or {}
        password_b64 = base64.b64encode(password.encode("utf-8")).decode("utf-8")
        self.login_params = {
            "Input_Account": username,
            "Input_Passwd": password_b64,
            "currLang": "en",
            "RememberPassword": 0,
            "SHA512_password": False,
        }

        # NR5103 ships with a self-signed certificate, so skip verification by default.
        self.params.setdefault("verify", False)
        urllib3.disable_warnings()

    def load_cookies(self, cookiefile: str):
        try:
            with open(cookiefile, "rt", encoding="utf-8") as f:
                cookies = json.load(f)
            logger.debug("Cookies loaded")
            self.params["cookies"] = cookies
        except FileNotFoundError:
            logger.debug("Cookie file does not exist, ignoring.")
        except json.JSONDecodeError:
            logger.warning("Ignoring invalid cookie file.")

    def store_cookies(self, cookiefile: str):
        cookies = self.params.get("cookies")
        if not cookies:
            logger.warning("No cookie to write")
            return

        with open(cookiefile, "wt", encoding="utf-8") as f:
            json.dump(cookies, f)
        logger.debug("Cookies saved")

    def login(self) -> Optional[str]:
        login_json = json.dumps(self.login_params)

        with requests.post(f"{self.url}/UserLogin", data=login_json, **self.params) as resp:
            if resp.status_code != 200:
                logger.error("Unauthorized")
                return None

            # Update cookies
            self.params["cookies"] = requests.utils.dict_from_cookiejar(resp.cookies)
            payload = resp.json()
            return payload.get("sessionkey")

    def logout(self, sessionkey: str):
        with requests.get(f"{self.url}/cgi-bin/UserLogout?sessionkey={sessionkey}", **self.params) as resp:
            resp.raise_for_status()

    def connect(self):
        with requests.get(f"{self.url}/getBasicInformation", **self.params) as resp:
            resp.raise_for_status()
            data = resp.json()
            if data.get("result") != "ZCFG_SUCCESS":
                raise NR5103Exception("Connection failure")

        with requests.get(f"{self.url}/UserLoginCheck", **self.params) as resp:
            resp.raise_for_status()

    def get_status(self, retries: int = 1) -> Optional[Dict[str, Any]]:
        def parse_traffic_object(obj: Dict[str, Any]) -> Dict[str, Any]:
            ret: Dict[str, Any] = {}
            for iface, iface_st in zip(obj.get("ipIface", []), obj.get("ipIfaceSt", [])):
                ret[iface.get("X_ZYXEL_IfName")] = iface_st
            return ret

        attempts = retries
        while attempts > 0:
            try:
                cellular = self.get_json_object("cellwan_status")
                traffic = parse_traffic_object(self.get_json_object("Traffic_Status"))
                return {"cellular": cellular, "traffic": traffic}
            except requests.exceptions.HTTPError as exc:
                logger.warning(exc)
                if exc.response is not None and exc.response.status_code == 401:
                    logger.info("Login required, retrying")
                    self.login()
                else:
                    attempts -= 1

        return None

    def get_json_object(self, oid: str) -> Dict[str, Any]:
        with requests.get(f"{self.url}/cgi-bin/DAL?oid={oid}", **self.params) as resp:
            resp.raise_for_status()
            payload = resp.json()
            if payload.get("result") != "ZCFG_SUCCESS":
                raise NR5103Exception(f"Request for {oid} failed")
            objects = payload.get("Object", [])
            if not objects:
                raise NR5103Exception(f"No object data for oid {oid}")
            return objects[0]
