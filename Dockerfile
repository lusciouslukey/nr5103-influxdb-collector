FROM python:3.9.6-buster

RUN useradd --create-home appuser
USER appuser

RUN mkdir -p /home/appuser/app
WORKDIR /home/appuser/app

RUN pip install requests
COPY collector ./collector
COPY nr5103 ./nr5103
COPY setup.py .
RUN pip install . --no-cache-dir

ENTRYPOINT ["python", "-m", "collector.cli"]
