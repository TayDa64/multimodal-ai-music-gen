/*
  ==============================================================================

    SpectrumComponent.h
    
    Real-time FFT spectrum analyzer visualization.
    Displays frequency content with smooth animation and genre-themed colors.
    
    Phase 7: Waveform & Spectrum Visualization

  ==============================================================================
*/

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include <juce_audio_basics/juce_audio_basics.h>
#include <juce_dsp/juce_dsp.h>
#include "GenreTheme.h"

//==============================================================================
/**
    Real-time spectrum analyzer component.
    
    Features:
    - FFT-based frequency analysis
    - Genre-aware color theming with frequency gradients
    - Multiple display modes (bars, line, filled)
    - Smooth animation with configurable decay
    - Peak hold indicators
    - Logarithmic or linear frequency scale
    
    Performance:
    - Uses JUCE DSP FFT for efficient processing
    - Lock-free sample input from audio thread
    - Renders at 60fps with minimal CPU
*/
class SpectrumComponent : public juce::Component,
                          private juce::Timer
{
public:
    //==========================================================================
    /** FFT order determines resolution (2^order samples) */
    static constexpr int fftOrder = 11;  // 2048 samples
    static constexpr int fftSize = 1 << fftOrder;
    
    //==========================================================================
    /** Display modes for the spectrum */
    enum class DisplayMode
    {
        Bars,           // Classic bar graph
        Line,           // Smooth line
        Filled,         // Filled curve
        Glow            // Bars with glow effect
    };
    
    /** Frequency scale modes */
    enum class FrequencyScale
    {
        Linear,         // Linear frequency distribution
        Logarithmic     // Log scale (more like human hearing)
    };
    
    //==========================================================================
    SpectrumComponent();
    ~SpectrumComponent() override;
    
    //==========================================================================
    /** Push audio samples for analysis (call from audio thread) */
    void pushSamples(const float* samples, int numSamples);
    
    /** Push stereo audio samples (averages L+R) */
    void pushSamples(const float* leftSamples, const float* rightSamples, int numSamples);
    
    /** Clear spectrum data */
    void clear();
    
    //==========================================================================
    // Visual settings
    
    /** Set the display mode */
    void setDisplayMode(DisplayMode mode);
    DisplayMode getDisplayMode() const { return displayMode; }
    
    /** Set the frequency scale */
    void setFrequencyScale(FrequencyScale scale);
    FrequencyScale getFrequencyScale() const { return frequencyScale; }
    
    /** Set the genre theme for coloring */
    void setTheme(const GenreTheme& theme);
    
    /** Set smoothing factor (0.0 = no smoothing, 1.0 = infinite smoothing) */
    void setSmoothing(float smoothing);
    
    /** Set decay rate for bars (higher = slower decay) */
    void setDecayRate(float rate);
    
    /** Enable/disable peak hold indicators */
    void setPeakHoldEnabled(bool enabled);
    bool isPeakHoldEnabled() const { return peakHoldEnabled; }
    
    /** Set number of display bands */
    void setNumBands(int bands);
    int getNumBands() const { return numBands; }
    
    //==========================================================================
    void paint(juce::Graphics& g) override;
    void resized() override;

private:
    //==========================================================================
    void timerCallback() override;
    
    // FFT processing
    void processFFT();
    float getFrequencyForBin(int bin) const;
    int getBinForFrequency(float frequency) const;
    float getMagnitudeForFrequencyRange(float lowFreq, float highFreq) const;
    
    // Drawing helpers
    void drawBackground(juce::Graphics& g);
    void drawFrequencyLabels(juce::Graphics& g);
    void drawSpectrumBars(juce::Graphics& g);
    void drawSpectrumLine(juce::Graphics& g);
    void drawSpectrumFilled(juce::Graphics& g);
    void drawSpectrumGlow(juce::Graphics& g);
    void drawPeakHold(juce::Graphics& g);
    
    // Utility
    juce::Colour getColourForBand(int band) const;
    float getFrequencyForBand(int band) const;
    
    //==========================================================================
    // FFT processor
    juce::dsp::FFT forwardFFT;
    juce::dsp::WindowingFunction<float> window;
    
    // Input buffer (ring buffer for audio thread)
    std::array<float, fftSize * 2> fifo;
    std::array<float, fftSize * 2> fftData;
    int fifoIndex = 0;
    std::atomic<bool> nextFFTBlockReady { false };
    
    // Output data
    std::vector<float> spectrumData;      // Current smoothed levels
    std::vector<float> rawSpectrumData;   // Raw FFT output
    std::vector<float> peakHoldData;      // Peak hold levels
    std::vector<int> peakHoldCountdown;   // Frames until peak decay
    
    // Settings
    DisplayMode displayMode = DisplayMode::Glow;
    FrequencyScale frequencyScale = FrequencyScale::Logarithmic;
    GenreTheme theme = GenreTheme::defaultTheme();
    float smoothingFactor = 0.7f;
    float decayRate = 0.92f;
    bool peakHoldEnabled = true;
    int numBands = 64;
    
    // Audio info
    double currentSampleRate = 44100.0;
    
    // Peak hold timing
    static constexpr int peakHoldFrames = 30;  // ~0.5 sec at 60fps
    static constexpr float peakDecayRate = 0.95f;
    
    //==========================================================================
    // Production-grade envelope follower parameters
    // Attack: fast response to transients (~5ms)
    // Release: smooth decay (~300ms)
    static constexpr float defaultAttackMs = 5.0f;
    static constexpr float defaultReleaseMs = 300.0f;
    float attackCoeff = 0.0f;   // Calculated from attack time
    float releaseCoeff = 0.0f;  // Calculated from release time
    
    // Noise floor gate - prevents flickering on silent frequencies
    static constexpr float noiseFloorDb = -80.0f;
    static constexpr float gateThreshold = 0.00001f;  // ~-100dB linear
    
    // Multi-frame averaging for smoother display
    static constexpr int averagingFrames = 3;
    std::vector<std::vector<float>> averagingBuffer;
    int averagingIndex = 0;
    
    // Envelope state per band (for attack/release ballistics)
    std::vector<float> envelopeState;
    
    void calculateBallistics(double sampleRate, float attackMs, float releaseMs);
    float applyEnvelope(float current, float target, int bandIndex);
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(SpectrumComponent)
};

