#!/bin/bash
# Installation script for Calibre Books CLI

set -e  # Exit on any error

echo "Installing Calibre Books CLI..."

# Check Python version
python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
echo "Python version: $python_version"

if [[ $(echo "$python_version < 3.9" | bc -l) -eq 1 ]]; then
    echo "Error: Python 3.9+ is required. Found Python $python_version"
    echo "Please install Python 3.9+ and try again."
    exit 1
fi

# Check if pip is available
if ! command -v pip3 &> /dev/null; then
    echo "Error: pip3 is not available. Please install pip and try again."
    exit 1
fi

# Install from PyPI (when available) or local directory
if [ -f "pyproject.toml" ]; then
    echo "Installing from local directory..."
    pip3 install .
else
    echo "Installing from PyPI..."
    pip3 install calibre-books
fi

# Create configuration directory
mkdir -p ~/.calibre-books/logs
mkdir -p ~/.calibre-books/cache

# Verify installation
echo "Verifying installation..."
calibre-books --version

echo ""
echo "✅ Calibre Books CLI installed successfully!"
echo ""
echo "Get started with:"
echo "  calibre-books config init --interactive"
echo ""
echo "For help:"
echo "  calibre-books --help"
