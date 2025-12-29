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
    setupNegativePromptInput();
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
    promptInput.setTextToShowWhenEmpty("Describe the music you want to generate (genre, mood, instruments, BPM)...", 
                                       AppColours::textSecondary);
    promptInput.setFont(juce::Font(14.0f));
    
    // Handle Enter key to generate
    promptInput.onReturnKey = [this] {
        if (!isGenerating && isConnected && promptInput.getText().isNotEmpty())
        {
            listeners.call(&Listener::generateRequested, getCombinedPrompt());
        }
    };
    
    addAndMakeVisible(promptInput);
}

void PromptPanel::setupNegativePromptInput()
{
    // Label with muted styling
    negativePromptLabel.setText("Exclude (optional)", juce::dontSendNotification);
    negativePromptLabel.setFont(juce::Font(12.0f));
    negativePromptLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(negativePromptLabel);
    
    // Compact text editor for negative prompt
    negativePromptInput.setMultiLine(false);
    negativePromptInput.setReturnKeyStartsNewLine(false);
    negativePromptInput.setScrollbarsShown(false);
    negativePromptInput.setPopupMenuEnabled(true);
    negativePromptInput.setTextToShowWhenEmpty("e.g. rolling notes, hi-hat rolls, 808...", 
                                               AppColours::textSecondary.withAlpha(0.6f));
    negativePromptInput.setFont(juce::Font(13.0f));
    
    // Slightly darker background to differentiate from main prompt
    negativePromptInput.setColour(juce::TextEditor::backgroundColourId, 
                                  AppColours::surface.darker(0.15f));
    
    // Handle Enter key - also triggers generate
    negativePromptInput.onReturnKey = [this] {
        if (!isGenerating && isConnected && promptInput.getText().isNotEmpty())
        {
            listeners.call(&Listener::generateRequested, getCombinedPrompt());
        }
    };
    
    addAndMakeVisible(negativePromptInput);
}

void PromptPanel::setupGenreSelector()
{
    // Genre selection is now handled by the main GenreSelector component
    // This section is hidden but kept for potential future use
    genreLabel.setText("Genre", juce::dontSendNotification);
    genreLabel.setFont(juce::Font(12.0f));
    genreLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    genreLabel.setVisible(false);  // Hidden - using main GenreSelector
    addAndMakeVisible(genreLabel);
    
    // Setup genre presets (kept for internal use but combo box hidden)
    genrePresets = {
        { "G-Funk",     "",    92 },   // Empty suffix - genre set via GenreSelector
        { "Trap",       "",    140 },
        { "Boom Bap",   "",    90 },
        { "Lo-Fi",      "",    85 },
        { "Drill",      "",    140 },
        { "RnB",        "",    100 },
        { "Jazz Hop",   "",    88 },
        { "Custom",     "",    100 }
    };
    
    // Populate combo box but keep it hidden
    for (int i = 0; i < (int)genrePresets.size(); ++i)
    {
        genreSelector.addItem(genrePresets[i].name, i + 1);
    }
    
    genreSelector.setSelectedId(1);
    genreSelector.setVisible(false);  // Hidden - using main GenreSelector
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
            // Use combined prompt (main + negative) - genre is passed separately via GenreSelector
            juce::String finalPrompt = getCombinedPrompt();
            
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
    promptLabel.setBounds(bounds.removeFromTop(20));
    bounds.removeFromTop(4);
    
    // Prompt input (main area - takes proportionally more space)
    auto availableHeight = bounds.getHeight() - 140; // Reserve space for other controls
    auto mainPromptHeight = juce::jmax(50, (int)(availableHeight * 0.75f));
    promptInput.setBounds(bounds.removeFromTop(mainPromptHeight));
    bounds.removeFromTop(8);
    
    // Negative prompt section (smaller, single line)
    negativePromptLabel.setBounds(bounds.removeFromTop(18));
    bounds.removeFromTop(2);
    negativePromptInput.setBounds(bounds.removeFromTop(26));
    bounds.removeFromTop(10);
    
    // Genre row - hidden (using main GenreSelector)
    // Skip layout for genre controls
    
    // Duration row (separate line for clarity)
    auto durationRow = bounds.removeFromTop(26);
    durationLabel.setBounds(durationRow.removeFromLeft(60).withHeight(26));
    durationSlider.setBounds(durationRow.withHeight(26)); // Takes remaining width
    
    bounds.removeFromTop(10);
    
    // Generate button row
    auto buttonRow = bounds.removeFromTop(34);
    auto buttonWidth = 140;
    
    // Center the button
    auto buttonX = (buttonRow.getWidth() - buttonWidth) / 2;
    generateButton.setBounds(buttonRow.withX(buttonRow.getX() + buttonX).withWidth(buttonWidth).withHeight(30));
    cancelButton.setBounds(generateButton.getBounds());
}

//==============================================================================
juce::String PromptPanel::getPromptText() const
{
    return promptInput.getText();
}

juce::String PromptPanel::getNegativePromptText() const
{
    return negativePromptInput.getText();
}

juce::String PromptPanel::getCombinedPrompt() const
{
    juce::String combined = promptInput.getText();
    juce::String negative = negativePromptInput.getText().trim();
    
    // Only append negative prompt section if user entered something
    if (negative.isNotEmpty())
    {
        // Use the established "negative prompt:" syntax for Python backend
        combined += " negative prompt: " + negative;
    }
    
    return combined;
}

void PromptPanel::setPromptText(const juce::String& text)
{
    promptInput.setText(text);
}

void PromptPanel::setNegativePromptText(const juce::String& text)
{
    negativePromptInput.setText(text);
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
        negativePromptInput.setEnabled(false);
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
        negativePromptInput.setEnabled(true);
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
        negativePromptInput.setEnabled(true);
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
