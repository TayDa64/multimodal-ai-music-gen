/*
  ==============================================================================

    WaveformComponent.h
    
    Real-time waveform visualization (oscilloscope style).
    Displays audio output as a rolling waveform with genre-themed colors.
    
    Phase 7: Waveform & Spectrum Visualization

  ==============================================================================
*/

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include <juce_audio_basics/juce_audio_basics.h>
#include "GenreTheme.h"
#include "../../Audio/AudioEngine.h"

//==============================================================================
/**
    Real-time waveform visualization component.
    
    Features:
    - Oscilloscope-style rolling waveform display
    - Genre-aware color theming
    - Glow/bloom effects for visual appeal
    - Smooth anti-aliased rendering
    - Optional mirror mode (symmetric display)
    - Peak hold indicators
    
    Performance:
    - Uses a ring buffer for efficient sample capture
    - Renders at 60fps with minimal CPU usage
    - Path-based rendering for smooth curves
*/
class WaveformComponent : public juce::Component,
                          private juce::Timer
{
public:
    //==========================================================================
    /** Display modes for the waveform */
    enum class DisplayMode
    {
        Line,           // Simple line waveform
        Filled,         // Filled waveform from center
        Mirror,         // Mirrored (symmetrical) display
        Bars            // Segmented bar display
    };
    
    //==========================================================================
    WaveformComponent();
    ~WaveformComponent() override;
    
    //==========================================================================
    /** Push audio samples for visualization (call from audio thread) */
    void pushSamples(const float* samples, int numSamples);
    
    /** Push stereo audio samples */
    void pushSamples(const float* leftSamples, const float* rightSamples, int numSamples);
    
    /** Clear the waveform buffer */
    void clear();
    
    //==========================================================================
    // Visual settings
    
    /** Set the display mode */
    void setDisplayMode(DisplayMode mode);
    DisplayMode getDisplayMode() const { return displayMode; }
    
    /** Set the genre theme for coloring */
    void setTheme(const GenreTheme& theme);
    
    /** Enable/disable glow effect */
    void setGlowEnabled(bool enabled);
    bool isGlowEnabled() const { return glowEnabled; }
    
    /** Set line thickness */
    void setLineThickness(float thickness);
    
    /** Enable/disable stereo mode (shows L/R separately) */
    void setStereoMode(bool stereo);
    bool isStereoMode() const { return stereoMode; }
    
    //==========================================================================
    void paint(juce::Graphics& g) override;
    void resized() override;

private:
    //==========================================================================
    void timerCallback() override;
    
    // Drawing helpers
    void drawBackground(juce::Graphics& g);
    void drawGrid(juce::Graphics& g);
    void drawWaveformByMode(juce::Graphics& g, const std::vector<float>& samples,
                            juce::Rectangle<float> bounds);
    void drawWaveformLine(juce::Graphics& g, const std::vector<float>& samples, 
                          juce::Colour fillColour, juce::Colour outlineColour);
    void drawWaveformFilled(juce::Graphics& g, const std::vector<float>& samples,
                            juce::Colour fillColour, juce::Colour outlineColour);
    void drawWaveformMirror(juce::Graphics& g, const std::vector<float>& samples,
                            juce::Colour fillColour, juce::Colour outlineColour);
    void drawWaveformBars(juce::Graphics& g, const std::vector<float>& samples,
                          juce::Colour fillColour);
    void drawGlow(juce::Graphics& g, const juce::Path& path, juce::Colour glowColour);
    void drawPeakIndicators(juce::Graphics& g);
    
    // Sample processing
    void processSamplesForDisplay();
    float getSampleForPosition(const std::vector<float>& buffer, float position);
    
    //==========================================================================
    // Ring buffer for incoming samples (lock-free for audio thread safety)
    static constexpr int bufferSize = 4096;
    std::array<float, bufferSize> leftBuffer;
    std::array<float, bufferSize> rightBuffer;
    std::atomic<int> writePosition { 0 };
    
    // Display buffer (processed for rendering)
    std::vector<float> displayBufferLeft;
    std::vector<float> displayBufferRight;
    int displaySamples = 512;
    
    // Peak tracking
    float peakLeft = 0.0f;
    float peakRight = 0.0f;
    float peakDecay = 0.95f;
    
    // Visual settings
    DisplayMode displayMode = DisplayMode::Filled;
    GenreTheme theme = GenreTheme::defaultTheme();
    bool glowEnabled = true;
    bool stereoMode = false;
    float lineThickness = 2.0f;
    
    // Cached path for glow effect
    juce::Path cachedPath;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(WaveformComponent)
};

