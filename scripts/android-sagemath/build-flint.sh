#!/usr/bin/env bash
# ==============================================================================
# Cross-compile FLINT 3.1.3 for Android
# ==============================================================================
# FLINT (Fast Library for Number Theory) provides polynomial arithmetic,
# factorization, and number-theoretic functions. Depends on GMP and MPFR.
#
# Key cross-compile notes:
#   - FLINT 3.x uses CMake, not autotools
#   - Must point CMAKE_FIND_ROOT_PATH to our prefix so it finds GMP/MPFR
#   - Disable threading (pthreads behaves differently on Android)
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/env-android.sh"

FLINT_VERSION="3.1.3"
FLINT_TARBALL="flint-${FLINT_VERSION}.tar.gz"
FLINT_URL="https://github.com/flintlib/flint/releases/download/v${FLINT_VERSION}/${FLINT_TARBALL}"
FLINT_SRC="${SAGEMATH_SRC_DIR}/flint-${FLINT_VERSION}"
FLINT_BUILD="${SAGEMATH_BUILD_DIR}/flint"

# Check prerequisites
if [ ! -f "${SAGEMATH_PREFIX}/lib/libgmp.a" ]; then
    echo "ERROR: GMP not found. Build GMP first."
    exit 1
fi
if [ ! -f "${SAGEMATH_PREFIX}/lib/libmpfr.a" ]; then
    echo "ERROR: MPFR not found. Build MPFR first."
    exit 1
fi

# Check if already built
if [ -f "${SAGEMATH_PREFIX}/lib/libflint.a" ]; then
    echo "FLINT ${FLINT_VERSION} already built. Skipping."
    exit 0
fi

echo ">>> Building FLINT ${FLINT_VERSION} for ${ANDROID_TRIPLE}"

# Download
if [ ! -f "${SAGEMATH_SRC_DIR}/${FLINT_TARBALL}" ]; then
    echo "  Downloading FLINT..."
    curl -L -o "${SAGEMATH_SRC_DIR}/${FLINT_TARBALL}" "$FLINT_URL"
fi

# Extract
if [ ! -d "$FLINT_SRC" ]; then
    echo "  Extracting..."
    tar -xf "${SAGEMATH_SRC_DIR}/${FLINT_TARBALL}" -C "$SAGEMATH_SRC_DIR"
fi

# Build with CMake
rm -rf "$FLINT_BUILD"
mkdir -p "$FLINT_BUILD"
cd "$FLINT_BUILD"

# Create CMake toolchain file for Android NDK
cat > android-toolchain.cmake << TOOLCHAIN_EOF
set(CMAKE_SYSTEM_NAME Android)
set(CMAKE_SYSTEM_VERSION ${ANDROID_API_LEVEL})
set(CMAKE_ANDROID_ARCH_ABI ${ANDROID_ABI})
set(CMAKE_ANDROID_NDK ${NDK_HOME})
set(CMAKE_ANDROID_STL_TYPE c++_static)

set(CMAKE_C_COMPILER ${CC})
set(CMAKE_CXX_COMPILER ${CXX})
set(CMAKE_AR ${AR} CACHE FILEPATH "Archiver")
set(CMAKE_RANLIB ${RANLIB} CACHE FILEPATH "Ranlib")

set(CMAKE_FIND_ROOT_PATH ${SAGEMATH_PREFIX})
set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)

set(CMAKE_C_FLAGS "${CFLAGS}" CACHE STRING "C flags")
set(CMAKE_CXX_FLAGS "${CXXFLAGS}" CACHE STRING "CXX flags")
TOOLCHAIN_EOF

echo "  Configuring with CMake..."
cmake "$FLINT_SRC" \
    -DCMAKE_TOOLCHAIN_FILE=android-toolchain.cmake \
    -DCMAKE_INSTALL_PREFIX="${SAGEMATH_PREFIX}" \
    -DCMAKE_BUILD_TYPE=Release \
    -DBUILD_SHARED_LIBS=OFF \
    -DBUILD_TESTING=OFF \
    -DBUILD_DOCS=OFF \
    -DWITH_NTL=OFF \
    -DGMP_INCLUDE_DIR="${SAGEMATH_PREFIX}/include" \
    -DGMP_LIBRARY="${SAGEMATH_PREFIX}/lib/libgmp.a" \
    -DMPFR_INCLUDE_DIR="${SAGEMATH_PREFIX}/include" \
    -DMPFR_LIBRARY="${SAGEMATH_PREFIX}/lib/libmpfr.a" \
    > configure.log 2>&1

echo "  Compiling (${NPROC} jobs)..."
cmake --build . -j"$NPROC" > build.log 2>&1

echo "  Installing..."
cmake --install . > install.log 2>&1

# Verify
if [ -f "${SAGEMATH_PREFIX}/lib/libflint.a" ]; then
    echo ">>> FLINT ${FLINT_VERSION} built successfully"
    echo "  Static lib: libflint.a ($(du -h "${SAGEMATH_PREFIX}/lib/libflint.a" | cut -f1))"
else
    echo "ERROR: FLINT build failed. Check ${FLINT_BUILD}/build.log"
    exit 1
fi
