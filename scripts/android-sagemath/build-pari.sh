#!/usr/bin/env bash
# ==============================================================================
# Cross-compile PARI/GP 2.17.3 for Android
# ==============================================================================
# PARI provides number theory computations: elliptic curves, modular forms,
# algebraic number fields. SageMath uses libpari extensively.
#
# Key cross-compile notes:
#   - PARI uses its own Configure script (not autotools, not CMake)
#   - Must pass --host and explicitly set CC/LD
#   - Kernel must be set to "none" for cross-compilation (no assembler)
#   - Thread support disabled (Android pthreads quirks)
#   - graphic=none (no X11 on Android)
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/env-android.sh"

PARI_VERSION="2.17.3"
PARI_TARBALL="pari-${PARI_VERSION}.tar.gz"
PARI_URL="https://pari.math.u-bordeaux.fr/pub/pari/unix/${PARI_TARBALL}"
PARI_SRC="${SAGEMATH_SRC_DIR}/pari-${PARI_VERSION}"
PARI_BUILD="${SAGEMATH_BUILD_DIR}/pari"

# Check prerequisites
if [ ! -f "${SAGEMATH_PREFIX}/lib/libgmp.a" ]; then
    echo "ERROR: GMP not found. Build GMP first."
    exit 1
fi

# Check if already built
if [ -f "${SAGEMATH_PREFIX}/lib/libpari.a" ]; then
    echo "PARI ${PARI_VERSION} already built. Skipping."
    exit 0
fi

echo ">>> Building PARI/GP ${PARI_VERSION} for ${ANDROID_TRIPLE}"

# Download
if [ ! -f "${SAGEMATH_SRC_DIR}/${PARI_TARBALL}" ]; then
    echo "  Downloading PARI..."
    curl -L -o "${SAGEMATH_SRC_DIR}/${PARI_TARBALL}" "$PARI_URL"
fi

# Extract
if [ ! -d "$PARI_SRC" ]; then
    echo "  Extracting..."
    tar -xf "${SAGEMATH_SRC_DIR}/${PARI_TARBALL}" -C "$SAGEMATH_SRC_DIR"
fi

# PARI's Configure is special — it must be run from source dir
cd "$PARI_SRC"

echo "  Configuring..."
# PARI's Configure doesn't follow GNU conventions.
# We use env vars and explicit flags.
./Configure \
    --host="${ANDROID_TRIPLE}" \
    --prefix="${SAGEMATH_PREFIX}" \
    --with-gmp="${SAGEMATH_PREFIX}" \
    --kernel=none \
    --graphic=none \
    --mt=single \
    --without-readline \
    CC="$CC" \
    CFLAGS="$CFLAGS $CPPFLAGS" \
    LD="$CC" \
    LDFLAGS="$LDFLAGS" \
    DLLD="$CC" \
    RANLIB="$RANLIB" \
    > "${SAGEMATH_BUILD_DIR}/pari-configure.log" 2>&1

echo "  Compiling (${NPROC} jobs)..."
# PARI builds in-tree in Olinux-* or similar directory
make -j"$NPROC" lib-sta > "${SAGEMATH_BUILD_DIR}/pari-build.log" 2>&1

echo "  Installing..."
# PARI's install target
make install-lib-sta install-include \
    > "${SAGEMATH_BUILD_DIR}/pari-install.log" 2>&1

# If install doesn't produce libpari.a in the expected location, copy manually
if [ ! -f "${SAGEMATH_PREFIX}/lib/libpari.a" ]; then
    echo "  Manual install: locating libpari.a..."
    PARI_LIB=$(find "$PARI_SRC" -name "libpari.a" -type f 2>/dev/null | head -1)
    if [ -n "$PARI_LIB" ]; then
        cp "$PARI_LIB" "${SAGEMATH_PREFIX}/lib/"
        cp -r "$PARI_SRC"/src/headers/*.h "${SAGEMATH_PREFIX}/include/" 2>/dev/null || true
        mkdir -p "${SAGEMATH_PREFIX}/include/pari"
        cp "$PARI_SRC"/src/headers/pari/*.h "${SAGEMATH_PREFIX}/include/pari/" 2>/dev/null || true
        # Copy generated headers
        PARI_OBJDIR=$(find "$PARI_SRC" -maxdepth 1 -name "O*" -type d | head -1)
        if [ -n "$PARI_OBJDIR" ]; then
            cp "$PARI_OBJDIR"/*.h "${SAGEMATH_PREFIX}/include/pari/" 2>/dev/null || true
        fi
    fi
fi

# Verify
if [ -f "${SAGEMATH_PREFIX}/lib/libpari.a" ]; then
    echo ">>> PARI/GP ${PARI_VERSION} built successfully"
    echo "  Static lib: libpari.a ($(du -h "${SAGEMATH_PREFIX}/lib/libpari.a" | cut -f1))"
else
    echo "ERROR: PARI build failed. Check ${SAGEMATH_BUILD_DIR}/pari-build.log"
    exit 1
fi
