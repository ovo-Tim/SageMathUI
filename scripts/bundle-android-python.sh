#!/usr/bin/env bash
set -euo pipefail

# All paths can be overridden via environment variables for CI compatibility.
# Defaults point to the local development setup on macOS.
PROJECT_ROOT="${PROJECT_ROOT:-$(cd "$(dirname "$0")/.." && pwd)}"
CROSS_PREFIX="${CROSS_PREFIX:-$PROJECT_ROOT/sagemath-android/src/Python-3.13.3/cross-build/aarch64-linux-android/prefix}"

# Auto-detect NDK strip tool (CI = linux-x86_64, local = darwin-x86_64)
if [ -z "${NDK_STRIP:-}" ]; then
    NDK_ROOT="${NDK_HOME:-${ANDROID_HOME:-$HOME/Library/Android/sdk}/ndk/27.0.12077973}"
    if [[ "$OSTYPE" == "darwin"* ]]; then
        NDK_STRIP="$NDK_ROOT/toolchains/llvm/prebuilt/darwin-x86_64/bin/llvm-strip"
    else
        NDK_STRIP="$NDK_ROOT/toolchains/llvm/prebuilt/linux-x86_64/bin/llvm-strip"
    fi
fi

ANDROID_APP="$PROJECT_ROOT/src-tauri/gen/android/app/src/main"
ASSETS_DIR="$ANDROID_APP/assets"
JNILIBS_DIR="$ANDROID_APP/jniLibs/arm64-v8a"
STAGING="$PROJECT_ROOT/sagemath-android/staging"

echo "PROJECT_ROOT: $PROJECT_ROOT"
echo "CROSS_PREFIX: $CROSS_PREFIX"
echo "NDK_STRIP:    $NDK_STRIP"
echo ""

echo "=== Step 1: Clean staging area ==="
rm -rf "$STAGING"
mkdir -p "$STAGING/python/lib/python3.13"
mkdir -p "$STAGING/python/lib/python3.13/site-packages"

echo "=== Step 2: Copy and trim stdlib ==="
cp -a "$CROSS_PREFIX/lib/python3.13/" "$STAGING/python/lib/python3.13/"

REMOVE_DIRS=(
    test tests tkinter idlelib turtledemo ensurepip
    lib2to3 distutils config-3.13-aarch64-linux-android
)
for dir in "${REMOVE_DIRS[@]}"; do
    rm -rf "$STAGING/python/lib/python3.13/$dir"
    echo "  Removed $dir"
done

# Remove unnecessary C extensions from lib-dynload (keep essential ones)
DYNLOAD="$STAGING/python/lib/python3.13/lib-dynload"
REMOVE_SO=(
    _ctypes_test _testbuffer _testcapi _testclinic_limited _testclinic
    _testexternalinspection _testimportmultiple _testinternalcapi
    _testlimitedcapi _testmultiphase _testsinglephase _xxtestfuzz
    xxlimited_35 xxlimited xxsubtype
    _sqlite3 _ssl _lsprof _interpchannels _interpqueues _interpreters
    _codecs_cn _codecs_hk _codecs_iso2022 _codecs_jp _codecs_kr _codecs_tw
    _multibytecodec termios syslog resource
)
for mod in "${REMOVE_SO[@]}"; do
    rm -f "$DYNLOAD/${mod}".cpython-*.so
done
echo "  Trimmed lib-dynload: removed ${#REMOVE_SO[@]} unnecessary extensions"

# Strip debug symbols from remaining .so files
for so in "$DYNLOAD"/*.so; do
    "$NDK_STRIP" --strip-debug "$so" 2>/dev/null || true
done
echo "  Stripped lib-dynload .so files"

find "$STAGING" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "$STAGING" -name "*.pyc" -delete 2>/dev/null || true
echo "  Removed all __pycache__ and .pyc files"

find "$STAGING" -name "test_*.py" -delete 2>/dev/null || true
find "$STAGING" -name "*_test.py" -delete 2>/dev/null || true
echo "  Removed test files"

TRIMMED_SIZE=$(du -sh "$STAGING/python/lib/python3.13/" | cut -f1)
echo "  Trimmed stdlib: $TRIMMED_SIZE"

echo "=== Step 3: Install SymPy + mpmath ==="
SITE_PACKAGES="$STAGING/python/lib/python3.13/site-packages"

pip3 install --target "$SITE_PACKAGES" --no-deps --no-compile sympy mpmath 2>&1 | tail -5

find "$SITE_PACKAGES" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true
find "$SITE_PACKAGES" -name "*.pyc" -delete 2>/dev/null || true
rm -rf "$SITE_PACKAGES"/*.dist-info
rm -rf "$SITE_PACKAGES/sympy/testing" "$SITE_PACKAGES/sympy/benchmarks"

if [[ "$OSTYPE" == "darwin"* ]]; then
    sed -i '' 's/^from importlib.metadata import version$/__version__ = "1.3.0"/' "$SITE_PACKAGES/mpmath/__init__.py"
    sed -i '' '/^__version__ = version(__name__)$/d' "$SITE_PACKAGES/mpmath/__init__.py"
    sed -i '' '/^del version$/d' "$SITE_PACKAGES/mpmath/__init__.py"
else
    sed -i 's/^from importlib.metadata import version$/__version__ = "1.3.0"/' "$SITE_PACKAGES/mpmath/__init__.py"
    sed -i '/^__version__ = version(__name__)$/d' "$SITE_PACKAGES/mpmath/__init__.py"
    sed -i '/^del version$/d' "$SITE_PACKAGES/mpmath/__init__.py"
fi
echo "  Patched mpmath __init__.py to hardcode version"

SYMPY_SIZE=$(du -sh "$SITE_PACKAGES/sympy/" 2>/dev/null | cut -f1)
MPMATH_SIZE=$(du -sh "$SITE_PACKAGES/mpmath/" 2>/dev/null | cut -f1)
echo "  SymPy: $SYMPY_SIZE, mpmath: $MPMATH_SIZE"

echo "=== Step 4: Strip and copy binaries to jniLibs ==="
mkdir -p "$JNILIBS_DIR"

cp -L "$CROSS_PREFIX/bin/python3.13" "$JNILIBS_DIR/libpython_exec.so"
cp -L "$CROSS_PREFIX/lib/libpython3.13.so" "$JNILIBS_DIR/libpython3.13.so"
if [ -f "$CROSS_PREFIX/lib/libpython3.so" ]; then
    cp -L "$CROSS_PREFIX/lib/libpython3.so" "$JNILIBS_DIR/libpython3.so"
fi

BEFORE_STRIP=$(du -sh "$JNILIBS_DIR" | cut -f1)
"$NDK_STRIP" --strip-debug "$JNILIBS_DIR/libpython3.13.so"
"$NDK_STRIP" --strip-unneeded "$JNILIBS_DIR/libpython_exec.so" 2>/dev/null || true
[ -f "$JNILIBS_DIR/libpython3.so" ] && "$NDK_STRIP" --strip-debug "$JNILIBS_DIR/libpython3.so" 2>/dev/null || true
AFTER_STRIP=$(du -sh "$JNILIBS_DIR" | cut -f1)
echo "  Before strip: $BEFORE_STRIP → After strip: $AFTER_STRIP"

echo "=== Step 5: Copy assets ==="
rm -rf "$ASSETS_DIR/python" "$ASSETS_DIR/sage_bridge.py"
mkdir -p "$ASSETS_DIR"

cp -a "$STAGING/python" "$ASSETS_DIR/python"
cp "$PROJECT_ROOT/src-tauri/sage_bridge.py" "$ASSETS_DIR/sage_bridge.py"

ASSETS_TOTAL=$(du -sh "$ASSETS_DIR" | cut -f1)
echo "  Total assets: $ASSETS_TOTAL"

echo "=== Step 6: Summary ==="
echo "  jniLibs: $(ls -la "$JNILIBS_DIR/" | grep -c '.so') .so files"
ls -lh "$JNILIBS_DIR/"
echo ""
echo "  Assets: python stdlib + SymPy + mpmath + sage_bridge"
echo "  Total assets size: $ASSETS_TOTAL"
echo ""
echo "=== DONE. Ready to build APK. ==="
