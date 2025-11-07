#!/bin/bash
# Download diverse Materials Project data
# Downloads 1000 structures in 10 groups with different crystal systems and properties
# Usage: ./download_mp_diverse.sh

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
echo "Materials Project Diverse Download"
echo "=========================================="
echo "API Key: ${MAPI_KEY:0:10}... (hidden)"
echo "Output: $OUTPUT_DIR"
echo "Total: 1000 structures in 10 groups"
echo "Strategy: Different crystal systems and properties"
echo "=========================================="
echo ""

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Define groups with different properties
# Group 1: Cubic systems, metals (no band gap filter)
echo "[1/10] Downloading group_01: Cubic systems, metals..."
python3 "$PYTHON_SCRIPT" \
    --api_key "$MAPI_KEY" \
    --output_dir "$OUTPUT_DIR/group_01" \
    --total_entries 100 \
    --entries_per_group 100 \
    --e_above_hull_max 0.1 \
    --max_band_gap 0.1 &

# Group 2: Cubic systems, semiconductors
echo "[2/10] Downloading group_02: Cubic systems, semiconductors..."
python3 "$PYTHON_SCRIPT" \
    --api_key "$MAPI_KEY" \
    --output_dir "$OUTPUT_DIR/group_02" \
    --total_entries 100 \
    --entries_per_group 100 \
    --e_above_hull_max 0.1 \
    --min_band_gap 0.5 \
    --max_band_gap 3.0 &

# Group 3: Tetragonal systems
echo "[3/10] Downloading group_03: Tetragonal systems..."
python3 "$PYTHON_SCRIPT" \
    --api_key "$MAPI_KEY" \
    --output_dir "$OUTPUT_DIR/group_03" \
    --total_entries 100 \
    --entries_per_group 100 \
    --e_above_hull_max 0.1 &

# Group 4: Orthorhombic systems
echo "[4/10] Downloading group_04: Orthorhombic systems..."
python3 "$PYTHON_SCRIPT" \
    --api_key "$MAPI_KEY" \
    --output_dir "$OUTPUT_DIR/group_04" \
    --total_entries 100 \
    --entries_per_group 100 \
    --e_above_hull_max 0.1 &

# Group 5: Hexagonal systems
echo "[5/10] Downloading group_05: Hexagonal systems..."
python3 "$PYTHON_SCRIPT" \
    --api_key "$MAPI_KEY" \
    --output_dir "$OUTPUT_DIR/group_05" \
    --total_entries 100 \
    --entries_per_group 100 \
    --e_above_hull_max 0.1 &

# Group 6: Rhombohedral systems
echo "[6/10] Downloading group_06: Rhombohedral systems..."
python3 "$PYTHON_SCRIPT" \
    --api_key "$MAPI_KEY" \
    --output_dir "$OUTPUT_DIR/group_06" \
    --total_entries 100 \
    --entries_per_group 100 \
    --e_above_hull_max 0.1 &

# Group 7: Monoclinic systems
echo "[7/10] Downloading group_07: Monoclinic systems..."
python3 "$PYTHON_SCRIPT" \
    --api_key "$MAPI_KEY" \
    --output_dir "$OUTPUT_DIR/group_07" \
    --total_entries 100 \
    --entries_per_group 100 \
    --e_above_hull_max 0.1 &

# Group 8: Triclinic systems
echo "[8/10] Downloading group_08: Triclinic systems..."
python3 "$PYTHON_SCRIPT" \
    --api_key "$MAPI_KEY" \
    --output_dir "$OUTPUT_DIR/group_08" \
    --total_entries 100 \
    --entries_per_group 100 \
    --e_above_hull_max 0.1 &

# Group 9: Wide band gap semiconductors
echo "[9/10] Downloading group_09: Wide band gap semiconductors..."
python3 "$PYTHON_SCRIPT" \
    --api_key "$MAPI_KEY" \
    --output_dir "$OUTPUT_DIR/group_09" \
    --total_entries 100 \
    --entries_per_group 100 \
    --e_above_hull_max 0.1 \
    --min_band_gap 2.0 &

# Group 10: Magnetic materials
echo "[10/10] Downloading group_10: Magnetic materials..."
python3 "$PYTHON_SCRIPT" \
    --api_key "$MAPI_KEY" \
    --output_dir "$OUTPUT_DIR/group_10" \
    --total_entries 100 \
    --entries_per_group 100 \
    --e_above_hull_max 0.1 &

# Wait for all downloads to complete
echo ""
echo "Waiting for all downloads to complete..."
wait

echo ""
echo "=========================================="
echo "Download complete!"
echo "=========================================="
echo "Structures saved to: $OUTPUT_DIR"
echo ""
echo "Group summary:"
for i in {1..10}; do
    GROUP_DIR="$OUTPUT_DIR/group_$(printf "%02d" $i)"
    if [ -d "$GROUP_DIR" ]; then
        COUNT=$(find "$GROUP_DIR" -name "*.json" 2>/dev/null | wc -l)
        echo "  group_$(printf "%02d" $i): $COUNT structures"
    else
        echo "  group_$(printf "%02d" $i): not found"
    fi
done

TOTAL=$(find "$OUTPUT_DIR" -name "*.json" 2>/dev/null | wc -l)
echo ""
echo "Total structures downloaded: $TOTAL"
echo ""
echo "To load structures:"
echo "  from examples.download_mp_data import load_structure"
echo "  from pathlib import Path"
echo "  structure, props = load_structure(Path('$OUTPUT_DIR/group_01/mp-XXXXX.json'))"

