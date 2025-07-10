FROM python:3.11-slim

# Install system dependencies including Cairo and OpenCV requirements
RUN apt-get update && apt-get install -y \
    libcairo2-dev \
    libpango1.0-dev \
    libgdk-pixbuf2.0-dev \
    libffi-dev \
    pkg-config \
    python3-dev \
    build-essential \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    tesseract-ocr \
    tesseract-ocr-eng \
    libgfortran5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create directory for React build and set a fallback message
RUN mkdir -p /app/react/dist && \
    echo '<!DOCTYPE html><html><head><title>Backend API</title></head><body><h1>Jaaz AI Backend API</h1><p>Frontend not available</p><a href="/docs">API Documentation</a></body></html>' > /app/react/dist/index.html

# Expose port for Render (default 10000)
EXPOSE 10000

# Create startup script to handle dynamic PORT
RUN echo '#!/bin/bash\nuvicorn main:socket_app --host 0.0.0.0 --port ${PORT:-10000}' > /app/start.sh && chmod +x /app/start.sh

# Start the application with uvicorn for production
CMD ["/app/start.sh"]