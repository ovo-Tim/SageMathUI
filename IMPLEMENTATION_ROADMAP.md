# SageMath on Android: Implementation Roadmap

## Quick Decision Tree

### What do you want?
- **Basic symbolic math + numerical computation** → **Option A (Lightweight)** - Start here
- **Real computer algebra system** → **Option B (Maxima)** - Best balanced
- **Full SageMath** → **Option C (Full)** - 6-12 month project

---

## PHASE 1: Lightweight (Option A) - 2-3 WEEKS

### Goal
Embed Termux bootstrap + Python + SymPy/NumPy/SciPy in Tauri APK

### Dependencies to Obtain
```bash
# From Termux releases (latest)
https://github.com/termux/termux-packages/releases/download/bootstrap-2026.03.08-r1+apt.android-7/bootstrap-aarch64.zip

# Size: 30.7 MB (will be ~15 MB after zipping within APK)
```

### Implementation Steps

#### 1. Create NDK Wrapper (C/JNI)
```c
// jni/bootstrap.c
#include <jni.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <zip.h>

// External symbols from assembly file
extern char blob[];
extern int blob_size;

// JNI function to extract bootstrap
JNIEXPORT void JNICALL
Java_com_example_sagemath_BootstrapManager_extractBootstrap(
    JNIEnv *env, jobject obj, jstring prefix_path) {
    
    const char *prefix = (*env)->GetStringUTFChars(env, prefix_path, NULL);
    
    // Create zip from memory blob
    FILE *tmp = fopen("/tmp/bootstrap.zip", "wb");
    fwrite(blob, 1, blob_size, tmp);
    fclose(tmp);
    
    // Extract using unzip library or similar
    // unzip -q /tmp/bootstrap.zip -d {prefix}
    
    (*env)->ReleaseStringUTFChars(env, prefix_path, prefix);
}
```

#### 2. Add Assembly File
```asm
# jni/bootstrap_blob.S
.section .rodata
.global blob_start
.global blob_end

blob_start:
.incbin "bootstrap-aarch64.zip"
blob_end:

.global blob
.global blob_size

blob = blob_start
blob_size = blob_end - blob_start
```

#### 3. Kotlin/Tauri Bridge
```kotlin
// In your Tauri Android module
fun extractBootstrap(appCacheDir: File) {
    val prefixDir = File(appCacheDir, "termux_prefix")
    prefixDir.mkdirs()
    
    // Call JNI
    BootstrapManager.extractBootstrap(prefixDir.absolutePath)
    
    // Verify
    val pythonBin = File(prefixDir, "bin/python3")
    if (pythonBin.exists()) {
        println("✓ Bootstrap extracted successfully")
    }
}
```

#### 4. Subprocess Integration
```kotlin
// Launch Python subprocess with SymPy
fun runPythonMath(expression: String): String {
    val process = ProcessBuilder(
        "${prefixDir}/bin/python3",
        "-c",
        "from sympy import *; print(eval('$expression'))"
    ).start()
    
    return process.inputStream.bufferedReader().readText()
}
```

#### 5. Web UI Integration (Tauri)
```javascript
// src-tauri/src/main.rs
#[tauri::command]
async fn compute_math(expr: String) -> Result<String, String> {
    // Call Kotlin bridge
    invoke_compute(expr).await
}
```

### Python Packages to Include
```bash
# In Termux build:
pip install sympy numpy scipy matplotlib ipython

# Total size: ~150-200 MB (APK will be ~75-100 MB compressed)
```

### Testing Checklist
- [ ] Bootstrap extracts to `$APP_CACHE/termux_prefix`
- [ ] `python3 --version` works from subprocess
- [ ] `python3 -c "from sympy import *; print(solve(x**2 - 1))"` works
- [ ] Web UI can call Python and display results
- [ ] APK size < 120 MB

---

## PHASE 2: Medium (Option B) - +1 WEEK

### Add Maxima Support

#### 1. Verify Maxima in Bootstrap
Termux already has `maxima` package. Check if it's in your bootstrap.

```bash
# In your extracted prefix:
bin/maxima --version
```

#### 2. Subprocess Interface
```kotlin
fun runMaxima(command: String): String {
    val process = ProcessBuilder(
        "${prefixDir}/bin/maxima",
        "-b", "-",  // Batch mode
    ).start()
    
    process.outputStream.write("$command;".toByteArray())
    process.outputStream.close()
    
    return process.inputStream.bufferedReader().readText()
}
```

#### 3. Web UI Integration
```javascript
// Switch between engines
switch(engineType) {
    case 'sympy':
        return await invoke('compute_math', {expr});
    case 'maxima':
        return await invoke('compute_maxima', {expr});
}
```

### Testing
- [ ] `maxima --version` works
- [ ] Basic Maxima commands execute
- [ ] Results parse correctly
- [ ] Web UI switches between engines

---

## PHASE 3: Full SageMath (Option C) - 6-12 MONTHS

### ⚠️ HIGH EFFORT - Only if Phase A/B insufficient

#### Prerequisites
1. **Clone Termux packages**:
   ```bash
   git clone https://github.com/termux/termux-packages.git
   # Read: https://github.com/termux/termux-packages/wiki/Building-packages
   ```

2. **Obtain Android NDK**: Download r26 or later

3. **Set up cross-compilation environment**

#### Build Steps (Simplified)
```bash
# 1. Create custom SageMath package in Termux
packages/sagemath/build.sh:
TERMUX_PKG_HOMEPAGE="https://sagemath.org/"
TERMUX_PKG_DESCRIPTION="Open-source computer algebra system"
TERMUX_PKG_LICENSE="GPL-3.0"
TERMUX_PKG_VERSION="10.3"
TERMUX_PKG_SRCURL="https://github.com/sagemath/sage/releases/download/..."
TERMUX_PKG_DEPENDS="python, boost, maxima, maxima, gmp, mpfr, ..."

# 2. Handle gfortran absence (patch SageMath build):
# - Disable LAPACK fortran components
# - Use netlib-LAPACK (pure C) instead
# - Skip Fortran-dependent plotting libraries

# 3. Build for aarch64
./build-package.sh sagemath aarch64

# 4. Create bootstrap with custom package name
# (This is the bottleneck - requires rebuilding ALL packages)
```

#### Critical Blockers
- **gfortran missing**: You must either:
  - Port gfortran to Android (months of work)
  - Patch SageMath to disable Fortran deps
  - Use PRoot approach instead

- **Custom package name**: If you're not using `com.termux`, you must rebuild:
  - Python (paths hardcoded)
  - All 100+ dependencies
  - Bootstrap zip from scratch

#### Effort Breakdown
- gfortran port or patch: 2-3 months
- SageMath patches: 1 month
- Building and testing: 2 months
- Integration: 1-2 months
- **Total**: 6-12 months (non-trivial)

---

## AVOID: Full SageMath Unless...

### When Full SageMath is Worth It
- [ ] Your app is specifically marketed as "SageMath for Android"
- [ ] You have a team of 2+ developers
- [ ] You have 6+ months timeline
- [ ] Users explicitly need full SageMath features
- [ ] Willing to maintain build system for SageMath updates

### When Phase A/B is Better
- [ ] You need symbolic math + numeric computation
- [ ] SymPy + Maxima cover your use cases
- [ ] Want to ship in 3-4 weeks
- [ ] APK size matters (<150 MB target)
- [ ] Single developer project

---

## Resource Files

### Download These Now
```bash
# Bootstrap (choose your target arch)
wget https://github.com/termux/termux-packages/releases/download/bootstrap-2026.03.08-r1+apt.android-7/bootstrap-aarch64.zip

# Reference implementations
git clone https://github.com/termux/termux-app
# Study: app/src/main/java/com/termux/app/TermuxInstaller.java
# Study: app/src/main/cpp/termux-bootstrap-zip.S

# Python patches for Android
git clone https://github.com/termux/termux-packages
# Reference: packages/python/build.sh
# Reference: All patches in packages/python/*.patch
```

### Key Permalinks
- Bootstrap assembly: https://github.com/termux/termux-app/blob/master/app/src/main/cpp/termux-bootstrap-zip.S
- Bootstrap extraction: https://github.com/termux/termux-app/blob/master/app/src/main/java/com/termux/app/TermuxInstaller.java
- SageMath request: https://github.com/termux/termux-packages/issues/450
- Build wiki: https://github.com/termux/termux-packages/wiki/Building-packages

---

## Testing Strategy

### Phase A (Lightweight) Testing
```bash
# 1. Extract bootstrap manually
unzip bootstrap-aarch64.zip -d /tmp/test_prefix

# 2. Verify core tools
/tmp/test_prefix/bin/python3 --version
/tmp/test_prefix/bin/python3 -c "import numpy; print(numpy.__version__)"
/tmp/test_prefix/bin/python3 -c "from sympy import *; print(solve(x**2-4))"

# 3. Verify size
du -sh /tmp/test_prefix  # Should be ~150-200 MB

# 4. Deploy to Tauri Android
# Follow steps above for JNI/Kotlin integration
```

### Phase B (Maxima) Testing
```bash
# Verify Maxima
/tmp/test_prefix/bin/maxima --version

# Test command
echo "solve(x^2 + 3*x + 2)" | /tmp/test_prefix/bin/maxima -b -
```

---

## Next Steps

1. **Today**: Review TERMUX_ANALYSIS.md (full technical details)
2. **Day 1-2**: Set up Tauri Android project with Phase A structure
3. **Day 3-5**: Implement JNI bootstrap extraction + test
4. **Day 6-10**: Integrate Python subprocess + SymPy math
5. **Day 11-14**: Build web UI and connect to backend
6. **Day 15+**: Polish, add Maxima (Phase B), deploy

**Estimated Phase A completion**: 2-3 weeks solo developer

---

## Questions to Ask Yourself

- Do you need *full* SageMath or just symbolic math?
- What's your target APK size?
- How many developers are available?
- What's your timeline?
- Is offline computation required?

**If**: Full SageMath + unlimited time + team → **Phase C**  
**Else if**: Real CAS + balanced scope → **Phase B**  
**Else**: Fast MVP + symbolic math → **Phase A** ← **START HERE**

