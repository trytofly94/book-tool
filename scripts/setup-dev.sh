#!/bin/bash
# Development environment setup script for Calibre Books CLI

set -e  # Exit on any error

echo "Setting up Calibre Books CLI development environment..."

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "Error: pyproject.toml not found. Please run this script from the project root."
    exit 1
fi

# Check Python version
python_version=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Python version: $python_version"

if [[ $(echo "$python_version < 3.9" | bc -l) -eq 1 ]]; then
    echo "Error: Python 3.9+ is required. Found Python $python_version"
    exit 1
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Upgrade pip and install build tools
echo "Upgrading pip and installing build tools..."
pip install --upgrade pip setuptools wheel

# Install development dependencies
echo "Installing development dependencies..."
pip install -r requirements-dev.txt

# Install package in development mode
echo "Installing calibre-books in development mode..."
pip install -e .

# Set up pre-commit hooks
echo "Setting up pre-commit hooks..."
pre-commit install

# Create necessary directories
echo "Creating directories..."
mkdir -p ~/.calibre-books/logs
mkdir -p ~/.calibre-books/cache

# Verify installation
echo "Verifying installation..."
calibre-books --version

echo ""
echo "✅ Development environment setup complete!"
echo ""
echo "To activate the environment:"
echo "  source venv/bin/activate"
echo ""
echo "To run tests:"
echo "  pytest"
echo ""
echo "To run the CLI:"
echo "  calibre-books --help"
echo ""
echo "To format code:"
echo "  black src/ tests/"
echo "  isort src/ tests/"
