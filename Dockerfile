# Use Python 3.11 slim image for smaller size
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better Docker layer caching
COPY requirements_1.txt .
COPY requirements_2.txt .

# Install base Python dependencies
RUN pip install --no-cache-dir -r requirements_1.txt
RUN pip install --no-cache-dir -r requirements_2.txt

# Download and install spaCy large model directly
RUN curl -LO https://github.com/explosion/spacy-models/releases/download/en_core_web_lg-3.8.0/en_core_web_lg-3.8.0-py3-none-any.whl && \
    pip install --no-cache-dir en_core_web_lg-3.8.0-py3-none-any.whl && \
    rm en_core_web_lg-3.8.0-py3-none-any.whl

# Download and install spaCy small model
RUN curl -LO https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.8.0/en_core_web_sm-3.8.0-py3-none-any.whl && \
    pip install --no-cache-dir en_core_web_sm-3.8.0-py3-none-any.whl && \
    rm en_core_web_sm-3.8.0-py3-none-any.whl

# Copy application code and environment variables
COPY improved_etl.py .
COPY .env* ./

# Create necessary directories
RUN mkdir -p /app/data /app/output /app/logs

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash etl_user && \
    chown -R etl_user:etl_user /app
USER etl_user

# Entrypoint and default behavior
ENTRYPOINT ["python", "improved_etl.py"]
CMD ["--help"]
