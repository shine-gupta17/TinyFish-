#!/bin/bash
# Development startup script with auto-reload

set -e

echo "================================================"
echo "Starting ChatVerse API in Development Mode"
echo "================================================"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "WARNING: .env file not found. Using defaults."
fi

# Set development environment
export ENVIRONMENT=development
export DEBUG=True
export HOST=${HOST:-127.0.0.1}
export PORT=${PORT:-8000}

echo "Starting development server on $HOST:$PORT with auto-reload..."

# Start with uvicorn in reload mode
exec uvicorn app:app \
    --host $HOST \
    --port $PORT \
    --reload \
    --log-level debug \
    --access-log
