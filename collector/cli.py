import argparse
import logging
import atexit
from .config import Config
from nr5103.nr5103 import NR5103
from influxdb_client import InfluxDBClient
from .collector import Collector
from .version import __version__


def cli():
    logging.basicConfig(level=logging.INFO, force=True)

    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description=f'NR5103 InfluxDB collector v{__version__}')
    parser.add_argument('--config-file', default=None)
    args = parser.parse_args()

    config = Config(args.config_file)
    nr5103_client = NR5103(**config.nr5103)
    influxdb_client = InfluxDBClient(**config.influxdb)
    collector = Collector(nr5103_client, influxdb_client, config.collector)

    atexit.register(on_exit, collector, influxdb_client, logger)

    collector.run()


def on_exit(collector, influxdb_client, logger):
    collector.on_exit()
    influxdb_client.close()
    logger.info('CLI exited')


if __name__ == '__main__':
    cli()
