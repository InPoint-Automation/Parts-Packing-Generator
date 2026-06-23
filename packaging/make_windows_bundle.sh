#!/usr/bin/env bash
# ====================================================================
#  Build a clean source bundle to ship to the Windows build machine.
#  Copies ONLY the files needed to run packaging\build_windows.bat,
#  leaving out venvs, __pycache__, data/config dirs, git and docs.
#  Produces a single zip in dist/.
# ====================================================================
set -euo pipefail

# repo root = parent of this script's dir
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VERSION="$(sed -n 's/^__version__ = "\(.*\)"/\1/p' partspack/__init__.py | head -1)"
VERSION="${VERSION:-unknown}"

STAGE_NAME="PartsPack-${VERSION}-src"
OUT_DIR="$ROOT/dist"
STAGE="$OUT_DIR/$STAGE_NAME"
ZIP="$OUT_DIR/${STAGE_NAME}.zip"

INCLUDE=(
    PartsPack.py
    PartsPack.spec
    partspack
    requirements-windowsbundle.txt
    pyproject.toml
    packaging
    README.md
    LICENSE
    CHANGELOG.md
)

echo "=== Staging $STAGE_NAME ==="
rm -rf "$STAGE" "$ZIP"
mkdir -p "$STAGE"

for item in "${INCLUDE[@]}"; do
    if [ ! -e "$item" ]; then
        echo "  skip (missing): $item"
        continue
    fi
    echo "  add: $item"
    rsync -a --relative \
        --exclude='__pycache__/' \
        --exclude='*.pyc' \
        --exclude='.build-venv/' \
        --exclude='.venv/' \
        "$item" "$STAGE/"
done

echo "=== Zipping ==="
( cd "$OUT_DIR" && zip -1 -rq "${STAGE_NAME}.zip" "$STAGE_NAME" )

echo
echo "=== DONE ==="
echo "Bundle: $ZIP"
echo "Size:   $(du -h "$ZIP" | cut -f1)"
echo "Copy it to the Windows box, unzip, then run: packaging\\build_windows.bat"
