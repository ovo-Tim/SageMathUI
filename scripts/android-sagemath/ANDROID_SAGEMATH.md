# SageMath Android Integration Guide

## Architecture Overview

```
┌─────────────────────────────────────────┐
│              Android APK                │
│  ┌────────────┐  ┌──────────────────┐   │
│  │  Tauri      │  │  WebView (Vue3)  │   │
│  │  Rust Core  │  │  MathLive+KaTeX  │   │
│  │             │  └──────────────────┘   │
│  │  AndroidSage│                         │
│  │  Solver     │──── stdin/stdout ────┐  │
│  └────────────┘                       │  │
│                                       ▼  │
│  ┌────────────────────────────────────┐  │
│  │  Embedded Python 3.12              │  │
│  │  + sage_bridge.py                  │  │
│  │  + SymPy/mpmath                    │  │
│  │  + SageMath pure-Python core       │  │
│  │  + libgmp/mpfr/flint/pari/ntl.a    │  │
│  └────────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

## Build Pipeline

### Prerequisites

- macOS or Linux host
- Android SDK (API 24+), NDK 27.x
- JDK 17
- Rust + `aarch64-linux-android` target
- CMake 3.16+
- ~5 GB disk space for build artifacts

### Step 1: Cross-Compile C Libraries

```bash
# Set environment
source scripts/android-sagemath/env-android.sh

# Build all dependencies (or individually)
./scripts/android-sagemath/build-all.sh --target aarch64

# Individual builds if needed:
# ./scripts/android-sagemath/build-gmp.sh
# ./scripts/android-sagemath/build-mpfr.sh
# ./scripts/android-sagemath/build-flint.sh
# ./scripts/android-sagemath/build-pari.sh
# ./scripts/android-sagemath/build-ntl.sh
```

Output: `sagemath-android/install/aarch64-linux-android/{lib,include}/`

### Step 2: Cross-Compile Python

```bash
./scripts/android-sagemath/build-python.sh
```

This builds a host Python for bootstrapping, then cross-compiles CPython 3.12 for Android.

Output: `sagemath-android/install/aarch64-linux-android/lib/python3.12/`

### Step 3: Install SageMath Python Packages

```bash
./scripts/android-sagemath/build-sagemath.sh
```

Installs SymPy, mpmath, and SageMath's pure-Python modules into the cross-prefix.

### Step 4: Bundle into APK

The cross-compiled files must be included in the Android APK as assets and extracted at first launch.

#### 4a. Create the asset bundle

```bash
cd sagemath-android/install/aarch64-linux-android
tar czf ../sagemath-bundle.tar.gz \
  lib/libpython3.12.a \
  lib/python3.12/ \
  bin/python3 \
  lib/libgmp.a lib/libmpfr.a lib/libflint.a lib/libpari.a lib/libntl.a
```

#### 4b. Add to Android assets

```bash
mkdir -p src-tauri/gen/android/app/src/main/assets
cp sagemath-android/install/sagemath-bundle.tar.gz \
   src-tauri/gen/android/app/src/main/assets/

# Also bundle sage_bridge.py
cp src-tauri/sage_bridge.py \
   src-tauri/gen/android/app/src/main/assets/
```

#### 4c. First-launch extraction (Kotlin)

Add to `MainActivity.kt`:

```kotlin
private fun extractSageMathBundle() {
    val targetDir = File(filesDir, "python")
    if (targetDir.exists()) return  // Already extracted

    val bundleStream = assets.open("sagemath-bundle.tar.gz")
    // Extract tar.gz to targetDir
    // Also copy sage_bridge.py to filesDir
}
```

### Step 5: Build the APK

```bash
export ANDROID_HOME="$HOME/Library/Android/sdk"
export NDK_HOME="$ANDROID_HOME/ndk/27.0.12077973"
export JAVA_HOME="/opt/homebrew/opt/openjdk@17"

pnpm tauri android build --target aarch64
```

## Runtime Flow

1. App launches → `MainActivity.extractSageMathBundle()` runs on first start
2. Bundle extracts to `/data/data/com.sagemath.ui/files/python/`
3. `sage_bridge.py` copied to `/data/data/com.sagemath.ui/files/`
4. Rust `AndroidSageSolver` spawns `/data/data/com.sagemath.ui/files/python/bin/python3 sage_bridge.py`
5. JSON IPC over stdin/stdout (same protocol as desktop `LocalSageSolver`)

## Known Issues & Workarounds

### SIGALRM not available on Android
`sage_bridge.py` uses `signal.alarm()` for computation timeouts. Android's bionic libc doesn't support `SIGALRM` reliably. The `AndroidSageSolver` handles timeouts on the Rust side (30s tokio timeout) instead.

**Fix**: Modify `sage_bridge.py` to skip `signal.alarm()` when `sys.platform == 'linux'` and `/system/build.prop` exists (Android detection).

### Cython Extensions
SageMath's performance-critical C extensions (cysignals, sage.rings.*, sage.libs.*) require Cython cross-compilation, which is significantly more complex than pure-Python installation. The current setup runs in "degraded mode" using SymPy + mpmath for computation.

**Future work**: Use `crossenv` or `python-for-android` recipes to build Cython extensions.

### APK Size
Full SageMath bundle with Python + all libraries: ~400-500 MB. Consider:
- Stripping debug symbols: `$STRIP --strip-unneeded *.so`
- Compressing assets (they're already gzipped)
- Using Android App Bundle (AAB) for Play Store delivery
- On-demand download of SageMath bundle after install

### China Network Issues
Build scripts use mirror URLs for downloads:
- GMP/MPFR: `mirrors.tuna.tsinghua.edu.cn` (TUNA)
- Python: `mirrors.huaweicloud.com`
- Gradle: `mirrors.cloud.tencent.com`
- Maven: Alibaba mirrors (already configured in `build.gradle.kts`)

## File Reference

```
scripts/android-sagemath/
├── env-android.sh          # Environment setup (source this first)
├── build-all.sh            # Master orchestrator
├── build-gmp.sh            # GMP 6.3.0
├── build-mpfr.sh           # MPFR 4.2.1
├── build-flint.sh          # FLINT 3.1.3
├── build-pari.sh           # PARI/GP 2.17.3
├── build-ntl.sh            # NTL 11.5.1
├── build-python.sh         # CPython 3.12.8
└── build-sagemath.sh       # SageMath Python packages

src-tauri/src/solver/
├── android.rs              # AndroidSageSolver (mobile)
├── local.rs                # LocalSageSolver (desktop)
├── subprocess.rs           # SubprocessSolver (backup)
├── traits.rs               # Solver trait definition
├── types.rs                # Shared types
└── mod.rs                  # Conditional compilation routing
```

## Dependency Graph

```
GMP 6.3.0 ──┬──► MPFR 4.2.1 ──► FLINT 3.1.3
             ├──► PARI/GP 2.17.3
             └──► NTL 11.5.1

Python 3.12.8 ──► SymPy 1.13.3
                  mpmath 1.3.0
                  SageMath pure-Python core
```
