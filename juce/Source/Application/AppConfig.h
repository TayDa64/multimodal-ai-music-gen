/*
  ==============================================================================

    AppConfig.h
    
    Application configuration constants.

  ==============================================================================
*/

#pragma once

namespace AppConfig
{
    // Application identity
    static constexpr const char* appName = "AI Music Generator";
    static constexpr const char* companyName = "Multimodal Audio";
    static constexpr const char* versionString = "1.0.0";
    
    // Server configuration
    static constexpr int defaultServerPort = 9000;
    static constexpr int defaultResponsePort = 9001;
    static constexpr const char* serverHost = "127.0.0.1";
    
    // File extensions
    static constexpr const char* projectExtension = ".mmg";
    static constexpr const char* projectWildcard = "*.mmg";
    
    // UI constants
    static constexpr int minWindowWidth = 800;
    static constexpr int minWindowHeight = 600;
    static constexpr int defaultWindowWidth = 1280;
    static constexpr int defaultWindowHeight = 800;
    
    // Timeouts
    static constexpr int connectionTimeoutMs = 5000;
    static constexpr int generationTimeoutMs = 300000; // 5 minutes
    static constexpr int healthCheckIntervalMs = 2000;
}
