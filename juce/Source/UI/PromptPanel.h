/*
  ==============================================================================

    PromptPanel.h
    
    Text input panel for entering generation prompts.

  ==============================================================================
*/

#pragma once

#include <JuceHeader.h>
#include "../Application/AppState.h"

//==============================================================================
/**
    Panel for entering prompts and configuring generation parameters.
*/
class PromptPanel  : public juce::Component,
                    private AppState::Listener
{
public:
    //==============================================================================
    PromptPanel(AppState& state);
    ~PromptPanel() override;

    //==============================================================================
    void paint(juce::Graphics&) override;
    void resized() override;
    
    //==============================================================================
    /** Listener for prompt panel events */
    class Listener
    {
    public:
        virtual ~Listener() = default;
        virtual void generateRequested(const juce::String& prompt) = 0;
        virtual void cancelRequested() = 0;
    };
    
    void addListener(Listener* listener);
    void removeListener(Listener* listener);
    
    /** Get the current prompt text */
    juce::String getPromptText() const;
    
    /** Set the prompt text */
    void setPromptText(const juce::String& text);
    
    /** Enable/disable the generate button */
    void setGenerateEnabled(bool enabled);

private:
    //==============================================================================
    void setupPromptInput();
    void setupGenreSelector();
    void setupDurationControls();
    void setupGenerateButton();
    void updateGenrePresets();
    
    // AppState::Listener
    void onGenerationStarted() override;
    void onGenerationProgress(const GenerationProgress& progress) override;
    void onGenerationCompleted(const juce::File& outputFile) override;
    void onGenerationError(const juce::String& error) override;
    void onConnectionStatusChanged(bool connected) override;
    
    //==============================================================================
    AppState& appState;
    juce::ListenerList<Listener> listeners;
    
    // Prompt input
    juce::TextEditor promptInput;
    juce::Label promptLabel;
    
    // Genre selector
    juce::ComboBox genreSelector;
    juce::Label genreLabel;
    
    // Duration control
    juce::Slider durationSlider;
    juce::Label durationLabel;
    juce::Label durationValueLabel;
    
    // Generate button
    juce::TextButton generateButton{ "Generate" };
    juce::TextButton cancelButton{ "Cancel" };
    
    // State
    bool isGenerating = false;
    bool isConnected = false;
    
    // Genre presets
    struct GenrePreset
    {
        juce::String name;
        juce::String promptSuffix;
        int suggestedBPM;
    };
    std::vector<GenrePreset> genrePresets;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(PromptPanel)
};
