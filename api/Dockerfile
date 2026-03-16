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
COPY .env ./

# Set Python path so Flask can resolve 'routes.*' imports
ENV PYTHONPATH=/app/api

# Expose Flask port
EXPOSE 5001

# Run Flask API
CMD ["python", "api/app.py"]
