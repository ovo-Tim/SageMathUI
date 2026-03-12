package com.sagemath.ui

import android.os.Bundle
import android.util.Log
import androidx.activity.enableEdgeToEdge
import org.json.JSONObject
import java.io.File
import java.io.FileOutputStream
import java.io.IOException

class MainActivity : TauriActivity() {
    companion object {
        private const val TAG = "SageMathUI"
        private const val ASSETS_VERSION = "2"
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        enableEdgeToEdge()
        writeSolverConfig()
        extractPythonAssets()
        super.onCreate(savedInstanceState)
    }

    private fun writeSolverConfig() {
        val config = JSONObject().apply {
            put("native_lib_dir", applicationInfo.nativeLibraryDir)
            put("files_dir", filesDir.absolutePath)
            put("cache_dir", cacheDir.absolutePath)
        }
        File(filesDir, ".solver_config.json").writeText(config.toString())
        Log.d(TAG, "Solver config: $config")
    }

    private fun extractPythonAssets() {
        val versionMarker = File(filesDir, ".python_assets_version")
        if (versionMarker.exists() && versionMarker.readText().trim() == ASSETS_VERSION) {
            Log.d(TAG, "Python assets already extracted (v$ASSETS_VERSION)")
            return
        }

        Log.i(TAG, "Extracting Python assets (v$ASSETS_VERSION)...")

        val pythonDir = File(filesDir, "python")
        if (pythonDir.exists()) {
            pythonDir.deleteRecursively()
        }
        pythonDir.mkdirs()

        try {
            extractAssetDir("python", pythonDir)
            extractAssetFile("sage_bridge.py", File(filesDir, "sage_bridge.py"))

            versionMarker.writeText(ASSETS_VERSION)
            Log.i(TAG, "Python assets extracted successfully")
        } catch (e: IOException) {
            Log.e(TAG, "Failed to extract Python assets", e)
        }
    }

    private fun extractAssetDir(assetPath: String, targetDir: File) {
        val entries = assets.list(assetPath) ?: return

        if (entries.isEmpty()) {
            extractAssetFile(assetPath, targetDir)
            return
        }

        targetDir.mkdirs()
        for (entry in entries) {
            val childAssetPath = "$assetPath/$entry"
            val childTarget = File(targetDir, entry)
            extractAssetDir(childAssetPath, childTarget)
        }
    }

    private fun extractAssetFile(assetPath: String, targetFile: File) {
        targetFile.parentFile?.mkdirs()
        try {
            assets.open(assetPath).use { input ->
                FileOutputStream(targetFile).use { output ->
                    input.copyTo(output)
                }
            }
        } catch (e: IOException) {
            Log.w(TAG, "Skipping asset: $assetPath (${e.message})")
        }
    }
}
