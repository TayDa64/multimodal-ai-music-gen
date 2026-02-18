/*
  ==============================================================================

    ProgressOverlay.h
    
    Progress overlay shown during generation.

  ==============================================================================
*/

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include "../Application/AppState.h"

//==============================================================================
/**
    Semi-transparent overlay showing generation progress.
*/
class ProgressOverlay  : public juce::Component,
                        private AppState::Listener,
                        private juce::Timer
{
public:
    //==============================================================================
    ProgressOverlay(AppState& state);
    ~ProgressOverlay() override;

    //==============================================================================
    void paint(juce::Graphics&) override;
    void resized() override;
    
    //==============================================================================
    /** Listener for overlay events */
    class Listener
    {
    public:
        virtual ~Listener() = default;
        virtual void cancelRequested() = 0;
    };
    
    void addListener(Listener* listener);
    void removeListener(Listener* listener);
    
    /** Show/hide the overlay */
    void show();
    void hide();
    bool isShowing() const { return isVisible(); }

private:
    //==============================================================================
    // AppState::Listener
    void onGenerationStarted() override;
    void onGenerationProgress(const GenerationProgress& progress) override;
    void onGenerationCompleted(const juce::File& outputFile) override;
    void onGenerationError(const juce::String& error) override;
    void onConnectionStatusChanged(bool connected) override;
    
    // Timer for animation
    void timerCallback() override;
    
    //==============================================================================
    AppState& appState;
    juce::ListenerList<Listener> listeners;
    
    // Progress display
    juce::Label titleLabel;
    juce::Label stepLabel;
    juce::Label detailLabel;
    juce::Label percentLabel;
    juce::TextButton cancelButton{ "Cancel" };
    
    // Progress state
    double currentProgress = 0.0;
    juce::String currentStep = "Initializing...";
    juce::String currentDetail;
    double lastProgressSeconds = 0.0;
    
    // Animation
    float spinnerAngle = 0.0f;
    float fadeAlpha = 0.0f;
    bool fadingIn = false;
    bool fadingOut = false;
    double startTimeSeconds = 0.0;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(ProgressOverlay)
};
