# syntax=docker/dockerfile:1
FROM python:3.11-slim

# Set environment flags
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# Install system dependencies including curl for container health check
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create dedicated non-root user
RUN useradd -m -u 1000 -s /bin/bash appuser

WORKDIR /app

# Copy dependencies first for efficient Docker layer caching
COPY requirements.txt ./
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy application files and grant ownership to non-root user
COPY . .
RUN chown -R appuser:appuser /app

# Switch to non-root user
USER appuser

EXPOSE 8501

# Streamlit healthcheck endpoint
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl --fail http://localhost:8501/_stcore/health || exit 1

# Launch Streamlit server
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true"]
