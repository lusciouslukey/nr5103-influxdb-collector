from setuptools import setup, find_packages
from collector.version import __version__

setup(
    name='nr5103-influxdb-collector',
    version=__version__,
    description='Zyxel NR5103 InfluxDB Collector',
    author='Anssi Törmä',
    license='MIT',
    url='https://github.com/lusciouslukey/nr5103-influxdb-collector',
    packages=find_packages(),
    install_requires=[
        'ping3==2.9.1',
        'influxdb-client==1.19.0',
        'rx==3.2.0',
        'urllib3<2'
    ],
    entry_points={
        'console_scripts': ['nr5103-collector=collector.cli:cli'],
    },
)
