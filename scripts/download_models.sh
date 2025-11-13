#!/bin/bash
# NeuroscribeAI - Model Download Script
# Downloads all required NER models for the application

set -e  # Exit on error

echo "============================================================"
echo "NeuroscribeAI - Model Download Script"
echo "============================================================"

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if Python is available
if command -v python3 &> /dev/null; then
    PYTHON=python3
elif command -v python &> /dev/null; then
    PYTHON=python
else
    echo -e "${RED}✗ Python not found. Please install Python 3.8+${NC}"
    exit 1
fi

echo "Using Python: $PYTHON"
$PYTHON --version

# Check if running in virtual environment
if [ -z "$VIRTUAL_ENV" ]; then
    echo -e "${YELLOW}⚠ Warning: Not running in a virtual environment${NC}"
    echo "Consider creating one with: python3 -m venv venv && source venv/bin/activate"
    read -p "Continue anyway? (y/n) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Check if required packages are installed
echo ""
echo "Checking required packages..."

packages_missing=0

if ! $PYTHON -c "import spacy" 2>/dev/null; then
    echo -e "${RED}✗ spacy not installed${NC}"
    packages_missing=1
else
    echo -e "${GREEN}✓ spacy installed${NC}"
fi

if ! $PYTHON -c "import scispacy" 2>/dev/null; then
    echo -e "${RED}✗ scispacy not installed${NC}"
    packages_missing=1
else
    echo -e "${GREEN}✓ scispacy installed${NC}"
fi

if ! $PYTHON -c "import transformers" 2>/dev/null; then
    echo -e "${RED}✗ transformers not installed${NC}"
    packages_missing=1
else
    echo -e "${GREEN}✓ transformers installed${NC}"
fi

if [ $packages_missing -eq 1 ]; then
    echo ""
    echo -e "${YELLOW}Some packages are missing. Installing from requirements.txt...${NC}"
    $PYTHON -m pip install -r requirements.txt
fi

# Run the Python download script
echo ""
echo "============================================================"
echo "Starting Model Downloads"
echo "============================================================"

$PYTHON "$(dirname "$0")/download_models.py"

exit_code=$?

if [ $exit_code -eq 0 ]; then
    echo ""
    echo -e "${GREEN}============================================================${NC}"
    echo -e "${GREEN}✓ All models downloaded and verified successfully!${NC}"
    echo -e "${GREEN}============================================================${NC}"
else
    echo ""
    echo -e "${RED}============================================================${NC}"
    echo -e "${RED}✗ Model download failed. Check the logs above.${NC}"
    echo -e "${RED}============================================================${NC}"
fi

exit $exit_code
