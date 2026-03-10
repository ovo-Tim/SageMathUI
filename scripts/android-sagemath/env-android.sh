#!/usr/bin/env bash
# ==============================================================================
# SageMath Android Cross-Compilation — Environment Setup
# ==============================================================================
# Source this file before running any build-*.sh script.
#
# Usage:
#   source scripts/android-sagemath/env-android.sh
#
# Prerequisites:
#   - Android SDK with NDK 27.x installed
#   - macOS or Linux host
# ==============================================================================

set -euo pipefail

# ---------- Android SDK / NDK ----------
export ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
export NDK_VERSION="${NDK_VERSION:-27.0.12077973}"
export NDK_HOME="${ANDROID_HOME}/ndk/${NDK_VERSION}"
export ANDROID_API_LEVEL="${ANDROID_API_LEVEL:-24}"

if [ ! -d "$NDK_HOME" ]; then
    echo "ERROR: NDK not found at $NDK_HOME"
    echo "  Install with: sdkmanager 'ndk;${NDK_VERSION}'"
    exit 1
fi

# ---------- Target architecture ----------
export TARGET_ARCH="${TARGET_ARCH:-aarch64}"

case "$TARGET_ARCH" in
    aarch64)
        export ANDROID_TRIPLE="aarch64-linux-android"
        export ANDROID_ABI="arm64-v8a"
        ;;
    armv7)
        export ANDROID_TRIPLE="armv7a-linux-androideabi"
        export ANDROID_ABI="armeabi-v7a"
        ;;
    x86_64)
        export ANDROID_TRIPLE="x86_64-linux-android"
        export ANDROID_ABI="x86_64"
        ;;
    x86)
        export ANDROID_TRIPLE="i686-linux-android"
        export ANDROID_ABI="x86"
        ;;
    *)
        echo "ERROR: Unsupported TARGET_ARCH=$TARGET_ARCH"
        echo "  Supported: aarch64, armv7, x86_64, x86"
        exit 1
        ;;
esac

# ---------- NDK Toolchain ----------
export NDK_TOOLCHAIN="${NDK_HOME}/toolchains/llvm/prebuilt/$(uname -s | tr '[:upper:]' '[:lower:]')-$(uname -m)"
if [ ! -d "$NDK_TOOLCHAIN" ]; then
    # macOS arm64 may report as "darwin-aarch64" but NDK uses "darwin-x86_64"
    export NDK_TOOLCHAIN="${NDK_HOME}/toolchains/llvm/prebuilt/darwin-x86_64"
fi

export CC="${NDK_TOOLCHAIN}/bin/${ANDROID_TRIPLE}${ANDROID_API_LEVEL}-clang"
export CXX="${NDK_TOOLCHAIN}/bin/${ANDROID_TRIPLE}${ANDROID_API_LEVEL}-clang++"
export AR="${NDK_TOOLCHAIN}/bin/llvm-ar"
export AS="${NDK_TOOLCHAIN}/bin/llvm-as"
export LD="${NDK_TOOLCHAIN}/bin/ld"
export RANLIB="${NDK_TOOLCHAIN}/bin/llvm-ranlib"
export STRIP="${NDK_TOOLCHAIN}/bin/llvm-strip"
export NM="${NDK_TOOLCHAIN}/bin/llvm-nm"
export OBJDUMP="${NDK_TOOLCHAIN}/bin/llvm-objdump"
export READELF="${NDK_TOOLCHAIN}/bin/llvm-readelf"

# Verify toolchain exists
if [ ! -f "$CC" ]; then
    echo "ERROR: Clang not found at $CC"
    echo "  Check NDK installation and ANDROID_API_LEVEL=${ANDROID_API_LEVEL}"
    exit 1
fi

# ---------- Build directories ----------
export SAGEMATH_ANDROID_ROOT="${SAGEMATH_ANDROID_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)/sagemath-android}"
export SAGEMATH_SRC_DIR="${SAGEMATH_ANDROID_ROOT}/src"
export SAGEMATH_BUILD_DIR="${SAGEMATH_ANDROID_ROOT}/build/${ANDROID_TRIPLE}"
export SAGEMATH_PREFIX="${SAGEMATH_ANDROID_ROOT}/install/${ANDROID_TRIPLE}"

mkdir -p "$SAGEMATH_SRC_DIR" "$SAGEMATH_BUILD_DIR" "$SAGEMATH_PREFIX"/{lib,include,bin,share}

# ---------- Compiler flags ----------
export CFLAGS="-O2 -fPIC -D__ANDROID_API__=${ANDROID_API_LEVEL}"
export CXXFLAGS="-O2 -fPIC -D__ANDROID_API__=${ANDROID_API_LEVEL}"
export LDFLAGS="-L${SAGEMATH_PREFIX}/lib"
export CPPFLAGS="-I${SAGEMATH_PREFIX}/include"
export PKG_CONFIG_PATH="${SAGEMATH_PREFIX}/lib/pkgconfig"
export PKG_CONFIG_LIBDIR="${SAGEMATH_PREFIX}/lib/pkgconfig"

# ---------- Parallelism ----------
if command -v nproc &>/dev/null; then
    export NPROC=$(nproc)
elif command -v sysctl &>/dev/null; then
    export NPROC=$(sysctl -n hw.ncpu)
else
    export NPROC=4
fi

# ---------- Summary ----------
echo "============================================"
echo "SageMath Android Build Environment"
echo "============================================"
echo "  NDK:          $NDK_HOME"
echo "  API Level:    $ANDROID_API_LEVEL"
echo "  Target:       $ANDROID_TRIPLE ($ANDROID_ABI)"
echo "  CC:           $CC"
echo "  Prefix:       $SAGEMATH_PREFIX"
echo "  Parallelism:  $NPROC jobs"
echo "============================================"
