/*
  ==============================================================================

    PromptPanel.cpp
    
    Implementation of prompt input panel.

  ==============================================================================
*/

#include "PromptPanel.h"
#include "Theme/ColourScheme.h"

//==============================================================================
PromptPanel::PromptPanel(AppState& state)
    : appState(state)
{
    setupPromptInput();
    setupGenreSelector();
    setupDurationControls();
    setupGenerateButton();
    
    appState.addListener(this);
}

PromptPanel::~PromptPanel()
{
    appState.removeListener(this);
}

//==============================================================================
void PromptPanel::setupPromptInput()
{
    // Label
    promptLabel.setText("Prompt", juce::dontSendNotification);
    promptLabel.setFont(juce::Font(14.0f, juce::Font::bold));
    addAndMakeVisible(promptLabel);
    
    // Text editor
    promptInput.setMultiLine(true);
    promptInput.setReturnKeyStartsNewLine(false);
    promptInput.setScrollbarsShown(true);
    promptInput.setPopupMenuEnabled(true);
    promptInput.setTextToShowWhenEmpty("Describe the music you want to generate...", 
                                       AppColours::textSecondary);
    promptInput.setFont(juce::Font(14.0f));
    
    // Handle Enter key to generate
    promptInput.onReturnKey = [this] {
        if (!isGenerating && isConnected && promptInput.getText().isNotEmpty())
        {
            listeners.call(&Listener::generateRequested, promptInput.getText());
        }
    };
    
    addAndMakeVisible(promptInput);
}

void PromptPanel::setupGenreSelector()
{
    // Label
    genreLabel.setText("Genre", juce::dontSendNotification);
    genreLabel.setFont(juce::Font(12.0f));
    genreLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(genreLabel);
    
    // Setup genre presets
    genrePresets = {
        { "G-Funk",     "west coast g-funk synths bass",    92 },
        { "Trap",       "trap 808 hi-hats",                 140 },
        { "Boom Bap",   "boom bap drums sample chops",      90 },
        { "Lo-Fi",      "lo-fi chill vinyl crackle",        85 },
        { "Drill",      "UK drill sliding 808s",            140 },
        { "RnB",        "smooth rnb soul",                  100 },
        { "Jazz Hop",   "jazz hip-hop samples",             88 },
        { "Custom",     "",                                 100 }
    };
    
    // Populate combo box
    for (int i = 0; i < (int)genrePresets.size(); ++i)
    {
        genreSelector.addItem(genrePresets[i].name, i + 1);
    }
    
    genreSelector.setSelectedId(1); // G-Funk default
    
    genreSelector.onChange = [this] {
        int selectedIndex = genreSelector.getSelectedId() - 1;
        if (selectedIndex >= 0 && selectedIndex < (int)genrePresets.size())
        {
            auto& preset = genrePresets[selectedIndex];
            if (preset.name != "Custom")
            {
                appState.setBPM(preset.suggestedBPM);
            }
        }
    };
    
    addAndMakeVisible(genreSelector);
}

void PromptPanel::setupDurationControls()
{
    // Label
    durationLabel.setText("Duration", juce::dontSendNotification);
    durationLabel.setFont(juce::Font(12.0f));
    durationLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(durationLabel);
    
    // Slider with text box showing value
    durationSlider.setSliderStyle(juce::Slider::LinearHorizontal);
    durationSlider.setTextBoxStyle(juce::Slider::TextBoxRight, false, 60, 20);
    durationSlider.setRange(4, 32, 4);
    durationSlider.setValue(appState.getDurationBars());
    durationSlider.setTextValueSuffix(" bars");
    durationSlider.onValueChange = [this] {
        int bars = (int)durationSlider.getValue();
        appState.setDurationBars(bars);
    };
    addAndMakeVisible(durationSlider);
    
    // Value label no longer needed since slider shows it
    durationValueLabel.setVisible(false);
}

void PromptPanel::setupGenerateButton()
{
    // Generate button - always visible when not generating
    generateButton.setColour(juce::TextButton::buttonColourId, AppColours::primary);
    generateButton.setColour(juce::TextButton::textColourOffId, AppColours::textPrimary);
    generateButton.setButtonText("Generate");
    generateButton.onClick = [this] {
        if (!isGenerating && promptInput.getText().isNotEmpty())
        {
            // Append genre suffix if not custom
            juce::String finalPrompt = promptInput.getText();
            int selectedIndex = genreSelector.getSelectedId() - 1;
            if (selectedIndex >= 0 && selectedIndex < (int)genrePresets.size())
            {
                auto& preset = genrePresets[selectedIndex];
                if (preset.promptSuffix.isNotEmpty())
                {
                    finalPrompt += " " + preset.promptSuffix;
                }
            }
            
            appState.setPrompt(finalPrompt);
            listeners.call(&Listener::generateRequested, finalPrompt);
        }
    };
    // Enable button even when disconnected - will show error message if clicked
    generateButton.setEnabled(true);
    generateButton.setVisible(true);
    addAndMakeVisible(generateButton);
    
    // Cancel button - only shown during generation
    cancelButton.setColour(juce::TextButton::buttonColourId, AppColours::error);
    cancelButton.onClick = [this] {
        listeners.call(&Listener::cancelRequested);
    };
    cancelButton.setVisible(false);
    addChildComponent(cancelButton); // Use addChildComponent since it starts hidden
}

//==============================================================================
void PromptPanel::paint(juce::Graphics& g)
{
    // Background
    g.setColour(AppColours::surface);
    g.fillRoundedRectangle(getLocalBounds().toFloat(), 8.0f);
    
    // Border
    g.setColour(AppColours::border);
    g.drawRoundedRectangle(getLocalBounds().toFloat().reduced(0.5f), 8.0f, 1.0f);
}

void PromptPanel::resized()
{
    auto bounds = getLocalBounds().reduced(16);
    
    // Title
    promptLabel.setBounds(bounds.removeFromTop(24));
    bounds.removeFromTop(8);
    
    // Prompt input (takes most of the space)
    auto inputHeight = juce::jmax(60, bounds.getHeight() - 120);
    promptInput.setBounds(bounds.removeFromTop(inputHeight));
    bounds.removeFromTop(12);
    
    // Genre row
    auto genreRow = bounds.removeFromTop(28);
    genreLabel.setBounds(genreRow.removeFromLeft(45).withHeight(28));
    genreSelector.setBounds(genreRow.removeFromLeft(120).withHeight(28));
    
    bounds.removeFromTop(8);
    
    // Duration row (separate line for clarity)
    auto durationRow = bounds.removeFromTop(28);
    durationLabel.setBounds(durationRow.removeFromLeft(60).withHeight(28));
    durationSlider.setBounds(durationRow.withHeight(28)); // Takes remaining width
    
    bounds.removeFromTop(12);
    
    // Generate button row
    auto buttonRow = bounds.removeFromTop(36);
    auto buttonWidth = 140;
    
    // Center the button
    auto buttonX = (buttonRow.getWidth() - buttonWidth) / 2;
    generateButton.setBounds(buttonRow.withX(buttonRow.getX() + buttonX).withWidth(buttonWidth).withHeight(32));
    cancelButton.setBounds(generateButton.getBounds());
}

//==============================================================================
juce::String PromptPanel::getPromptText() const
{
    return promptInput.getText();
}

void PromptPanel::setPromptText(const juce::String& text)
{
    promptInput.setText(text);
}

void PromptPanel::setGenerateEnabled(bool enabled)
{
    generateButton.setEnabled(enabled && isConnected && !isGenerating);
}

//==============================================================================
void PromptPanel::onGenerationStarted()
{
    juce::MessageManager::callAsync([this] {
        isGenerating = true;
        generateButton.setVisible(false);
        cancelButton.setVisible(true);
        promptInput.setEnabled(false);
        genreSelector.setEnabled(false);
        durationSlider.setEnabled(false);
    });
}

void PromptPanel::onGenerationProgress(const GenerationProgress& /*progress*/)
{
    // Could update button text with progress if desired
}

void PromptPanel::onGenerationCompleted(const juce::File& /*outputFile*/)
{
    juce::MessageManager::callAsync([this] {
        DBG("PromptPanel::onGenerationCompleted - resetting UI state");
        isGenerating = false;
        
        // Restore Generate button
        generateButton.setVisible(true);
        generateButton.setEnabled(true);
        generateButton.setButtonText(isConnected ? "Generate" : "Generate (Offline)");
        
        // Hide Cancel button
        cancelButton.setVisible(false);
        
        // Re-enable all input controls
        promptInput.setEnabled(true);
        genreSelector.setEnabled(true);
        durationSlider.setEnabled(true);
        
        // Force repaint to ensure UI updates
        repaint();
    });
}

void PromptPanel::onGenerationError(const juce::String& /*error*/)
{
    juce::MessageManager::callAsync([this] {
        DBG("PromptPanel::onGenerationError - resetting UI state");
        isGenerating = false;
        
        // Restore Generate button
        generateButton.setVisible(true);
        generateButton.setEnabled(true);
        generateButton.setButtonText(isConnected ? "Generate" : "Generate (Offline)");
        
        // Hide Cancel button
        cancelButton.setVisible(false);
        
        // Re-enable all input controls
        promptInput.setEnabled(true);
        genreSelector.setEnabled(true);
        durationSlider.setEnabled(true);
        
        // Force repaint
        repaint();
    });
}

void PromptPanel::onConnectionStatusChanged(bool connected)
{
    juce::MessageManager::callAsync([this, connected] {
        isConnected = connected;
        // Keep button enabled - clicking when disconnected shows helpful error message
        generateButton.setEnabled(!isGenerating);
        generateButton.setButtonText(connected ? "Generate" : "Generate (Offline)");
    });
}

//==============================================================================
void PromptPanel::addListener(Listener* listener)
{
    listeners.add(listener);
}

void PromptPanel::removeListener(Listener* listener)
{
    listeners.remove(listener);
}
