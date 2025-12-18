#!/bin/bash

# Start DevBoard frontend and backend

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_PID=""

cleanup() {
    echo ""
    echo "Shutting down..."
    if [[ -n "$FRONTEND_PID" ]]; then
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
echo "Starting backend (make start)..."
cd "$SCRIPT_DIR/backend"
make start