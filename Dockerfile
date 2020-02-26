FROM python:3.8-slim

RUN apt-get update && apt-get install -y git && rm -rf /var/cache/apt/*
COPY requirements.txt ./
RUN pip3 install -r requirements.txt

COPY chart-updater.py /app/
COPY chart_updater /app/chart_updater/
WORKDIR /app

ENTRYPOINT ["python3", "chart-updater.py"]
