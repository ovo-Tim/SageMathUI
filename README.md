# SageMath UI (sage-math-ui) v0.1.0

A PhotoMath-like math solver powered by SageMath.

This project uses Tauri 2 (Rust backend), Vue 3, TypeScript, MathLive, KaTeX, and Python (SageMath/SymPy).

## Prerequisites

Before starting the desktop or Android builds, ensure your environment meets these requirements:

- Node.js (LTS)
- pnpm
- Rust (latest stable)
- Python 3.12+ with SymPy and mpmath
- Platform-specific Tauri v2 prerequisites. See the [Tauri v2 documentation](https://v2.tauri.app/start/prerequisites/) for setup instructions.

## Desktop Build

### Development

To start the development server and open the Tauri window:

```bash
pnpm install
pnpm tauri dev
```

The development server runs at http://localhost:1420. The application window opens automatically.

### Production

To generate a production build:

```bash
pnpm tauri build
```

The compiled assets and installer are located in `src-tauri/target/release/bundle/`.

## Android Build

Building for Android is a multi-step process that involves cross-compiling the SageMath stack for the aarch64-linux-android target.

### Requirements

- Android SDK (API 24+) and NDK 27.x
- JDK 17
- CMake 3.16+
- Approximately 5GB of available disk space
- Rust `aarch64-linux-android` target installed via rustup

### Build Process Summary

1. Cross-compile essential C libraries (GMP, MPFR, FLINT, PARI, NTL) using the scripts in `scripts/android-sagemath/`.
2. Cross-compile Python 3.12 for the Android target.
3. Install SageMath Python packages into the cross-compilation prefix.
4. Bundle the resulting environment into the APK assets.
5. Generate the APK:

```bash
pnpm tauri android build --target aarch64
```

For a detailed step-by-step walkthrough, refer to `scripts/android-sagemath/ANDROID_SAGEMATH.md`.

## Project Structure

- `src/`: Vue 3 frontend components and logic.
- `src-tauri/`: Tauri and Rust backend implementation.
  - `src/solver/`: SageMath solver logic.
  - `sage_bridge.py`: Python computation bridge for inter-process communication.
- `scripts/android-sagemath/`: Scripts and documentation for Android cross-compilation.

## License

MIT
