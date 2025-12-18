# Refined to better fit the NR5103 model and updated dependencies

Credit to atorma and pkorpinen for the original work:

# Zyxel NR5103 InfluxDB collector

Periodically gets the status of your NR5103 modem, pings a host of your choosing,
and stores the results in InfluxDB. Includes sample Grafana dashboards.

## Requirements

* Python 3.8+ or Docker
* InfluxDB version 1.8+ or 2.0+. See [InfluxDB 1.8 API compatibility](https://github.com/influxdata/influxdb-client-python#influxdb-18-api-compatibility).

## Installation

Specific tag, e.g. v2.2.3:

```sh
pip install git+https://github.com/lusciouslukey/nr5103-influxdb-collector.git@v2.2.3
```

Master version:

```sh
pip install git+https://github.com/lusciouslukey/nr5103-influxdb-collector.git
```

## Usage

**Note!** Use the https protocol in NR5103 URL. Authentication does not work when using http.

Using configuration file:

```sh
nr5103-collector --config-file=/path/to/config.ini
```

config.ini

```
[influx2]
url=http://localhost:8086
org=my-org
token=my-token

[tags]
my_tag=my_default_value
other_tag=other_tag_default_value

[nr5103]
url=https://192.168.1.1
username=admin
password=my-password

[collector]
bucket=nr5103
measurement=status
interval=5000
influxdb_max_retries=5
influxdb_max_retry_time=180000
influxdb_max_retry_delay=125000
influxdb_exponential_base=2
ping_host=google.com
ping_timeout=1
```

Using environment properties (see [https://pypi.org/project/influxdb-client](https://pypi.org/project/influxdb-client)
for InfluxDB client environment properties):

```sh
INFLUXDB_V2_URL=http://localhost:8086 \
 INFLUXDB_V2_ORG=my-org \
 INFLUXDB_V2_TOKEN=my-token \
 NR5103_URL=https://192.168.1.1 \
 NR5103_USERNAME=admin \
 NR5103_PASSWORD=my-password \
 COLLECTOR_BUCKET=nr5103 \
 COLLECTOR_MEASUREMENT=status \
 COLLECTOR_PING_HOST=google.com \
 nr5103-collector
```

Using both environment properties and config file (the former take precedence):

```sh
INFLUXDB_V2_TOKEN=my-token NR5103_PASSWORD=my-password nr5103-collector --config-file=/path/to/config.ini
```

## Using Docker

```sh
docker build -t nr5103-collector .
docker run -v /path/to/config.ini:/config.ini:ro nr5103-collector --config-file=/config.ini
```

With the `ping_host` option you may have to use the `--network host` Docker run option.

## Configuration

### [influx2]

See [https://github.com/influxdata/influxdb-client-python](https://github.com/influxdata/influxdb-client-python).
For InfluxDB 1.8+ see [API compatibility](https://github.com/influxdata/influxdb-client-python#influxdb-18-api-compatibility).

### [tags]

Optional [default tags](https://github.com/influxdata/influxdb-client-python#default-tags) to add to all data points. Can also be given as environment properties.

### [nr5103]

* `url` / `NR5103_URL` - The https URL of the NR5103 web interface. Required.
* `username` / `NR5103_USERNAME`: The username of the NR5103 user. Required.
* `password` / `NR5103_PASSWORD`: The password of the NR5103 user. Required.

### [collector]

* `bucket` / `COLLECTOR_BUCKET`: InfluxDB bucket name to store data in. Required.
  * See also [InfluxDB 1.8 API compatibility](https://github.com/influxdata/influxdb-client-python#influxdb-18-api-compatibility).
* `measurement` / `COLLECTOR_MEASUREMENT`: InfluxDB measurement name. Required.
* `interval` / `COLLECTOR_INTERVAL`: Interval, in milliseconds, of data collection. Default is `5000`.
* `influxdb_max_retries` / `COLLECTOR_INFLUXDB_MAX_RETRIES`: See [https://github.com/influxdata/influxdb-client-python#batching](https://github.com/influxdata/influxdb-client-python#batching)
* `influxdb_max_retry_time` / `COLLECTOR_INFLUXDB_MAX_RETRY_TIME`: See [https://github.com/influxdata/influxdb-client-python#batching](https://github.com/influxdata/influxdb-client-python#batching)  
* `influxdb_max_retry_delay` / `COLLECTOR_INFLUXDB_MAX_RETRY_DELAY`: See [https://github.com/influxdata/influxdb-client-python#batching](https://github.com/influxdata/influxdb-client-python#batching)
* `influxdb_exponential_base` / `COLLECTOR_INFLUXDB_EXPONENTIAL_BASE`: See [https://github.com/influxdata/influxdb-client-python#batching](https://github.com/influxdata/influxdb-client-python#batching)
* `ping_host` / `COLLECTOR_PING_HOST`: Optional hostname for ping measurements. Default is `None` meaning ping is not measured.
* `ping_timeout` / `COLLECTOR_PING_TIMEOUT`: Ping timeout in seconds. Default is `1`.
