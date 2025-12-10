# ==============================================================================
# Multimodal AI Music Generator - JUCE Application
# ==============================================================================
#
# Build Instructions:
#   mkdir build && cd build
#   cmake .. -DJUCE_DIR="path/to/JUCE"
#   cmake --build . --config Release
#
# Or with Visual Studio:
#   cmake .. -G "Visual Studio 17 2022" -DJUCE_DIR="path/to/JUCE"
#   Open build/MultimodalMusicGen.sln
#
# ==============================================================================

cmake_minimum_required(VERSION 3.22)

# Project definition
project(MultimodalMusicGen
    VERSION 1.0.0
    DESCRIPTION "AI-Powered Music Generation with Real-Time Visualization"
    LANGUAGES CXX
)

# C++ Standard
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# ==============================================================================
# JUCE Configuration
# ==============================================================================

# Allow user to specify JUCE path
set(JUCE_DIR "" CACHE PATH "Path to JUCE framework directory")

# Try to find JUCE in common locations if not specified
if(NOT JUCE_DIR)
    # Check common installation paths
    set(JUCE_SEARCH_PATHS
        "C:/JUCE"
        "$ENV{USERPROFILE}/JUCE"
        "$ENV{PROGRAMFILES}/JUCE"
        "${CMAKE_CURRENT_SOURCE_DIR}/../JUCE"
        "${CMAKE_CURRENT_SOURCE_DIR}/../../JUCE"
    )
    
    foreach(SEARCH_PATH ${JUCE_SEARCH_PATHS})
        if(EXISTS "${SEARCH_PATH}/modules/juce_core/juce_core.h")
            set(JUCE_DIR "${SEARCH_PATH}")
            message(STATUS "Found JUCE at: ${JUCE_DIR}")
            break()
        endif()
    endforeach()
endif()

# Verify JUCE was found
if(NOT JUCE_DIR OR NOT EXISTS "${JUCE_DIR}/modules/juce_core/juce_core.h")
    message(FATAL_ERROR 
        "JUCE not found! Please specify JUCE location:\n"
        "  cmake .. -DJUCE_DIR=\"path/to/JUCE\"\n"
        "Or install JUCE from: https://juce.com/get-juce/download"
    )
endif()

# Add JUCE to the project
add_subdirectory(${JUCE_DIR} ${CMAKE_BINARY_DIR}/JUCE EXCLUDE_FROM_ALL)

# ==============================================================================
# Application Target
# ==============================================================================

juce_add_gui_app(MultimodalMusicGen
    # Application identity
    PRODUCT_NAME "AI Music Generator"
    COMPANY_NAME "Multimodal Audio"
    BUNDLE_ID "com.multimodal.aimusicgen"
    
    # Version
    VERSION "${PROJECT_VERSION}"
    
    # Icon (will be created later)
    # ICON_BIG "${CMAKE_CURRENT_SOURCE_DIR}/Resources/Icon.png"
    
    # Plugin characteristics (for future VST3 support)
    PLUGIN_MANUFACTURER_CODE Mmag
    PLUGIN_CODE Mmgn
    
    # App characteristics
    NEEDS_MIDI_INPUT TRUE
    NEEDS_MIDI_OUTPUT TRUE
    IS_SYNTH FALSE
    EDITOR_WANTS_KEYBOARD_FOCUS TRUE
    
    # Document handling
    DOCUMENT_EXTENSIONS "mmg"
)

# ==============================================================================
# Source Files
# ==============================================================================

target_sources(MultimodalMusicGen PRIVATE
    # Application entry point
    Source/Main.cpp
    
    # Main window and component
    Source/MainComponent.cpp
    Source/MainComponent.h
    
    # Application state
    Source/Application/AppState.cpp
    Source/Application/AppState.h
    Source/Application/AppConfig.h
    
    # Communication with Python backend
    Source/Communication/OSCBridge.cpp
    Source/Communication/OSCBridge.h
    Source/Communication/Messages.h
    Source/Communication/PythonManager.cpp
    Source/Communication/PythonManager.h
    
    # UI Components (placeholders for now)
    Source/UI/TransportComponent.cpp
    Source/UI/TransportComponent.h
    Source/UI/PromptPanel.cpp
    Source/UI/PromptPanel.h
    Source/UI/ProgressOverlay.cpp
    Source/UI/ProgressOverlay.h
    
    # Look and Feel
    Source/UI/Theme/AppLookAndFeel.cpp
    Source/UI/Theme/AppLookAndFeel.h
    Source/UI/Theme/ColourScheme.h
)

# ==============================================================================
# JUCE Module Dependencies
# ==============================================================================

target_link_libraries(MultimodalMusicGen
    PRIVATE
        # Core modules
        juce::juce_core
        juce::juce_events
        juce::juce_data_structures
        
        # Audio modules
        juce::juce_audio_basics
        juce::juce_audio_devices
        juce::juce_audio_formats
        juce::juce_audio_processors
        juce::juce_audio_utils
        
        # GUI modules
        juce::juce_graphics
        juce::juce_gui_basics
        juce::juce_gui_extra
        
        # Network (for OSC)
        juce::juce_osc
        
    PUBLIC
        # Recommended flags
        juce::juce_recommended_config_flags
        juce::juce_recommended_lto_flags
        juce::juce_recommended_warning_flags
)

# ==============================================================================
# Preprocessor Definitions
# ==============================================================================

target_compile_definitions(MultimodalMusicGen
    PRIVATE
        # JUCE configuration
        JUCE_WEB_BROWSER=0
        JUCE_USE_CURL=0
        JUCE_VST3_CAN_REPLACE_VST2=0
        
        # Application info
        JUCE_APPLICATION_NAME_STRING="$<TARGET_PROPERTY:MultimodalMusicGen,JUCE_PRODUCT_NAME>"
        JUCE_APPLICATION_VERSION_STRING="$<TARGET_PROPERTY:MultimodalMusicGen,JUCE_VERSION>"
        
        # OSC configuration
        JUCE_USE_OSC=1
        
        # Development flags
        $<$<CONFIG:Debug>:JUCE_DEBUG=1>
        $<$<CONFIG:Debug>:DEBUG=1>
        $<$<CONFIG:Release>:NDEBUG=1>
)

# ==============================================================================
# Include Directories
# ==============================================================================

target_include_directories(MultimodalMusicGen
    PRIVATE
        ${CMAKE_CURRENT_SOURCE_DIR}/Source
)

# ==============================================================================
# Platform-Specific Configuration
# ==============================================================================

if(WIN32)
    # Windows-specific settings
    target_compile_definitions(MultimodalMusicGen PRIVATE
        _UNICODE
        UNICODE
        WIN32_LEAN_AND_MEAN
    )
    
    # Link Windows libraries
    target_link_libraries(MultimodalMusicGen PRIVATE
        ws2_32      # Winsock for OSC
        winmm       # Windows Multimedia
        version     # Version info
    )
    
elseif(APPLE)
    # macOS-specific settings
    target_link_libraries(MultimodalMusicGen PRIVATE
        "-framework CoreAudio"
        "-framework CoreMIDI"
        "-framework AudioToolbox"
        "-framework Accelerate"
    )
    
elseif(UNIX)
    # Linux-specific settings
    find_package(PkgConfig REQUIRED)
    pkg_check_modules(ALSA REQUIRED alsa)
    pkg_check_modules(FREETYPE2 REQUIRED freetype2)
    
    target_link_libraries(MultimodalMusicGen PRIVATE
        ${ALSA_LIBRARIES}
        ${FREETYPE2_LIBRARIES}
        pthread
        dl
    )
endif()

# ==============================================================================
# Copy Resources
# ==============================================================================

# Copy Python backend info for runtime
configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/../requirements.txt
    ${CMAKE_BINARY_DIR}/requirements.txt
    COPYONLY
)

# ==============================================================================
# Installation
# ==============================================================================

install(TARGETS MultimodalMusicGen
    RUNTIME DESTINATION bin
    BUNDLE DESTINATION .
)

# ==============================================================================
# Summary
# ==============================================================================

message(STATUS "")
message(STATUS "=== Multimodal AI Music Generator ===")
message(STATUS "Version:     ${PROJECT_VERSION}")
message(STATUS "JUCE:        ${JUCE_DIR}")
message(STATUS "Build Type:  ${CMAKE_BUILD_TYPE}")
message(STATUS "Platform:    ${CMAKE_SYSTEM_NAME}")
message(STATUS "")
