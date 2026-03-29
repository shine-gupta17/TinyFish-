#!/bin/bash

# ChatVerse API Stop Script

echo "🛑 Stopping ChatVerse API..."

# Find and kill the process running on PORT (default 8000)
PORT=${PORT:-8000}

PID=$(lsof -ti:$PORT)

if [ -z "$PID" ]; then
    echo "ℹ️  No process found running on port $PORT"
    exit 0
fi

echo "🔍 Found process $PID running on port $PORT"
kill -15 $PID

# Wait for graceful shutdown
sleep 2

# Check if process still exists
if ps -p $PID > /dev/null; then
    echo "⚠️  Process still running, forcing shutdown..."
    kill -9 $PID
fi

echo "✅ ChatVerse API stopped successfully"
