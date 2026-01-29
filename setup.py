from setuptools import setup, find_packages
from collector.version import __version__

setup(
    name='nr5103-influxdb-collector',
    version=__version__,
    description='Zyxel NR5103 InfluxDB Collector',
    author='Luke Bennett',
    license='MIT',
    url='https://github.com/lusciouslukey/nr5103-influxdb-collector',
    packages=find_packages(),
    install_requires=[
        'ping3==5.1.5',
        'influxdb-client==1.50.0',
        'rx==3.2.0',
        'urllib3==2.6.3',
        'requests==2.32.5'
    ],
    entry_points={
        'console_scripts': ['nr5103-collector=collector.cli:cli'],
    },
)
