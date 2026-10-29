FROM python:3.12-slim AS base
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY opspilot ./opspilot

# Runs as a non-root user -- same baseline hardening discipline as the
# other projects in this portfolio.
RUN useradd --create-home --uid 1000 opspilot \
    && mkdir -p /data && chown opspilot:opspilot /data
USER opspilot

ENV OPSPILOT_DB_PATH=/data/opspilot.db
EXPOSE 8000
CMD ["uvicorn", "opspilot.server:app", "--host", "0.0.0.0", "--port", "8000"]
