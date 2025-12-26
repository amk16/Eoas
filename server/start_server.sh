#!/bin/bash
set -e

# Log startup information
echo "=== Server Startup ==="
echo "Current directory: $(pwd)"
echo "PORT environment variable: ${PORT:-8080}"
echo "starting server on $PORT..."
echo "Python version: $(python --version)"
echo "Working directory contents:"
ls -la
echo ""
echo "src directory contents:"
ls -la src/ || echo "ERROR: src directory not found"
echo ""

# Set PYTHONPATH to ensure imports work
export PYTHONPATH=/app:$PYTHONPATH
echo "PYTHONPATH: $PYTHONPATH"
echo ""



# Start uvicorn
PORT=${PORT:-8080}
echo "Starting uvicorn on port $PORT..."
exec python -m uvicorn src.main:app --host 0.0.0.0 --port "$PORT" --log-level info --proxy-headers --forwarded-allow-ips="*" 
