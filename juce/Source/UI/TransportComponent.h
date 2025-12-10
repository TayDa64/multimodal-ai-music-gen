/*
  ==============================================================================

    TransportComponent.h
    
    Transport controls: play, pause, stop, position, BPM.

  ==============================================================================
*/

#pragma once

#include <JuceHeader.h>
#include "../Application/AppState.h"

//==============================================================================
/**
    Transport bar component with playback controls and time display.
*/
class TransportComponent  : public juce::Component,
                           private AppState::Listener,
                           private juce::Timer
{
public:
    //==============================================================================
    TransportComponent(AppState& state);
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
    
    // Timer
    void timerCallback() override;
    
    //==============================================================================
    AppState& appState;
    juce::ListenerList<Listener> listeners;
    
    // Transport buttons
    juce::TextButton playButton{ "Play" };
    juce::TextButton pauseButton{ "Pause" };
    juce::TextButton stopButton{ "Stop" };
    
    // Position slider
    juce::Slider positionSlider;
    juce::Label positionLabel;
    
    // BPM control
    juce::Slider bpmSlider;
    juce::Label bpmLabel;
    
    // Time display
    juce::Label timeDisplay;
    juce::Label durationDisplay;
    
    // Status
    juce::Label statusLabel;
    juce::Label connectionIndicator;
    
    // State
    bool isPlaying = false;
    double currentPosition = 0.0;
    double totalDuration = 0.0;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(TransportComponent)
};
