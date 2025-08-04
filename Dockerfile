# Simple Dockerfile for BlueJay Development
FROM python:3.11-slim

WORKDIR /app

# Install only essential system dependency for PostgreSQL connection
RUN apt-get update && apt-get install -y \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY . .

# Expose port
EXPOSE 8000

# Disable Python output buffering for better logging
ENV PYTHONUNBUFFERED=1

# Start server with hot reload for development
CMD ["uvicorn", "src.api.server:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]