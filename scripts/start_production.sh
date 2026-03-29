#!/bin/bash
# Production startup script for ChatVerse API

set -e  # Exit on error

echo "================================================"
echo "Starting ChatVerse API in Production Mode"
echo "================================================"

# Check Python version
python_version=$(python3 --version)
echo "Python version: $python_version"

# Activate virtual environment if it exists
if [ -d "venv" ]; then
    echo "Activating virtual environment..."
    source venv/bin/activate
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "ERROR: .env file not found!"
    echo "Please create .env file with required environment variables"
    exit 1
fi

# Load environment variables
export $(cat .env | grep -v '^#' | xargs)

# Validate required environment variables
required_vars=("SUPABASE_URL" "SUPABASE_KEY" "BACKEND_URL" "FRONTEND_PLATFORM_URL")
for var in "${required_vars[@]}"; do
    if [ -z "${!var}" ]; then
        echo "ERROR: Required environment variable $var is not set"
        exit 1
    fi
done

echo "Environment variables validated ✓"

# Set production environment
export ENVIRONMENT=production
export DEBUG=False

# Number of workers (default: CPU cores * 2 + 1)
WORKERS=${WORKERS:-4}
HOST=${HOST:-0.0.0.0}
PORT=${PORT:-8000}

echo "Starting server with $WORKERS workers on $HOST:$PORT"

# Start the application with Uvicorn
exec uvicorn app_production:app \
    --host $HOST \
    --port $PORT \
    --workers $WORKERS \
    --log-level info \
    --access-log \
    --no-use-colors \
    --proxy-headers \
    --forwarded-allow-ips='*' \
    --timeout-keep-alive 75
