# Football Data Engineering Airflow Image
# Based on Apache Airflow 2.9.0 with Python 3.10
# Includes dependencies for Wikipedia data scraping and processing
FROM apache/airflow:2.9.0-python3.10

LABEL maintainer="Kareem Nagah"
LABEL description="Airflow image for Football Data Engineering project"

USER root

# Install system dependencies
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create directories for data and pipelines
RUN mkdir -p /opt/airflow/data /opt/airflow/pipelines

# Set permissions - ensure airflow user has full access to directories
RUN chown -R airflow:root /opt/airflow && chmod -R 777 /opt/airflow/data

# Switch back to airflow user
USER airflow

# Copy requirements file
COPY --chown=airflow:root requirements.txt /requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r /requirements.txt

# Healthcheck to ensure Airflow is running properly
HEALTHCHECK --interval=30s --timeout=30s --retries=3 \
  CMD airflow jobs check --job-type SchedulerJob --hostname "$${HOSTNAME}"