#!/usr/bin/env bash
# ==============================================================================
# Cross-compile MPFR 4.2.1 for Android
# ==============================================================================
# MPFR (Multiple Precision Floating-Point Reliable) provides arbitrary-precision
# floating-point arithmetic. Depends on GMP.
#
# Key cross-compile notes:
#   - ac_cv_header_locale_h=no fixes ARM cross-compile locale detection issue
#   - Requires GMP to be built first
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/env-android.sh"

MPFR_VERSION="4.2.1"
MPFR_TARBALL="mpfr-${MPFR_VERSION}.tar.xz"
MPFR_URL="https://www.mpfr.org/mpfr-${MPFR_VERSION}/${MPFR_TARBALL}"
MPFR_MIRROR="https://ftp.gnu.org/gnu/mpfr/${MPFR_TARBALL}"
MPFR_SRC="${SAGEMATH_SRC_DIR}/mpfr-${MPFR_VERSION}"
MPFR_BUILD="${SAGEMATH_BUILD_DIR}/mpfr"

# Check prerequisite
if [ ! -f "${SAGEMATH_PREFIX}/lib/libgmp.a" ]; then
    echo "ERROR: GMP not found. Build GMP first: ./build-gmp.sh"
    exit 1
fi

# Check if already built
if [ -f "${SAGEMATH_PREFIX}/lib/libmpfr.a" ]; then
    echo "MPFR ${MPFR_VERSION} already built. Skipping."
    exit 0
fi

echo ">>> Building MPFR ${MPFR_VERSION} for ${ANDROID_TRIPLE}"

# Download
if [ ! -f "${SAGEMATH_SRC_DIR}/${MPFR_TARBALL}" ]; then
    echo "  Downloading MPFR..."
    curl -L -o "${SAGEMATH_SRC_DIR}/${MPFR_TARBALL}" "$MPFR_URL" 2>/dev/null \
        || curl -L -o "${SAGEMATH_SRC_DIR}/${MPFR_TARBALL}" "$MPFR_MIRROR"
fi

# Extract
if [ ! -d "$MPFR_SRC" ]; then
    echo "  Extracting..."
    tar -xf "${SAGEMATH_SRC_DIR}/${MPFR_TARBALL}" -C "$SAGEMATH_SRC_DIR"
fi

# Build
rm -rf "$MPFR_BUILD"
mkdir -p "$MPFR_BUILD"
cd "$MPFR_BUILD"

echo "  Configuring..."
"$MPFR_SRC/configure" \
    --host="${ANDROID_TRIPLE}" \
    --prefix="${SAGEMATH_PREFIX}" \
    --with-gmp="${SAGEMATH_PREFIX}" \
    --disable-shared \
    --enable-static \
    --with-pic \
    ac_cv_header_locale_h=no \
    CC="$CC" \
    AR="$AR" \
    RANLIB="$RANLIB" \
    STRIP="$STRIP" \
    CFLAGS="$CFLAGS $CPPFLAGS" \
    LDFLAGS="$LDFLAGS" \
    > configure.log 2>&1

echo "  Compiling (${NPROC} jobs)..."
make -j"$NPROC" > build.log 2>&1

echo "  Installing..."
make install > install.log 2>&1

# Verify
if [ -f "${SAGEMATH_PREFIX}/lib/libmpfr.a" ]; then
    echo ">>> MPFR ${MPFR_VERSION} built successfully"
    echo "  Static lib: libmpfr.a ($(du -h "${SAGEMATH_PREFIX}/lib/libmpfr.a" | cut -f1))"
else
    echo "ERROR: MPFR build failed. Check ${MPFR_BUILD}/build.log"
    exit 1
fi
