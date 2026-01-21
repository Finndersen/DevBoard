#!/bin/bash

# Start DevBoard frontend and backend
# Usage: ./start.sh [BACKEND_PORT]
# Example: ./start.sh 8001

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_PORT="${1:-8000}"
FRONTEND_PID=""

cleanup() {
    echo ""
    echo "Shutting down..."
    # Kill frontend and all its child processes (e.g., Vite dev server)
    if [[ -n "$FRONTEND_PID" ]]; then
        pkill -P "$FRONTEND_PID" 2>/dev/null || true
        kill "$FRONTEND_PID" 2>/dev/null || true
    fi
    exit 0
}

trap cleanup SIGINT SIGTERM

# Start frontend in background
echo "Starting frontend (pnpm dev)..."
cd "$SCRIPT_DIR/frontend"
pnpm dev &
FRONTEND_PID=$!

# Start backend in foreground (shows console output)
echo "Starting backend on port $BACKEND_PORT..."
cd "$SCRIPT_DIR/backend"
BACKEND_PORT="$BACKEND_PORT" make start