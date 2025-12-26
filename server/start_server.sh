#!/bin/bash
cd "$(dirname "$0")"
echo "Starting backend server on port 3001..."
python3.13 -m uvicorn src.main:app --reload --host 0.0.0.0 --port 3001
