/*
  ==============================================================================

    TransportComponent.h
    
    Transport controls: play, pause, stop, position, BPM.

  ==============================================================================
*/

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include "../Application/AppState.h"
#include "../Audio/AudioEngine.h"

// Forward declaration
class AudioSettingsDialog;

//==============================================================================
/**
    Transport bar component with playback controls and time display.
*/
class TransportComponent  : public juce::Component,
                           private AppState::Listener,
                           private mmg::AudioEngine::Listener,
                           private juce::Timer
{
public:
    //==============================================================================
    TransportComponent(AppState& state, mmg::AudioEngine& engine);
    ~TransportComponent() override;

    //==============================================================================
    void paint(juce::Graphics&) override;
    void resized() override;
    
    //==============================================================================
    /** Listener for transport events */
    class Listener
    {
    public:
        virtual ~Listener() = default;
        virtual void transportPlayRequested() = 0;
        virtual void transportPauseRequested() = 0;
        virtual void transportStopRequested() = 0;
        virtual void transportPositionChanged(double newPosition) = 0;
        virtual void transportBPMChanged(int newBPM) = 0;
    };
    
    void addListener(Listener* listener);
    void removeListener(Listener* listener);

private:
    //==============================================================================
    void setupButtons();
    void setupSliders();
    void setupLabels();
    void updateButtonStates();
    void updateTimeDisplay();
    
    // Button callbacks
    void playClicked();
    void pauseClicked();
    void stopClicked();
    
    // AppState::Listener
    void onGenerationStarted() override;
    void onGenerationProgress(const GenerationProgress& progress) override;
    void onGenerationCompleted(const juce::File& outputFile) override;
    void onGenerationError(const juce::String& error) override;
    void onConnectionStatusChanged(bool connected) override;
    
    // AudioEngine::Listener
    void transportStateChanged(mmg::AudioEngine::TransportState newState) override;
    void audioDeviceChanged() override;
    
    // Timer
    void timerCallback() override;
    
    //==============================================================================
    AppState& appState;
    mmg::AudioEngine& audioEngine;
    juce::ListenerList<Listener> listeners;
    
    // Transport buttons
    juce::TextButton playButton{ "Play" };
    juce::TextButton pauseButton{ "Pause" };
    juce::TextButton stopButton{ "Stop" };
    juce::ToggleButton loopButton{ "Loop" };
    
    // Position slider
    juce::Slider positionSlider;
    juce::Label positionLabel;
    
    // BPM control
    juce::Slider bpmSlider;
    juce::Label bpmLabel;
    
    // Test tone (for audio verification)
    juce::ToggleButton testToneButton{ "Test Tone" };
    
    // Load MIDI button (for testing)
    juce::TextButton loadMidiButton{ "Load MIDI" };
    
    // Time display
    juce::Label timeDisplay;
    juce::Label barBeatDisplay;  // Bar:Beat display (e.g., "3:2")
    juce::Label durationDisplay;
    
    // Audio settings button
    juce::TextButton audioSettingsButton{ juce::String(juce::CharPointer_UTF8("\xE2\x9A\x99")) }; // Gear icon
    
    // Status
    juce::Label statusLabel;
    juce::Label connectionIndicator;
    
    // State
    bool isPlaying = false;
    double currentPosition = 0.0;
    double totalDuration = 0.0;
    bool lastHasAudioState = false;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(TransportComponent)
};
