#!/bin/bash
# ChatVerse Backend - Production Startup Script for VPS
# This script starts the FastAPI application with optimized settings

set -e  # Exit on error

echo "🚀 ChatVerse Backend - Starting Production Server"
echo "=================================================="

# Load environment variables
if [ -f .env ]; then
    echo "✅ Loading environment variables from .env"
    export $(cat .env | grep -v '^#' | xargs)
else
    echo "⚠️  Warning: .env file not found, using system environment variables"
fi

# Set defaults if not provided
export HOST=${HOST:-0.0.0.0}
export PORT=${PORT:-8000}
export WORKERS=${WORKERS:-4}
export DEBUG=${DEBUG:-false}

echo "📋 Configuration:"
echo "   Host: $HOST"
echo "   Port: $PORT"
echo "   Workers: $WORKERS"
echo "   Debug: $DEBUG"
echo ""

# Check Python version
echo "🐍 Checking Python version..."
python3 --version

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install/upgrade dependencies
echo "📦 Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Run database migrations if needed
# echo "🗄️  Running database migrations..."
# python scripts/migrate.py

# Health check before starting
echo "🏥 Running health check..."
python3 -c "
import sys
try:
    from supabase_client_async import async_supabase
    print('✅ All imports successful')
except Exception as e:
    print(f'❌ Import error: {e}')
    sys.exit(1)
"

echo ""
echo "🌟 Starting Uvicorn server..."
echo "=================================================="

# Start the server with production settings
if [ "$DEBUG" = "true" ]; then
    echo "🐛 Running in DEBUG mode with auto-reload"
    uvicorn app:app \
        --host "$HOST" \
        --port "$PORT" \
        --reload \
        --log-level info \
        --access-log
else
    echo "🚀 Running in PRODUCTION mode"
    uvicorn app:app \
        --host "$HOST" \
        --port "$PORT" \
        --workers "$WORKERS" \
        --log-level info \
        --access-log \
        --no-access-log \
        --limit-concurrency 1000 \
        --limit-max-requests 10000 \
        --timeout-keep-alive 5
fi
