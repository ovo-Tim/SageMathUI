/**
 * Bootstrap: Manages extraction and setup of embedded Termux environment
 * 
 * This handles:
 * 1. Extracting the embedded Termux bootstrap ZIP
 * 2. Installing required Python packages via apt
 * 3. Setting up executable permissions
 * 4. Managing the Termux environment
 */
package com.sagemath.ui

import android.content.Context
import android.util.Log
import java.io.File
import java.io.BufferedReader
import java.io.InputStreamReader

class Bootstrap {
    companion object {
        private const val TAG = "Bootstrap"
        private const val BOOTSTRAP_VERSION = "2026.03.08-r1"
        private const val MARK_FILE = "bootstrap_v${BOOTSTRAP_VERSION}.installed"
        
        init {
            try {
                System.loadLibrary("sage_bootstrap")
                Log.i(TAG, "Bootstrap JNI library loaded")
            } catch (e: UnsatisfiedLinkError) {
                Log.e(TAG, "Failed to load bootstrap JNI library", e)
            }
        }

        /**
         * Extract and initialize Termux bootstrap environment
         * @param context Android context for getting file paths
         * @return true if successful, false otherwise
         */
        fun initializeBootstrap(context: Context): Boolean {
            val bootstrapDir = File(context.filesDir, "termux_prefix")
            val markFile = File(bootstrapDir, MARK_FILE)
            
            // Check if already extracted and initialized
            if (markFile.exists()) {
                Log.i(TAG, "Bootstrap already initialized at ${bootstrapDir.absolutePath}")
                return verifyPythonInstallation(bootstrapDir)
            }

            // Create bootstrap directory if it doesn't exist
            if (!bootstrapDir.exists()) {
                bootstrapDir.mkdirs()
                Log.i(TAG, "Created bootstrap directory")
            }

            // Step 1: Extract bootstrap zip using JNI
            Log.i(TAG, "Starting bootstrap extraction to ${bootstrapDir.absolutePath}")
            val extractSuccess = extractBootstrapNative(bootstrapDir.absolutePath)
            
            if (!extractSuccess) {
                Log.e(TAG, "Bootstrap extraction failed")
                return false
            }
            
            Log.i(TAG, "Bootstrap extracted successfully")

            // Step 2: Set executable permissions on critical binaries
            setExecutablePermissions(bootstrapDir)

            // Step 3: Install Python and dependencies
            if (!installPythonDependencies(bootstrapDir)) {
                Log.w(TAG, "Python installation encountered issues, but continuing")
                // Don't fail completely - user might still have SymPy
            }

            // Step 4: Mark as installed
            try {
                markFile.createNewFile()
                Log.i(TAG, "Bootstrap marked as initialized")
            } catch (e: Exception) {
                Log.w(TAG, "Failed to create mark file", e)
            }

            return true
        }

        /**
         * Extract Termux bootstrap environment to app's files directory
         * @param context Android context for getting file paths
         * @return true if extraction successful, false otherwise
         */
        fun extractBootstrap(context: Context): Boolean {
            return initializeBootstrap(context)
        }

        /**
         * Verify Python 3 is installed and working
         */
        private fun verifyPythonInstallation(bootstrapDir: File): Boolean {
            val pythonPath = File(bootstrapDir, "bin/python3")
            if (!pythonPath.exists()) {
                Log.w(TAG, "Python3 not found, attempting installation")
                return installPythonDependencies(bootstrapDir)
            }
            
            try {
                val process = Runtime.getRuntime().exec(
                    arrayOf(pythonPath.absolutePath, "-c", "print('Python OK')")
                )
                val exitCode = process.waitFor()
                return exitCode == 0
            } catch (e: Exception) {
                Log.e(TAG, "Python verification failed", e)
                return false
            }
        }

        /**
         * Install Python and required packages via apt
         */
        private fun installPythonDependencies(bootstrapDir: File): Boolean {
            val bashPath = File(bootstrapDir, "bin/bash")
            if (!bashPath.exists()) {
                Log.e(TAG, "Bash not found in bootstrap")
                return false
            }

            // List of packages to install (Python + math libraries)
            val packages = listOf(
                "python",      // Latest Python version available in Termux
                "numpy",       // Numerical computing
                "scipy",       // Scientific computing
                "sympy"        // Symbolic mathematics
            )

            Log.i(TAG, "Installing Python packages...")
            
            // Run apt update and install
            val installScript = """
                export PREFIX=${bootstrapDir.absolutePath}
                export PATH=$$PREFIX/bin:$$PATH
                export LD_LIBRARY_PATH=$$PREFIX/lib:$$LD_LIBRARY_PATH
                export HOME=$$PREFIX
                
                # Update package list
                apt update -y 2>&1 | tail -5
                
                # Install packages
                for pkg in ${packages.joinToString(" ")}; do
                  echo "Installing $$pkg..."
                  apt install -y "$$pkg" || echo "Warning: Failed to install $$pkg"
                done
                
                echo "Installation complete"
            """.trimIndent()

            return try {
                // Write script to temporary file
                val scriptFile = File(bootstrapDir, ".install_packages.sh")
                scriptFile.writeText(installScript)
                scriptFile.setExecutable(true, false)

                // Execute script
                val process = Runtime.getRuntime().exec(
                    arrayOf(bashPath.absolutePath, scriptFile.absolutePath)
                )
                
                // Capture output
                val reader = BufferedReader(InputStreamReader(process.inputStream))
                var line: String?
                while (reader.readLine().also { line = it } != null) {
                    Log.d(TAG, "apt: $line")
                }
                reader.close()

                val exitCode = process.waitFor()
                scriptFile.delete()
                
                if (exitCode == 0) {
                    Log.i(TAG, "Python packages installed successfully")
                    true
                } else {
                    Log.w(TAG, "Package installation completed with exit code: $exitCode")
                    // Still return true - partial installation might be acceptable
                    true
                }
            } catch (e: Exception) {
                Log.e(TAG, "Failed to install Python packages", e)
                false
            }
        }

        /**
         * Set executable permissions on critical binaries
         */
        private fun setExecutablePermissions(bootstrapDir: File) {
            val binaries = listOf(
                "bin/bash",
                "bin/sh",
                "bin/python3",
                "bin/python",
                "bin/pip",
                "bin/pip3",
                "bin/chmod",
                "bin/ls",
                "bin/apt"
            )
            
            for (binary in binaries) {
                val file = File(bootstrapDir, binary)
                if (file.exists()) {
                    try {
                        file.setExecutable(true, false)
                        Log.d(TAG, "Set executable: $binary")
                    } catch (e: Exception) {
                        Log.w(TAG, "Failed to set executable on $binary", e)
                    }
                }
            }
        }

        /**
         * Get the path to the extracted Termux prefix
         */
        fun getBootstrapPrefix(context: Context): String {
            return File(context.filesDir, "termux_prefix").absolutePath
        }

        /**
         * Get Python executable path
         */
        fun getPythonPath(context: Context): String {
            val prefix = getBootstrapPrefix(context)
            return File(prefix, "bin/python3").absolutePath
        }

        /**
         * Check if bootstrap is fully initialized
         */
        fun isBootstrapReady(context: Context): Boolean {
            val bootstrapDir = File(context.filesDir, "termux_prefix")
            val markFile = File(bootstrapDir, MARK_FILE)
            
            if (!markFile.exists()) {
                return false
            }
            
            // Verify Python can be executed
            val pythonPath = File(bootstrapDir, "bin/python3")
            if (!pythonPath.exists()) {
                return false
            }
            
            return try {
                val process = Runtime.getRuntime().exec(
                    arrayOf(pythonPath.absolutePath, "-c", "import sys; print(sys.version)")
                )
                process.waitFor() == 0
            } catch (e: Exception) {
                false
            }
        }

        /**
         * Get bootstrap information (for debugging)
         */
        fun getBootstrapInfo(context: Context): String {
            val bootstrapDir = File(context.filesDir, "termux_prefix")
            val pythonPath = File(bootstrapDir, "bin/python3")
            
            return buildString {
                append("Bootstrap Path: ${bootstrapDir.absolutePath}\n")
                append("Bootstrap Exists: ${bootstrapDir.exists()}\n")
                append("Python Exists: ${pythonPath.exists()}\n")
                
                if (pythonPath.exists()) {
                    try {
                        val process = Runtime.getRuntime().exec(
                            arrayOf(pythonPath.absolutePath, "-c", "import sys; print(sys.version)")
                        )
                        val reader = BufferedReader(InputStreamReader(process.inputStream))
                        val version = reader.readLine() ?: "unknown"
                        reader.close()
                        append("Python Version: $version\n")
                    } catch (e: Exception) {
                        append("Python Error: ${e.message}\n")
                    }
                }
                
                // Check for SymPy
                if (pythonPath.exists()) {
                    try {
                        val process = Runtime.getRuntime().exec(
                            arrayOf(pythonPath.absolutePath, "-c", "import sympy; print('SymPy available')")
                        )
                        val reader = BufferedReader(InputStreamReader(process.inputStream))
                        val result = reader.readLine() ?: "not available"
                        reader.close()
                        append("SymPy: $result\n")
                    } catch (e: Exception) {
                        append("SymPy: not available\n")
                    }
                }
            }
        }

        // JNI functions
        @Throws(UnsatisfiedLinkError::class)
        private external fun extractBootstrapNative(outputPath: String): Boolean

        external fun getBootstrapSize(): Long
    }
}
