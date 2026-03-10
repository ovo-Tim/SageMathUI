# Android Build Guide for SageMath UI

This guide explains how to build the SageMath UI app for Android with embedded Termux bootstrap.

## Overview

The project uses Tauri to compile to Android, with additional NDK integration for extracting an embedded Termux environment containing Python and math libraries.

### Architecture

- **Frontend**: Vue.js + TypeScript (Tauri WebView)
- **Backend**: Rust (Tauri command handler) → Python subprocess (sage_bridge.py)
- **Native Layer**: JNI (Java Native Interface) for bootstrap extraction

### Build Chain

```
Source Code
    ↓
Rust Compilation (src-tauri/src/)
    ↓
NDK Compilation (C JNI + Assembly)
    ↓
Gradle Build (Android app assembly)
    ↓
APK Assembly + Signing
    ↓
Final APK (installable on Android)
```

## Prerequisites

### 1. Install Android Development Tools

```bash
# Install Android SDK/NDK (if not already installed)
brew install --cask android-sdk
brew install --cask android-ndk

# Add to your shell profile (~/.zshrc or ~/.bash_profile):
export ANDROID_HOME=$HOME/Library/Android/sdk
export NDK_HOME=$ANDROID_HOME/ndk/25.2.9519653  # or latest version
export PATH=$PATH:$ANDROID_HOME/tools:$ANDROID_HOME/platform-tools
```

### 2. Install Tauri CLI

```bash
cargo install tauri-cli
```

### 3. Install Node Dependencies

```bash
cd /Users/tim/my_project/SageMathUI
pnpm install
```

## Build Steps

### Step 1: Download Termux Bootstrap

The Termux bootstrap (aarch64 architecture) must be downloaded and embedded in the APK.

```bash
# Create bootstrap directory
mkdir -p /Users/tim/my_project/SageMathUI/src-tauri/gen/android/app/src/main/cpp

# Download latest bootstrap (30.7 MB)
# From: https://github.com/termux/termux-packages/releases/download/bootstrap-2026.03.08-r1/bootstrap-aarch64.zip
curl -L -o /Users/tim/my_project/SageMathUI/src-tauri/gen/android/app/src/main/cpp/bootstrap-aarch64.zip \
  https://github.com/termux/termux-packages/releases/download/bootstrap-2026.03.08-r1/bootstrap-aarch64.zip

# Verify size (~30.7 MB)
ls -lh /Users/tim/my_project/SageMathUI/src-tauri/gen/android/app/src/main/cpp/bootstrap-aarch64.zip
```

**Note**: The bootstrap includes:
- Python 3.13.12 (with 13 Android patches)
- NumPy, SciPy, SymPy
- Basic shells and utilities
- **Missing**: gfortran, full SageMath

### Step 2: Configure NDK Paths

Update environment variables for Android build:

```bash
export ANDROID_HOME=$HOME/Library/Android/sdk
export NDK_HOME=$ANDROID_HOME/ndk/25.2.9519653
export CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER=$NDK_HOME/toolchains/llvm/prebuilt/darwin-x86_64/bin/aarch64-linux-android-clang
```

### Step 3: Add Android Targets to Rust

```bash
rustup target add aarch64-linux-android
```

### Step 4: Build APK with Tauri

```bash
cd /Users/tim/my_project/SageMathUI

# Development build (unoptimized, smaller download)
cargo tauri android dev

# Release build (optimized, larger APK)
cargo tauri android build --release
```

**Expected Output**:
```
Compiling sage-math-ui v0.1.0
...
APK successfully built:
src-tauri/gen/android/app/build/outputs/apk/release/sage-ui-0.1.0-release.apk
```

### Step 5: Install on Device/Emulator

```bash
# Install APK
adb install -r src-tauri/gen/android/app/build/outputs/apk/release/sage-ui-0.1.0-release.apk

# Launch app
adb shell am start -n com.sagemath.ui/.MainActivity

# View logs
adb logcat | grep "SageMath\|Bootstrap\|Python"
```

## Troubleshooting

### Issue: "Bootstrap extraction failed"

**Cause**: bootstrap-aarch64.zip not found during compilation

**Solution**:
```bash
# Verify file exists
ls -lh src-tauri/gen/android/app/src/main/cpp/bootstrap-aarch64.zip

# If missing, download it:
curl -L -o src-tauri/gen/android/app/src/main/cpp/bootstrap-aarch64.zip \
  https://github.com/termux/termux-packages/releases/download/bootstrap-2026.03.08-r1/bootstrap-aarch64.zip
```

### Issue: "NDK not found"

**Solution**:
```bash
# Install NDK
sdkmanager "ndk;25.2.9519653"

# Set environment:
export NDK_HOME=$ANDROID_HOME/ndk/25.2.9519653
```

### Issue: APK size too large (>200 MB)

**Solution**: Current APK includes Python + NumPy. To reduce:
- Use SymPy only (no NumPy): ~100 MB APK
- Compress bootstrap with `–Zmax` in zip

### Issue: "No space left on device" during extraction

The Termux bootstrap requires ~150-200 MB of free space on device. For devices with limited space:

1. **Option A**: Extract to SD card instead of internal storage
   - Modify Bootstrap.kt to use `context.getExternalFilesDir()`
   
2. **Option B**: Use SymPy-only fallback
   - See `FALLBACK_SYMPYONLY.md` for lightweight build

## APK Contents and Size Breakdown

```
sage-ui-0.1.0-release.apk (estimated 170-200 MB)
├── Native Libraries (arm64-v8a)
│   ├── libsage_bootstrap.so (JNI extraction library)
│   └── libc++_shared.so (C++ runtime)
├── DEX (Compiled Java bytecode)
│   ├── Kotlin runtime
│   └── Android libraries
├── Assets (Web frontend)
│   ├── HTML/CSS/JavaScript
│   └── Math notation fonts (KaTeX)
├── Resources (Icons, strings)
├── bootstrap-aarch64.zip (embedded, 30.7 MB)
└── Metadata (manifest, config)
```

## Environment Setup at Runtime

When app launches:

1. **MainActivity** → Calls `Bootstrap.extractBootstrap(context)`
2. **Bootstrap.extractBootstrap()** → JNI call to `extractBootstrapNative()`
3. **JNI handler** → Extracts `bootstrap-aarch64.zip` to `$APP_FILES/termux_prefix/`
4. **Tauri command** → Initializes Python subprocess at `$TERMUX_PREFIX/bin/python3`
5. **sage_bridge.py** → JSON stdin/stdout loop, waits for math expressions

**Environment variables set**:
```bash
PREFIX=$APP_FILES/termux_prefix
PATH=$PREFIX/bin:$PATH
LD_LIBRARY_PATH=$PREFIX/lib:$LD_LIBRARY_PATH
HOME=$APP_CACHE
TMPDIR=$APP_CACHE/tmp
```

## Next Steps

After successful APK build:

1. **Test on Device**: Verify math computations work
2. **Benchmark Performance**: Time math operations (target <2s per request)
3. **Add Features**:
   - Maxima for symbolic computation (add +1 week)
   - Gnuplot for graphing (add +1 week)
4. **Submit to Play Store**: Configure signing key and metadata

## References

- [Tauri Android Documentation](https://tauri.app/develop/platforms/android/)
- [Android NDK Build System](https://developer.android.com/ndk/guides/cmake)
- [Termux Bootstrap Format](https://github.com/termux/termux-packages/wiki/Building-packages)
- [JNI Programming Guide](https://docs.oracle.com/en/java/javase/21/docs/specs/jni/design.html)

