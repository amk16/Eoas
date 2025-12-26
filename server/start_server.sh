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

# Test if we can import the app
echo "Testing app import..."
python -c "import sys; sys.path.insert(0, '/app'); from src.main import app; print('App imported successfully')" || {
    echo "ERROR: Failed to import app"
    python -c "import sys; print('Python path:', sys.path)"
    exit 1
}

# Start uvicorn
PORT=${PORT:-8080}
echo "Starting uvicorn on port $PORT..."
exec python -m uvicorn src.main:app --host 0.0.0.0 --port "$PORT" --log-level info
