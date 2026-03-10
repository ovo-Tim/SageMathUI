# Minimum CMake version
cmake_minimum_required(VERSION 3.22)

# Project name
project(sage_ui_jni)

# Set C++ standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_C_STANDARD 11)

# Add bootstrap extraction JNI library
add_library(sage_bootstrap SHARED
    bootstrap_jni.c
    bootstrap_bin.S
)

# Include JNI headers
find_package(JNI REQUIRED)
target_include_directories(sage_bootstrap PRIVATE ${JNI_INCLUDE_DIRS})

# Link against NDK libraries
target_link_libraries(sage_bootstrap
    log
    z
)

# Set output directory
set_target_properties(sage_bootstrap PROPERTIES
    LIBRARY_OUTPUT_DIRECTORY ${CMAKE_LIBRARY_OUTPUT_DIRECTORY}
)
