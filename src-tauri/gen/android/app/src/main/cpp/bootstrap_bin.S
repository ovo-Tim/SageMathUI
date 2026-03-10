# Assembly file to embed Termux bootstrap ZIP as binary data
# Usage: Compiled into JNI library, allows loading bootstrap-aarch64.zip without file I/O

.data
.global bootstrap_zip_start
.global bootstrap_zip_end

.align 4
bootstrap_zip_start:
    # Binary data will be inserted here by build script
    # This is a placeholder; actual zip data inserted during build
    .incbin "bootstrap-aarch64.zip"

bootstrap_zip_end:
    .long 0  # End marker

.previous
