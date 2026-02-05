#!/bin/bash
set -e

# DevBoard Setup Script
# Sets up both backend and frontend development environments

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Parse arguments
SKIP_MIGRATIONS=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-migrations)
            SKIP_MIGRATIONS=true
            shift
            ;;
        *)
            echo "Unknown option: $1"
            echo "Usage: $0 [--skip-migrations]"
            exit 1
            ;;
    esac
done

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

check_command() {
    if ! command -v "$1" &> /dev/null; then
        error "$1 is required but not installed. Please install it first."
    fi
}

# Check prerequisites
info "Checking prerequisites..."

check_command node
check_command pnpm
check_command uv

info "All prerequisites satisfied"

# Backend setup
info "Setting up backend..."
cd "$SCRIPT_DIR/backend"

info "Installing backend dependencies..."
make install

if [ "$SKIP_MIGRATIONS" = false ]; then
    info "Running database migrations..."
    make migrate
else
    warn "Skipping database migrations (--skip-migrations flag set)"
fi

info "Backend setup complete"

# Frontend setup
info "Setting up frontend..."
cd "$SCRIPT_DIR/frontend"

info "Installing frontend dependencies..."
pnpm install

info "Frontend setup complete"

# Summary
echo ""
info "Setup complete!"
echo ""
echo "To start the development servers, run:"
echo ""
echo "  ./start.sh"
