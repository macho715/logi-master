#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[RunLocal] Activating inbox reader (dry run)..."
python -m inbox_reader --dry-run --verbose

echo "[RunLocal] Generating sample report..."
python -m report_builder --sample --verbose

echo "[RunLocal] Outputs located in work/"
