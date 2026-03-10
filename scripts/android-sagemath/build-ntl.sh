#!/usr/bin/env bash
# ==============================================================================
# Cross-compile NTL 11.5.1 for Android
# ==============================================================================
# NTL (Number Theory Library) provides lattice basis reduction, polynomial
# factoring over Z and GF(p), and other number-theoretic algorithms.
# Depends on GMP.
#
# Key cross-compile notes:
#   - NTL uses its own configure script in src/
#   - Must set CXX, AR, RANLIB, CXXFLAGS explicitly
#   - SHARED=off for static-only build
#   - NTL_THREADS=off (Android pthreads quirks)
#   - NTL_GMP_LIP=on to use GMP for large integer arithmetic
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/env-android.sh"

NTL_VERSION="11.5.1"
NTL_TARBALL="ntl-${NTL_VERSION}.tar.gz"
NTL_URL="https://libntl.org/${NTL_TARBALL}"
NTL_SRC="${SAGEMATH_SRC_DIR}/ntl-${NTL_VERSION}"
NTL_BUILD="${SAGEMATH_BUILD_DIR}/ntl"

# Check prerequisites
if [ ! -f "${SAGEMATH_PREFIX}/lib/libgmp.a" ]; then
    echo "ERROR: GMP not found. Build GMP first."
    exit 1
fi

# Check if already built
if [ -f "${SAGEMATH_PREFIX}/lib/libntl.a" ]; then
    echo "NTL ${NTL_VERSION} already built. Skipping."
    exit 0
fi

echo ">>> Building NTL ${NTL_VERSION} for ${ANDROID_TRIPLE}"

# Download
if [ ! -f "${SAGEMATH_SRC_DIR}/${NTL_TARBALL}" ]; then
    echo "  Downloading NTL..."
    curl -L -o "${SAGEMATH_SRC_DIR}/${NTL_TARBALL}" "$NTL_URL"
fi

# Extract
if [ ! -d "$NTL_SRC" ]; then
    echo "  Extracting..."
    tar -xf "${SAGEMATH_SRC_DIR}/${NTL_TARBALL}" -C "$SAGEMATH_SRC_DIR"
fi

# NTL builds from its src/ subdirectory
cd "$NTL_SRC/src"

echo "  Configuring..."
./configure \
    PREFIX="${SAGEMATH_PREFIX}" \
    GMP_PREFIX="${SAGEMATH_PREFIX}" \
    CXX="$CXX" \
    AR="$AR" \
    RANLIB="$RANLIB" \
    CXXFLAGS="$CXXFLAGS $CPPFLAGS -I${SAGEMATH_PREFIX}/include" \
    LDFLAGS="$LDFLAGS" \
    SHARED=off \
    NTL_THREADS=off \
    NTL_GMP_LIP=on \
    NTL_STD_CXX14=on \
    TUNE=generic \
    > "${SAGEMATH_BUILD_DIR}/ntl-configure.log" 2>&1

echo "  Compiling (${NPROC} jobs)..."
make -j"$NPROC" > "${SAGEMATH_BUILD_DIR}/ntl-build.log" 2>&1

echo "  Installing..."
make install > "${SAGEMATH_BUILD_DIR}/ntl-install.log" 2>&1

# Verify
if [ -f "${SAGEMATH_PREFIX}/lib/libntl.a" ]; then
    echo ">>> NTL ${NTL_VERSION} built successfully"
    echo "  Static lib: libntl.a ($(du -h "${SAGEMATH_PREFIX}/lib/libntl.a" | cut -f1))"
else
    echo "ERROR: NTL build failed. Check ${SAGEMATH_BUILD_DIR}/ntl-build.log"
    exit 1
fi
