#!/bin/bash
# Script to build and serve the documentation

# Install uv if not already installed
if ! command -v uv &> /dev/null; then
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# Create and activate virtual environment if it doesn't exist
if [ ! -d ".venv" ]; then
    uv venv
fi

# Activate virtual environment
source .venv/bin/activate

# Install dependencies using uv
uv pip install -e ".[docs]"

# Build the documentation
echo "Building documentation..."
python3 -m mkdocs build

# Serve the documentation (optional)
echo "To serve the documentation locally, run:"
echo "python3 -m mkdocs serve --dev-addr=127.0.0.1:8000"
