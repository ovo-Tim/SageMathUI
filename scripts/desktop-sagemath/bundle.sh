#!/usr/bin/env bash
set -euo pipefail

# Creates a portable Python + SymPy bundle for desktop platforms.
# Uses python-build-standalone for a fully self-contained Python installation.
#
# Usage: ./bundle.sh <triple>
# Triples:
#   aarch64-apple-darwin
#   x86_64-apple-darwin
#   x86_64-unknown-linux-gnu
#   x86_64-pc-windows-msvc

PYTHON_VERSION="${PYTHON_VERSION:-3.12.8}"
PBS_RELEASE="${PBS_RELEASE:-20241219}"

TRIPLE="${1:?Usage: $0 <triple>}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
WORK_DIR="$PROJECT_ROOT/sagemath-desktop-build"
BUNDLE_DIR="$WORK_DIR/sagemath-bundle"
OUTPUT_DIR="$PROJECT_ROOT/src-tauri/resources"
OUTPUT="$OUTPUT_DIR/sagemath-bundle.tar.gz"

echo "=== Building SageMath desktop bundle ==="
echo "  Triple:  $TRIPLE"
echo "  Python:  $PYTHON_VERSION"
echo "  Release: $PBS_RELEASE"

# ── Clean previous build ──────────────────────────────────────────
rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR" "$BUNDLE_DIR" "$OUTPUT_DIR"

# ── Download python-build-standalone ──────────────────────────────
PBS_URL="https://github.com/indygreg/python-build-standalone/releases/download/${PBS_RELEASE}/cpython-${PYTHON_VERSION}+${PBS_RELEASE}-${TRIPLE}-install_only.tar.gz"
echo ""
echo "Downloading Python from:"
echo "  $PBS_URL"
curl -fSL -o "$WORK_DIR/python.tar.gz" "$PBS_URL"

echo "Extracting Python..."
tar xzf "$WORK_DIR/python.tar.gz" -C "$BUNDLE_DIR"

# ── Determine platform-specific paths ─────────────────────────────
PYTHON_MAJOR_MINOR="${PYTHON_VERSION%.*}"  # e.g., "3.12"

case "$TRIPLE" in
    *windows*)
        PYTHON_BIN="$BUNDLE_DIR/python/python.exe"
        PIP_CMD=("$PYTHON_BIN" -m pip)
        SITE_PACKAGES="$BUNDLE_DIR/python/Lib/site-packages"
        ;;
    *)
        PYTHON_BIN="$BUNDLE_DIR/python/bin/python3"
        PIP_CMD=("$PYTHON_BIN" -m pip)
        SITE_PACKAGES="$BUNDLE_DIR/python/lib/python${PYTHON_MAJOR_MINOR}/site-packages"
        ;;
esac

if [[ ! -f "$PYTHON_BIN" ]]; then
    echo "ERROR: Python binary not found at $PYTHON_BIN"
    echo "Bundle directory contents:"
    find "$BUNDLE_DIR" -maxdepth 3 -type f | head -20
    exit 1
fi

echo "Python binary: $PYTHON_BIN"
"$PYTHON_BIN" --version

# ── Install SymPy (pulls mpmath as dependency) ────────────────────
echo ""
echo "Installing SymPy..."
"${PIP_CMD[@]}" install --no-cache-dir --disable-pip-version-check sympy

echo ""
echo "Installed packages:"
"${PIP_CMD[@]}" list --format=columns 2>/dev/null || "${PIP_CMD[@]}" list

# ── Strip unnecessary files to reduce bundle size ─────────────────
echo ""
echo "Stripping unnecessary files..."

# Remove __pycache__ and .pyc files
find "$BUNDLE_DIR/python" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "$BUNDLE_DIR/python" -name "*.pyc" -delete 2>/dev/null || true

# Remove test suites
find "$BUNDLE_DIR/python" -path "*/test/*" -type f -delete 2>/dev/null || true
find "$BUNDLE_DIR/python" -path "*/tests/*" -type f -delete 2>/dev/null || true
find "$BUNDLE_DIR/python" -name "test" -type d -empty -delete 2>/dev/null || true
find "$BUNDLE_DIR/python" -name "tests" -type d -empty -delete 2>/dev/null || true

# Remove packages not needed at runtime
case "$TRIPLE" in
    *windows*)
        rm -rf "$BUNDLE_DIR/python/Lib/ensurepip" 2>/dev/null || true
        rm -rf "$BUNDLE_DIR/python/Lib/idlelib" 2>/dev/null || true
        rm -rf "$BUNDLE_DIR/python/Lib/tkinter" 2>/dev/null || true
        rm -rf "$BUNDLE_DIR/python/Lib/distutils" 2>/dev/null || true
        rm -rf "$BUNDLE_DIR/python/Lib/unittest" 2>/dev/null || true
        rm -rf "$BUNDLE_DIR/python/Scripts" 2>/dev/null || true
        ;;
    *)
        rm -rf "$BUNDLE_DIR/python/lib/python${PYTHON_MAJOR_MINOR}/ensurepip" 2>/dev/null || true
        rm -rf "$BUNDLE_DIR/python/lib/python${PYTHON_MAJOR_MINOR}/idlelib" 2>/dev/null || true
        rm -rf "$BUNDLE_DIR/python/lib/python${PYTHON_MAJOR_MINOR}/tkinter" 2>/dev/null || true
        rm -rf "$BUNDLE_DIR/python/lib/python${PYTHON_MAJOR_MINOR}/distutils" 2>/dev/null || true
        rm -rf "$BUNDLE_DIR/python/lib/python${PYTHON_MAJOR_MINOR}/unittest" 2>/dev/null || true
        # Remove pip/setuptools executables (keep the packages for potential pip use)
        rm -f "$BUNDLE_DIR/python/bin/pip"* 2>/dev/null || true
        ;;
esac

# Remove .dist-info directories (pip metadata)
find "$BUNDLE_DIR/python" -name "*.dist-info" -type d -exec rm -rf {} + 2>/dev/null || true

# ── Write version marker ──────────────────────────────────────────
echo "$PYTHON_VERSION" > "$BUNDLE_DIR/python/.bundle-version"

# ── Create tarball ────────────────────────────────────────────────
echo ""
echo "Creating bundle tarball..."
tar czf "$OUTPUT" -C "$BUNDLE_DIR" python/

echo ""
echo "=== Bundle created ==="
echo "  Output: $OUTPUT"
du -sh "$OUTPUT"

# ── Clean up ──────────────────────────────────────────────────────
rm -rf "$WORK_DIR"
echo "Done."
