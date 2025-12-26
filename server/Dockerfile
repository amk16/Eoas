# Use Python 3.13 slim image
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies
# ffmpeg is required for pydub audio processing
# bash is needed for the startup script
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    bash \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    pip show google-genai && \
    python3 -c "from google import genai; print('google-genai import successful')"

# Copy server source code
COPY src/ ./src/

# Create necessary directories
RUN mkdir -p data uploads/character_images temp

# Copy startup script
COPY start_server.sh ./
RUN chmod +x start_server.sh

# Set default port (Cloud Run will override with PORT env var)
ENV PORT=8080

# Expose port (Cloud Run sets PORT env var)
EXPOSE 8080

# Use startup script for better error handling
CMD ["./start_server.sh"]

