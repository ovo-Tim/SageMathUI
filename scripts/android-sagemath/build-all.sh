#!/usr/bin/env bash
# Master build script — orchestrates cross-compilation of all SageMath
# dependencies for Android.
#
# Usage:
#   ./scripts/android-sagemath/build-all.sh [--target aarch64|armv7|x86_64|x86]
#
# Build order (dependency graph):
#   GMP → MPFR → FLINT
#   GMP → PARI
#   GMP → NTL
#   Python (independent)
#   SageMath (depends on all above)
#
# Total build time: ~30-60 minutes on a modern machine
# Total output size: ~300-500 MB

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target)
            export TARGET_ARCH="$2"
            shift 2
            ;;
        --clean)
            CLEAN=1
            shift
            ;;
        --help)
            echo "Usage: $0 [--target aarch64|armv7|x86_64|x86] [--clean]"
            echo ""
            echo "Cross-compiles SageMath and all dependencies for Android."
            echo ""
            echo "Options:"
            echo "  --target ARCH  Target architecture (default: aarch64)"
            echo "  --clean        Remove build artifacts and start fresh"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

export TARGET_ARCH="${TARGET_ARCH:-aarch64}"

source "$SCRIPT_DIR/env-android.sh"

if [ "${CLEAN:-0}" = "1" ]; then
    echo "Cleaning build directories..."
    rm -rf "$SAGEMATH_BUILD_DIR" "$SAGEMATH_PREFIX"
    mkdir -p "$SAGEMATH_BUILD_DIR" "$SAGEMATH_PREFIX"/{lib,include,bin,share}
    echo "Clean complete."
fi

FAILED=()
SKIPPED=()
BUILT=()

run_build() {
    local name="$1"
    local script="$2"
    echo ""
    echo "================================================================"
    echo "  Building: ${name}"
    echo "================================================================"

    if bash "$script"; then
        BUILT+=("$name")
    else
        echo "FAILED: ${name}"
        FAILED+=("$name")
        return 1
    fi
}

START_TIME=$(date +%s)

# GMP must be first — everything depends on it
run_build "GMP 6.3.0" "$SCRIPT_DIR/build-gmp.sh"

# MPFR depends on GMP
run_build "MPFR 4.2.1" "$SCRIPT_DIR/build-mpfr.sh"

# FLINT depends on GMP + MPFR
run_build "FLINT 3.1.3" "$SCRIPT_DIR/build-flint.sh" || true

# PARI depends on GMP (FLINT failure is non-fatal)
run_build "PARI/GP 2.17.3" "$SCRIPT_DIR/build-pari.sh" || true

# NTL depends on GMP (independent of FLINT/PARI)
run_build "NTL 11.5.1" "$SCRIPT_DIR/build-ntl.sh" || true

# Python is independent of math libraries
run_build "Python 3.12.8" "$SCRIPT_DIR/build-python.sh" || true

# SageMath depends on Python + math libs
run_build "SageMath Core" "$SCRIPT_DIR/build-sagemath.sh" || true

END_TIME=$(date +%s)
ELAPSED=$((END_TIME - START_TIME))

echo ""
echo "================================================================"
echo "  Build Summary"
echo "================================================================"
echo "  Target:     ${ANDROID_TRIPLE} (${ANDROID_ABI})"
echo "  Prefix:     ${SAGEMATH_PREFIX}"
echo "  Time:       $((ELAPSED / 60))m $((ELAPSED % 60))s"
echo ""
echo "  Built:      ${BUILT[*]:-none}"
echo "  Failed:     ${FAILED[*]:-none}"
echo ""

if [ ${#FAILED[@]} -gt 0 ]; then
    echo "  Some builds failed. Check logs in: ${SAGEMATH_BUILD_DIR}/"
    echo ""
    echo "  Common fixes:"
    echo "    - GMP: Ensure NDK toolchain is correct"
    echo "    - PARI: May need manual Configure flags adjustment"
    echo "    - Python: Most complex — consider python-for-android (p4a) as alternative"
    echo "    - FLINT: Ensure CMake 3.16+ is installed"
fi

echo ""
echo "  Installed libraries:"
ls -la "${SAGEMATH_PREFIX}/lib/"*.a 2>/dev/null || echo "    (none)"
echo ""
echo "  Next steps:"
echo "    1. Bundle ${SAGEMATH_PREFIX}/ into the Android APK assets"
echo "    2. At runtime, extract to app's internal storage"
echo "    3. Set PYTHONPATH and LD_LIBRARY_PATH to the extracted location"
echo "    4. Launch sage_bridge.py via the embedded Python interpreter"
