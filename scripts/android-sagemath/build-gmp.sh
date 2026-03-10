#!/usr/bin/env bash
# ==============================================================================
# Cross-compile GMP 6.3.0 for Android
# ==============================================================================
# GMP (GNU Multiple Precision Arithmetic Library) is the foundation for all
# SageMath numerical computation. Every other library depends on it.
#
# Key cross-compile notes:
#   - Must use --disable-assembly on Android (NDK assembler incompatibilities)
#   - --enable-cxx provides C++ bindings required by FLINT and NTL
#   - --enable-fat is NOT supported for cross-compilation
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/env-android.sh"

GMP_VERSION="6.3.0"
GMP_TARBALL="gmp-${GMP_VERSION}.tar.xz"
GMP_URL="https://gmplib.org/download/gmp/${GMP_TARBALL}"
GMP_MIRROR="https://mirrors.tuna.tsinghua.edu.cn/gnu/gmp/${GMP_TARBALL}"
GMP_SRC="${SAGEMATH_SRC_DIR}/gmp-${GMP_VERSION}"
GMP_BUILD="${SAGEMATH_BUILD_DIR}/gmp"

# Check if already built
if [ -f "${SAGEMATH_PREFIX}/lib/libgmp.a" ] && [ -f "${SAGEMATH_PREFIX}/lib/libgmpxx.a" ]; then
    echo "GMP ${GMP_VERSION} already built. Skipping."
    echo "  To rebuild, remove: ${SAGEMATH_PREFIX}/lib/libgmp.a"
    exit 0
fi

echo ">>> Building GMP ${GMP_VERSION} for ${ANDROID_TRIPLE}"

# Download
if [ ! -f "${SAGEMATH_SRC_DIR}/${GMP_TARBALL}" ]; then
    echo "  Downloading GMP..."
    curl -L -o "${SAGEMATH_SRC_DIR}/${GMP_TARBALL}" "$GMP_URL" 2>/dev/null \
        || curl -L -o "${SAGEMATH_SRC_DIR}/${GMP_TARBALL}" "$GMP_MIRROR"
fi

# Extract
if [ ! -d "$GMP_SRC" ]; then
    echo "  Extracting..."
    tar -xf "${SAGEMATH_SRC_DIR}/${GMP_TARBALL}" -C "$SAGEMATH_SRC_DIR"
fi

# Build
rm -rf "$GMP_BUILD"
mkdir -p "$GMP_BUILD"
cd "$GMP_BUILD"

echo "  Configuring..."
"$GMP_SRC/configure" \
    --host="${ANDROID_TRIPLE}" \
    --prefix="${SAGEMATH_PREFIX}" \
    --enable-cxx \
    --disable-assembly \
    --disable-shared \
    --enable-static \
    --with-pic \
    CC="$CC" \
    CXX="$CXX" \
    AR="$AR" \
    RANLIB="$RANLIB" \
    STRIP="$STRIP" \
    CFLAGS="$CFLAGS" \
    CXXFLAGS="$CXXFLAGS" \
    > configure.log 2>&1

echo "  Compiling (${NPROC} jobs)..."
make -j"$NPROC" > build.log 2>&1

echo "  Installing..."
make install > install.log 2>&1

# Verify
if [ -f "${SAGEMATH_PREFIX}/lib/libgmp.a" ] && [ -f "${SAGEMATH_PREFIX}/lib/libgmpxx.a" ]; then
    echo ">>> GMP ${GMP_VERSION} built successfully"
    echo "  Static libs: libgmp.a ($(du -h "${SAGEMATH_PREFIX}/lib/libgmp.a" | cut -f1)), libgmpxx.a"
    echo "  Headers:     ${SAGEMATH_PREFIX}/include/gmp.h, gmpxx.h"
else
    echo "ERROR: GMP build failed. Check ${GMP_BUILD}/build.log"
    exit 1
fi
