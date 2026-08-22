FROM python:3.13-slim

LABEL maintainer="hcmsyoda"
LABEL description="EVGA SuperNOVA 850 PSU Monitor - System power, temp & fan monitoring"

RUN apt-get update && apt-get install -y --no-install-recommends \
    lm-sensors \
    ipmitool \
    dmidecode \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY templates/ templates/
COPY static/ static/

EXPOSE 8088

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD curl -f http://localhost:8088/api/health || exit 1

CMD ["python", "app.py"]
