FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY ingest /app/ingest

RUN mkdir -p /opt/chirpstack-ingest/uploads /opt/chirpstack-ingest/data && chmod 750 /opt/chirpstack-ingest /opt/chirpstack-ingest/uploads /opt/chirpstack-ingest/data

EXPOSE 8000

CMD ["uvicorn", "ingest.ingestion_api:app", "--host", "0.0.0.0", "--port", "8000"]
