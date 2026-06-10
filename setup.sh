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

install_node() {
    if command -v brew &> /dev/null; then
        info "Installing node via Homebrew..."
        brew install node
    else
        error "node is not installed and Homebrew is not available. Please install node manually."
    fi
}

install_pnpm() {
    info "Installing pnpm via npm..."
    npm install -g pnpm
}

install_uv() {
    if command -v brew &> /dev/null; then
        info "Installing uv via Homebrew..."
        brew install uv
    else
        info "Installing uv via installer script..."
        curl -LsSf https://astral.sh/uv/install.sh | sh
        export PATH="$HOME/.local/bin:$PATH"
    fi
}

# Check prerequisites
info "Checking prerequisites..."

if ! command -v node &> /dev/null; then
    warn "node not found, attempting to install..."
    install_node
fi

if ! command -v pnpm &> /dev/null; then
    warn "pnpm not found, attempting to install..."
    install_pnpm
fi

if ! command -v uv &> /dev/null; then
    warn "uv not found, attempting to install..."
    install_uv
fi
brew install tree

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
