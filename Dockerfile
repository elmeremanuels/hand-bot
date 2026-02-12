# Dockerfile for Polymarket Trading Bot
# TODO: Complete when ready for production deployment

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY src/ ./src/
COPY logs/ ./logs/

# Create logs directory
RUN mkdir -p logs

# Run the bot
CMD ["python", "-m", "src.main"]
