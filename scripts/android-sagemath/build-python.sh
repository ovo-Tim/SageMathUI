#!/usr/bin/env bash
# ==============================================================================
# Cross-compile CPython 3.12.x for Android
# ==============================================================================
# SageMath is a Python library — we need a working Python interpreter on Android.
# CPython 3.13+ has official Android support (PEP 738), but 3.12 also works
# with patches.
#
# Strategy:
#   1. Build a HOST Python first (needed for cross-compilation bootstrapping)
#   2. Cross-compile CPython for Android using the host Python
#   3. Install pip and essential packages (SymPy, etc.) into the cross prefix
#
# Key cross-compile notes:
#   - CPython cross-compilation requires a build Python of the same version
#   - Many configure checks need ac_cv_* overrides for Android
#   - Modules requiring system libs not on Android are disabled
#   - The resulting python3 binary runs on Android via the embedded interpreter
#
# References:
#   - https://devguide.python.org/getting-started/setup-building/#android
#   - https://github.com/niccokunzmann/python-on-android
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/env-android.sh"

PYTHON_VERSION="3.12.8"
PYTHON_MAJOR_MINOR="3.12"
PYTHON_TARBALL="Python-${PYTHON_VERSION}.tar.xz"
PYTHON_URL="https://www.python.org/ftp/python/${PYTHON_VERSION}/${PYTHON_TARBALL}"
PYTHON_MIRROR="https://mirrors.huaweicloud.com/python/${PYTHON_VERSION}/${PYTHON_TARBALL}"
PYTHON_SRC="${SAGEMATH_SRC_DIR}/Python-${PYTHON_VERSION}"
PYTHON_BUILD_HOST="${SAGEMATH_BUILD_DIR}/python-host"
PYTHON_BUILD_TARGET="${SAGEMATH_BUILD_DIR}/python-target"

# Check if already built
if [ -f "${SAGEMATH_PREFIX}/lib/libpython${PYTHON_MAJOR_MINOR}.a" ]; then
    echo "Python ${PYTHON_VERSION} already built. Skipping."
    exit 0
fi

echo ">>> Building CPython ${PYTHON_VERSION} for ${ANDROID_TRIPLE}"

# Download
if [ ! -f "${SAGEMATH_SRC_DIR}/${PYTHON_TARBALL}" ]; then
    echo "  Downloading Python..."
    curl -L -o "${SAGEMATH_SRC_DIR}/${PYTHON_TARBALL}" "$PYTHON_URL" 2>/dev/null \
        || curl -L -o "${SAGEMATH_SRC_DIR}/${PYTHON_TARBALL}" "$PYTHON_MIRROR"
fi

# Extract
if [ ! -d "$PYTHON_SRC" ]; then
    echo "  Extracting..."
    tar -xf "${SAGEMATH_SRC_DIR}/${PYTHON_TARBALL}" -C "$SAGEMATH_SRC_DIR"
fi

# -------------------------------------------------------
# Step 1: Build HOST Python (for cross-compilation bootstrap)
# -------------------------------------------------------
HOST_PYTHON="${PYTHON_BUILD_HOST}/python"

if [ ! -f "$HOST_PYTHON" ]; then
    echo "  Building host Python (for cross-compile bootstrap)..."
    rm -rf "$PYTHON_BUILD_HOST"
    mkdir -p "$PYTHON_BUILD_HOST"
    cd "$PYTHON_BUILD_HOST"

    # Use system compiler for host build
    "$PYTHON_SRC/configure" \
        --prefix="${PYTHON_BUILD_HOST}/install" \
        > configure-host.log 2>&1

    make -j"$NPROC" > build-host.log 2>&1

    # The host python binary
    if [ ! -f "$PYTHON_BUILD_HOST/python" ] && [ -f "$PYTHON_BUILD_HOST/python.exe" ]; then
        HOST_PYTHON="$PYTHON_BUILD_HOST/python.exe"
    fi

    echo "  Host Python built: $HOST_PYTHON"
else
    echo "  Host Python already built: $HOST_PYTHON"
fi

# -------------------------------------------------------
# Step 2: Cross-compile Python for Android
# -------------------------------------------------------
echo "  Cross-compiling Python for Android..."
rm -rf "$PYTHON_BUILD_TARGET"
mkdir -p "$PYTHON_BUILD_TARGET"
cd "$PYTHON_BUILD_TARGET"

# Create a Setup.local to disable modules not available on Android
cat > Setup.local << 'SETUP_EOF'
# Disable modules not available on Android
*disabled*
_tkinter
_curses
_curses_panel
_dbm
_gdbm
_lzma
_uuid
audioop
grp
nis
ossaudiodev
readline
spwd
syslog
SETUP_EOF

# Android-specific configure overrides
# These skip runtime checks that can't be run during cross-compilation
CROSS_CONFIGURE_VARS=(
    ac_cv_file__dev_ptmx=no
    ac_cv_file__dev_ptc=no
    ac_cv_func_getentropy=no
    ac_cv_func_getrandom=yes
    ac_cv_header_linux_random_h=yes
    ac_cv_func_clock_gettime=yes
    ac_cv_have_long_long_format=yes
    ac_cv_func_plock=no
    ac_cv_func_lchmod=no
    ac_cv_func_fdatasync=yes
    ac_cv_buggy_getaddrinfo=no
    ac_cv_func_sigaltstack=yes
)

"$PYTHON_SRC/configure" \
    --host="${ANDROID_TRIPLE}" \
    --build="$(uname -m)-$(uname -s | tr '[:upper:]' '[:lower:]')-gnu" \
    --prefix="${SAGEMATH_PREFIX}" \
    --with-build-python="$HOST_PYTHON" \
    --enable-ipv6 \
    --disable-shared \
    --enable-optimizations=no \
    --without-ensurepip \
    --without-doc-strings \
    --with-system-ffi=no \
    CC="$CC" \
    CXX="$CXX" \
    AR="$AR" \
    RANLIB="$RANLIB" \
    READELF="$READELF" \
    CFLAGS="$CFLAGS $CPPFLAGS" \
    CXXFLAGS="$CXXFLAGS $CPPFLAGS" \
    LDFLAGS="$LDFLAGS" \
    "${CROSS_CONFIGURE_VARS[@]}" \
    > configure.log 2>&1

echo "  Compiling (${NPROC} jobs)..."
make -j"$NPROC" > build.log 2>&1 || {
    echo "  WARNING: Some modules failed to build (expected on Android). Continuing..."
}

echo "  Installing..."
make install > install.log 2>&1 || {
    echo "  WARNING: Some install steps failed. Checking core files..."
}

# Verify
if [ -f "${SAGEMATH_PREFIX}/lib/libpython${PYTHON_MAJOR_MINOR}.a" ]; then
    echo ">>> Python ${PYTHON_VERSION} built successfully"
    echo "  Static lib: libpython${PYTHON_MAJOR_MINOR}.a ($(du -h "${SAGEMATH_PREFIX}/lib/libpython${PYTHON_MAJOR_MINOR}.a" | cut -f1))"
    echo "  Stdlib:     ${SAGEMATH_PREFIX}/lib/python${PYTHON_MAJOR_MINOR}/"
elif [ -f "${SAGEMATH_PREFIX}/lib/python${PYTHON_MAJOR_MINOR}/lib-dynload" ] || \
     [ -d "${SAGEMATH_PREFIX}/lib/python${PYTHON_MAJOR_MINOR}" ]; then
    echo ">>> Python ${PYTHON_VERSION} partially built (shared mode)"
    echo "  Stdlib installed. May need adjustment for static embedding."
else
    echo "ERROR: Python build failed. Check ${PYTHON_BUILD_TARGET}/build.log"
    echo "  This is the most complex cross-compilation step."
    echo "  Consider using python-for-android (p4a) instead:"
    echo "    pip install python-for-android"
    echo "    p4a create --requirements=python3"
    exit 1
fi
