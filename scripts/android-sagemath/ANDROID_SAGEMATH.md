# Android Python Integration Guide

## Architecture

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
│  │  Embedded Python 3.13              │  │
│  │  + sage_bridge.py                  │  │
│  │  + SymPy + mpmath                  │  │
│  └────────────────────────────────────┘  │
└─────────────────────────────────────────┘
```

The Android app embeds a cross-compiled Python 3.13 interpreter that runs
`sage_bridge.py`. Communication uses JSON over stdin/stdout (same protocol
as the desktop `LocalSageSolver`).

### APK structure

```
app.apk
├── lib/arm64-v8a/
│   ├── libsage_math_ui_lib.so    # Tauri Rust library
│   ├── libpython_exec.so         # Python 3.13 binary (renamed)
│   ├── libpython3.13.so          # Python shared library
│   └── libpython3.so             # Convenience symlink (optional)
├── assets/
│   ├── python/
│   │   └── lib/python3.13/       # Stdlib + site-packages (SymPy, mpmath)
│   ├── sage_bridge.py            # Python bridge script
│   └── tauri.conf.json
└── ...
```

### Runtime flow

1. First launch → `MainActivity.extractPythonAssets()` copies
   `assets/python/` → `/data/user/0/com.sagemath.ui/files/python/`
   and `assets/sage_bridge.py` → `.../files/sage_bridge.py`
2. Writes `.solver_config.json` with `native_lib_dir`, `files_dir`, `cache_dir`
3. `AndroidSageSolver` spawns:
   ```
   /data/app/<pkg>/lib/arm64/libpython_exec.so -u /data/.../files/sage_bridge.py
   ```
   with `PYTHONHOME`, `PYTHONPATH`, `LD_LIBRARY_PATH` environment variables
4. Python outputs `{"status": "ready", "backend": "sympy"}` on stdout
5. Rust sends JSON solve requests on stdin, reads JSON results from stdout


## Prerequisites

- macOS (Apple Silicon or Intel) or Linux x86_64
- Android SDK (API 24+) with NDK 27.x
- JDK 17
- Rust with `aarch64-linux-android` target
- Node.js + pnpm
- ~2 GB disk space


## Local Development

### Step 1: Cross-compile Python 3.13 for Android

```bash
source scripts/android-sagemath/env-android.sh

PYTHON_VERSION=3.13.3

# Download source
wget https://www.python.org/ftp/python/$PYTHON_VERSION/Python-$PYTHON_VERSION.tgz
tar xf Python-$PYTHON_VERSION.tgz
cd Python-$PYTHON_VERSION

# Build host Python (needed for --with-build-python)
mkdir -p build-host && cd build-host
../configure --prefix="$(pwd)/prefix"
make -j"$(nproc)" && make install
HOST_PYTHON="$(pwd)/prefix/bin/python3.13"
cd ..

# Cross-compile for Android aarch64
mkdir -p cross-build && cd cross-build
../configure \
  --host=aarch64-linux-android24 \
  --build=$(uname -m)-$(uname -s | tr '[:upper:]' '[:lower:]')-gnu \
  --with-build-python="$HOST_PYTHON" \
  --enable-shared \
  --without-ensurepip \
  --prefix="$(pwd)/prefix" \
  ac_cv_buggy_getaddrinfo=no \
  ac_cv_file__dev_ptmx=yes \
  ac_cv_file__dev_ptc=no
make -j"$(nproc)"
make install
```

Output: `Python-3.13.3/cross-build/prefix/` containing `bin/python3.13`,
`lib/python3.13/` (stdlib), `lib/libpython3.13.so`.

### Step 2: Bundle into Android assets

```bash
# Point to your cross-compiled prefix
export CROSS_PREFIX="path/to/Python-3.13.3/cross-build/prefix"

./scripts/bundle-android-python.sh
```

This script:
1. Copies the Python stdlib to a staging area, removing test/tkinter/idle bloat
2. Installs SymPy + mpmath via `pip install --target`
3. Patches mpmath to avoid `importlib.metadata` (unavailable on Android)
4. Strips debug symbols from `.so` files using the NDK strip tool
5. Copies Python binaries to `jniLibs/arm64-v8a/`
6. Copies the stdlib + sage_bridge.py to `assets/`

The script accepts these environment variables for customization:

| Variable | Default | Description |
|----------|---------|-------------|
| `PROJECT_ROOT` | Auto-detected from script location | Repository root |
| `CROSS_PREFIX` | `$PROJECT_ROOT/sagemath-android/src/Python-3.13.3/cross-build/.../prefix` | Cross-compiled Python install prefix |
| `NDK_STRIP` | Auto-detected from `NDK_HOME` or `ANDROID_HOME` | Path to `llvm-strip` |

### Step 3: Build and run

```bash
export ANDROID_HOME="$HOME/Library/Android/sdk"
export NDK_HOME="$ANDROID_HOME/ndk/27.0.12077973"
export JAVA_HOME="/opt/homebrew/opt/openjdk@17"

# Development
pnpm tauri android dev

# Release
pnpm tauri android build --target aarch64
```


## CI Build (GitHub Actions)

The release workflow (`.github/workflows/release.yml`) automates the entire
process:

1. **Setup**: Installs NDK 27, JDK 17, Rust, Node.js, Python 3.13 (host)
2. **Cross-compile**: Builds CPython 3.13.3 for `aarch64-linux-android24`
   using the NDK toolchain (~5-10 minutes, cached between runs)
3. **Bundle**: Runs `bundle-android-python.sh` with CI-appropriate paths
4. **Sign** (optional): If `ANDROID_KEY_BASE64` secret is set, creates a
   signed release APK using a keystore decoded from the secret
5. **Build**: `pnpm tauri android build`

### Required secrets (for signing)

| Secret | Description |
|--------|-------------|
| `ANDROID_KEY_BASE64` | Base64-encoded `.jks` keystore file |
| `ANDROID_KEY_ALIAS` | Key alias within the keystore |
| `ANDROID_KEY_PASSWORD` | Password for both keystore and key |

Generate a keystore:
```bash
keytool -genkey -v \
  -keystore release-key.jks \
  -keyalg RSA -keysize 2048 \
  -validity 10000 \
  -alias my-key-alias

# Base64-encode for GitHub secret
base64 -i release-key.jks | tr -d '\n'
```

### Cache

The cross-compiled Python prefix is cached with key
`android-python-3.13.3-aarch64-ndk27-<hash of bundle script>`.
The cache invalidates when `bundle-android-python.sh` changes.


## Troubleshooting

### "Skipping asset: python" in logcat

The `assets/python/` directory is missing from the APK. Run
`bundle-android-python.sh` before building, or check that the
cross-compiled prefix has `lib/python3.13/` and `bin/python3.13`.

### Python starts but no "ready" signal

Check `adb logcat -s python-stderr` for import errors. Common causes:
- Missing SymPy in site-packages (re-run bundle script)
- Wrong Python version in stdlib path (must be 3.13)
- Corrupted extraction — clear app data and relaunch

### SIGALRM not available on Android

`sage_bridge.py` uses `signal.alarm()` for computation timeouts, which is
unreliable on Android's bionic libc. The `AndroidSageSolver` handles
timeouts on the Rust side with a 30-second tokio timeout instead.

### Slow on emulator

ARM binaries run through translation on x86_64 emulators. SymPy import
alone takes ~1s on native ARM but can take 30+ seconds under translation.
Test on a real device when possible.


## File Reference

```
scripts/
├── bundle-android-python.sh       # Packages cross-compiled Python for APK
└── android-sagemath/
    ├── ANDROID_SAGEMATH.md        # This document
    ├── env-android.sh             # NDK environment variables
    ├── build-all.sh               # Full SageMath stack cross-compilation
    ├── build-python.sh            # CPython cross-compilation (3.12, legacy)
    ├── build-gmp.sh               # GMP 6.3.0
    ├── build-mpfr.sh              # MPFR 4.2.1
    ├── build-flint.sh             # FLINT 3.1.3
    ├── build-pari.sh              # PARI/GP 2.17.3
    ├── build-ntl.sh               # NTL 11.5.1
    └── build-sagemath.sh          # SageMath Python packages

src-tauri/
├── sage_bridge.py                 # Python bridge (SymPy/SageMath → JSON)
├── src/solver/
│   ├── android.rs                 # AndroidSageSolver (spawns Python)
│   ├── local.rs                   # LocalSageSolver (desktop variant)
│   ├── traits.rs                  # Solver trait
│   ├── types.rs                   # Shared types
│   └── mod.rs                     # cfg-gated module routing
└── gen/android/
    └── app/src/main/
        ├── java/.../MainActivity.kt   # Asset extraction on first launch
        ├── assets/python/             # Bundled Python stdlib (generated)
        └── jniLibs/arm64-v8a/         # Python .so binaries (generated)
```
