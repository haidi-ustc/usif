#!/bin/bash
# Rapid download script for Materials Project data
# Downloads 1000 structures in 10 groups with diverse properties and crystal systems
# Usage: ./download_mp_rapid.sh

set -e  # Exit on error

# Check for API key
if [ -z "$MAPI_KEY" ]; then
    echo "Error: MAPI_KEY environment variable not set"
    echo "Please set it with: export MAPI_KEY='your_api_key_here'"
    exit 1
fi

# Output directory
OUTPUT_DIR="data/mp_structures"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_SCRIPT="$SCRIPT_DIR/download_mp_data.py"

# Check if Python script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo "Error: Python script not found at $PYTHON_SCRIPT"
    exit 1
fi

echo "=========================================="
echo "Materials Project Rapid Download"
echo "=========================================="
echo "API Key: ${MAPI_KEY:0:10}... (hidden)"
echo "Output: $OUTPUT_DIR"
echo "Total: 1000 structures in 10 groups"
echo "=========================================="
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Download with default settings (high quality, diverse structures)
echo "Starting download..."
python3 "$PYTHON_SCRIPT" \
    --api_key "$MAPI_KEY" \
    --output_dir "$OUTPUT_DIR" \
    --total_entries 1000 \
    --entries_per_group 100 \
    --e_above_hull_max 0.1

echo ""
echo "=========================================="
echo "Download complete!"
echo "=========================================="
echo "Structures saved to: $OUTPUT_DIR"
echo ""
echo "Group structure:"
for i in {1..10}; do
    GROUP_DIR="$OUTPUT_DIR/group_$(printf "%02d" $i)"
    if [ -d "$GROUP_DIR" ]; then
        COUNT=$(find "$GROUP_DIR" -name "*.json" | wc -l)
        echo "  group_$(printf "%02d" $i): $COUNT structures"
    fi
done
echo ""
echo "To load structures:"
echo "  from examples.download_mp_data import load_structure"
echo "  from pathlib import Path"
echo "  structure, props = load_structure(Path('$OUTPUT_DIR/group_01/mp-XXXXX.json'))"

