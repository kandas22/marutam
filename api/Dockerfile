FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy API source code
COPY api/ ./api/

# NOTE: .env is NOT baked into the image; supply secrets via docker-compose
#       env_file / --env-file / environment variables at runtime.

# Set Python path so Flask can resolve 'routes.*' imports
ENV PYTHONPATH=/app/api

# Run as a non-root user for security
RUN addgroup --system appgroup && adduser --system --ingroup appgroup appuser
USER appuser

# Expose Gunicorn port
EXPOSE 5001

# Production: run with Gunicorn
# - app:create_app() uses the application factory pattern
# - Config is loaded from gunicorn.conf.py
CMD ["gunicorn", "--config", "api/gunicorn.conf.py", "api.app:create_app()"]
