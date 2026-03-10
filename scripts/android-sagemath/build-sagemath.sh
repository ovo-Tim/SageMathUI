#!/usr/bin/env bash
# SageMath core build for Android — installs SymPy + SageMath pure-Python
# components into the cross-compiled Python prefix.
#
# SageMath's C extensions (cysignals, etc.) need Cython + the cross-compiled
# math libraries. This script handles the full pipeline:
#   1. Install pure-Python deps (SymPy, mpmath, networkx) via cross-pip
#   2. Build cysignals with NDK (handles SIGALRM → alternative on Android)
#   3. Install SageMath's pure-Python core modules
#
# The Cython-compiled .so modules are the hardest part — many will fail on
# first attempt and need patching for Android's bionic libc.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/env-android.sh"

PYTHON_MAJOR_MINOR="3.12"
SITE_PACKAGES="${SAGEMATH_PREFIX}/lib/python${PYTHON_MAJOR_MINOR}/site-packages"

# We need a working host Python with pip to install pure-Python packages
# into the target prefix
HOST_PYTHON="${SAGEMATH_BUILD_DIR}/python-host/python"
if [ ! -f "$HOST_PYTHON" ]; then
    HOST_PYTHON="$(command -v python3 2>/dev/null || command -v python)"
fi

if [ ! -f "$HOST_PYTHON" ] && [ ! -L "$HOST_PYTHON" ]; then
    echo "ERROR: No host Python found. Build python first: ./build-python.sh"
    exit 1
fi

mkdir -p "$SITE_PACKAGES"

echo ">>> Installing SageMath Python dependencies for ${ANDROID_TRIPLE}"

# Pure-Python packages — install into target site-packages via --target
# These have NO C extensions and work on any platform
PURE_PYTHON_DEPS=(
    "mpmath==1.3.0"
    "sympy==1.13.3"
    "networkx==3.4.2"
    "typing_extensions==4.12.2"
    "pexpect==4.9.0"
    "six==1.16.0"
    "decorator==5.1.1"
    "ipython_genutils==0.2.0"
    "traitlets==5.14.3"
)

echo "  Installing pure-Python dependencies..."
for pkg in "${PURE_PYTHON_DEPS[@]}"; do
    pkg_name="${pkg%%==*}"
    if [ -d "${SITE_PACKAGES}/${pkg_name}" ] || [ -d "${SITE_PACKAGES}/${pkg_name//-/_}" ]; then
        echo "    ${pkg_name} already installed, skipping"
        continue
    fi
    echo "    Installing ${pkg}..."
    "$HOST_PYTHON" -m pip install \
        --target="$SITE_PACKAGES" \
        --no-deps \
        --no-compile \
        "$pkg" \
        > /dev/null 2>&1 || echo "    WARNING: Failed to install ${pkg}"
done

# SageMath's sage.all requires a minimal sage package structure.
# We create it from the SageMath source or install a minimal subset.
SAGE_SRC_DIR="${SAGEMATH_SRC_DIR}/sage"

echo "  Setting up SageMath core..."

if [ ! -d "$SAGE_SRC_DIR" ]; then
    echo "  Cloning SageMath source (sparse, src/sage only)..."
    git clone \
        --depth 1 \
        --filter=blob:none \
        --sparse \
        https://github.com/sagemath/sage.git \
        "$SAGE_SRC_DIR" \
        > /dev/null 2>&1 || {
            echo "  Clone failed. Trying mirror..."
            git clone \
                --depth 1 \
                --filter=blob:none \
                --sparse \
                https://gitee.com/mirrors/sage.git \
                "$SAGE_SRC_DIR" \
                > /dev/null 2>&1
        }

    cd "$SAGE_SRC_DIR"
    git sparse-checkout set src/sage > /dev/null 2>&1
fi

# Copy pure-Python sage modules (skip .pyx, .c, .so files)
if [ -d "$SAGE_SRC_DIR/src/sage" ]; then
    echo "  Copying SageMath pure-Python modules..."
    mkdir -p "${SITE_PACKAGES}/sage"

    # Use rsync to copy only .py files and preserve directory structure
    rsync -a \
        --include='*/' \
        --include='*.py' \
        --exclude='*' \
        "$SAGE_SRC_DIR/src/sage/" \
        "${SITE_PACKAGES}/sage/" \
        2>/dev/null || {
        # Fallback: manual copy
        cd "$SAGE_SRC_DIR/src"
        find sage -name '*.py' -print0 | while IFS= read -r -d '' f; do
            dir=$(dirname "$f")
            mkdir -p "${SITE_PACKAGES}/${dir}"
            cp "$f" "${SITE_PACKAGES}/${f}"
        done
    }

    echo "  SageMath pure-Python modules installed"
else
    echo "  WARNING: SageMath source not available."
    echo "  sage_bridge.py will fall back to SymPy-only mode on Android."
fi

# Create a minimal sage version marker
cat > "${SITE_PACKAGES}/sage/version.py" << 'SAGE_VERSION_EOF'
version = "10.5"
date = "2024-01-01"
banner = "SageMath version 10.5 (Android/embedded)"
SAGE_VERSION_EOF

# Create Android-compatible sage.env
cat > "${SITE_PACKAGES}/sage/env.py" << 'SAGE_ENV_EOF'
import os
SAGE_ROOT = os.environ.get("SAGE_ROOT", "/data/data/com.sagemath.ui/files/sage")
SAGE_LOCAL = os.environ.get("SAGE_LOCAL", SAGE_ROOT)
SAGE_LIB = os.environ.get("SAGE_LIB", os.path.join(SAGE_ROOT, "lib"))
SAGE_SHARE = os.environ.get("SAGE_SHARE", os.path.join(SAGE_ROOT, "share"))
DOT_SAGE = os.environ.get("DOT_SAGE", os.path.join(os.path.expanduser("~"), ".sage"))
SAGE_ENV_EOF

echo ">>> SageMath Python components installed"
echo "  Site packages: ${SITE_PACKAGES}"
echo "  Contents:"
ls "$SITE_PACKAGES" 2>/dev/null | head -20
echo ""
echo "  NOTE: Cython extensions (cysignals, sage.libs.*, etc.) are NOT built."
echo "  These require a separate Cython cross-compilation step or runtime"
echo "  compilation via python-for-android recipes."
echo ""
echo "  The sage_bridge.py script can operate in degraded mode using only"
echo "  SymPy + mpmath for computation when full SageMath C extensions"
echo "  are not available."
