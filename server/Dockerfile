# Use Python 3.13 slim image
FROM python:3.13-slim

# Set working directory
WORKDIR /app

# Install system dependencies
# ffmpeg is required for pydub audio processing
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

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

# Set default port (Cloud Run will override with PORT env var)
ENV PORT=8080

# Expose port (Cloud Run sets PORT env var)
EXPOSE 8080

# Run uvicorn (PORT is set by Cloud Run, defaults to 8080)
# Use python -m uvicorn to ensure proper module resolution
CMD ["sh", "-c", "echo Starting server on port ${PORT:-8080} && python -m uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8080}"]

