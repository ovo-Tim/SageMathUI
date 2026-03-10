// Bootstrap extraction JNI wrapper
// This extracts the embedded Termux bootstrap ZIP from the compiled binary

#include <jni.h>
#include <android/log.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <zip.h>

#define LOG_TAG "BootstrapJNI"
#define LOGI(...) __android_log_print(ANDROID_LOG_INFO, LOG_TAG, __VA_ARGS__)
#define LOGE(...) __android_log_print(ANDROID_LOG_ERROR, LOG_TAG, __VA_ARGS__)

// External symbols from bootstrap_bin.S
extern unsigned char bootstrap_zip_start[];
extern unsigned char bootstrap_zip_end[];

/**
 * Extract bootstrap zip from embedded binary
 * 
 * @param env JNI environment
 * @param clazz Java class
 * @param output_path Java string path to extract to
 * @return true if successful, false otherwise
 */
JNIEXPORT jboolean JNICALL
Java_com_sagemath_ui_Bootstrap_extractBootstrap(
    JNIEnv* env,
    jclass clazz,
    jstring output_path
) {
    const char* output_str = (*env)->GetStringUTFChars(env, output_path, 0);
    if (!output_str) {
        LOGE("Failed to get output path string");
        return JNI_FALSE;
    }

    // Calculate size of embedded zip
    size_t zip_size = bootstrap_zip_end - bootstrap_zip_start;
    LOGI("Extracting bootstrap zip (%zu bytes) to %s", zip_size, output_str);

    // Write zip file to temporary location
    char temp_zip[256];
    snprintf(temp_zip, sizeof(temp_zip), "%s/bootstrap.zip", output_str);

    FILE* zip_file = fopen(temp_zip, "wb");
    if (!zip_file) {
        LOGE("Failed to open output zip file: %s", temp_zip);
        (*env)->ReleaseStringUTFChars(env, output_path, output_str);
        return JNI_FALSE;
    }

    // Write embedded zip data
    if (fwrite(bootstrap_zip_start, 1, zip_size, zip_file) != zip_size) {
        LOGE("Failed to write complete zip file");
        fclose(zip_file);
        (*env)->ReleaseStringUTFChars(env, output_path, output_str);
        return JNI_FALSE;
    }
    fclose(zip_file);

    LOGI("Bootstrap zip written to: %s", temp_zip);

    // Open and extract zip
    int error = 0;
    zip_t* zip = zip_open(temp_zip, 0, &error);
    if (!zip) {
        LOGE("Failed to open zip file: error %d", error);
        (*env)->ReleaseStringUTFChars(env, output_path, output_str);
        return JNI_FALSE;
    }

    // Extract all files from zip
    zip_int64_t num_entries = zip_get_num_entries(zip, 0);
    LOGI("Found %lld entries in bootstrap zip", num_entries);

    for (zip_int64_t i = 0; i < num_entries; i++) {
        zip_stat_t stat;
        zip_stat_index(zip, i, 0, &stat);

        // Construct output file path
        char output_file[512];
        snprintf(output_file, sizeof(output_file), "%s/%s", output_str, stat.name);

        // Create parent directories if needed
        // (simplified - in production, use proper directory traversal)

        // Extract file
        zip_file_t* file = zip_fopen_index(zip, i, 0);
        if (!file) {
            LOGE("Failed to open entry %s in zip", stat.name);
            continue;
        }

        FILE* out = fopen(output_file, "wb");
        if (!out) {
            LOGE("Failed to create output file: %s", output_file);
            zip_fclose(file);
            continue;
        }

        // Copy file data
        char buffer[4096];
        zip_int64_t bytes;
        while ((bytes = zip_fread(file, buffer, sizeof(buffer))) > 0) {
            fwrite(buffer, 1, bytes, out);
        }

        fclose(out);
        zip_fclose(file);
        LOGI("Extracted: %s", stat.name);
    }

    zip_close(zip);
    LOGI("Bootstrap extraction completed");

    (*env)->ReleaseStringUTFChars(env, output_path, output_str);
    return JNI_TRUE;
}

/**
 * Get size of embedded bootstrap zip
 */
JNIEXPORT jlong JNICALL
Java_com_sagemath_ui_Bootstrap_getBootstrapSize(
    JNIEnv* env,
    jclass clazz
) {
    return (jlong)(bootstrap_zip_end - bootstrap_zip_start);
}
