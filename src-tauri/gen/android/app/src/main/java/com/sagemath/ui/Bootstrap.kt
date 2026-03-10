/**
 * Bootstrap: Manages extraction and setup of embedded Termux environment
 */
package com.sagemath.ui

import android.content.Context
import android.util.Log
import java.io.File

class Bootstrap {
    companion object {
        private const val TAG = "Bootstrap"
        
        init {
            try {
                System.loadLibrary("sage_bootstrap")
                Log.i(TAG, "Bootstrap JNI library loaded")
            } catch (e: UnsatisfiedLinkError) {
                Log.e(TAG, "Failed to load bootstrap JNI library", e)
            }
        }

        /**
         * Extract Termux bootstrap environment to app's files directory
         * @param context Android context for getting file paths
         * @return true if extraction successful, false otherwise
         */
        fun extractBootstrap(context: Context): Boolean {
            val bootstrapDir = File(context.filesDir, "termux_prefix")
            
            // Check if already extracted
            if (bootstrapDir.exists() && File(bootstrapDir, "bin/bash").exists()) {
                Log.i(TAG, "Bootstrap already extracted at ${bootstrapDir.absolutePath}")
                return true
            }

            // Create bootstrap directory if it doesn't exist
            if (!bootstrapDir.exists()) {
                bootstrapDir.mkdirs()
                Log.i(TAG, "Created bootstrap directory")
            }

            // Extract bootstrap zip using JNI
            Log.i(TAG, "Starting bootstrap extraction to ${bootstrapDir.absolutePath}")
            val success = extractBootstrapNative(bootstrapDir.absolutePath)
            
            if (success) {
                Log.i(TAG, "Bootstrap extracted successfully")
                // Set executable permissions on important binaries
                setExecutablePermissions(bootstrapDir)
            } else {
                Log.e(TAG, "Bootstrap extraction failed")
            }
            
            return success
        }

        /**
         * Set executable permissions on critical binaries
         */
        private fun setExecutablePermissions(bootstrapDir: File) {
            val binaries = listOf(
                "bin/bash",
                "bin/python3",
                "bin/chmod",
                "bin/ls"
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

        // JNI functions
        @Throws(UnsatisfiedLinkError::class)
        private external fun extractBootstrapNative(outputPath: String): Boolean

        external fun getBootstrapSize(): Long
    }
}
