/*
  ==============================================================================

    PromptPanel.cpp
    
    Implementation of prompt input panel.

  ==============================================================================
*/

#include "PromptPanel.h"
#include "Theme/ColourScheme.h"
#include "Theme/LayoutConstants.h"

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
    
    // Analyze Reference button - opens file chooser or URL dialog
    analyzeButton.setColour(juce::TextButton::buttonColourId, AppColours::surface.brighter(0.1f));
    analyzeButton.setColour(juce::TextButton::textColourOffId, AppColours::textSecondary);
    analyzeButton.setTooltip("Analyze a reference audio file or URL to extract BPM, key, and prompt hints");
    analyzeButton.onClick = [this] {
        // Show popup menu with File/URL options
        juce::PopupMenu menu;
        menu.addItem(1, "Analyze Local File...");
        menu.addItem(2, "Analyze URL...");
        menu.addSeparator();
        menu.addItem(3, "Drop audio file here", false, false); // Hint item, disabled
        
        menu.showMenuAsync(juce::PopupMenu::Options()
            .withTargetComponent(&analyzeButton),
            [this](int result) {
                if (result == 1) {
                    // Open file chooser
                    auto chooser = std::make_unique<juce::FileChooser>(
                        "Select Audio File to Analyze",
                        juce::File::getSpecialLocation(juce::File::userMusicDirectory),
                        "*.wav;*.mp3;*.flac;*.aiff;*.ogg;*.m4a;*.mid;*.midi");
                    
                    chooser->launchAsync(juce::FileBrowserComponent::openMode | 
                                        juce::FileBrowserComponent::canSelectFiles,
                        [this](const juce::FileChooser& fc) {
                            auto file = fc.getResult();
                            if (file.existsAsFile()) {
                                listeners.call(&Listener::analyzeFileRequested, file);
                            }
                        });
                    // Keep chooser alive until dialog closes
                    juce::MessageManager::callAsync([c = std::move(chooser)]() mutable { c.reset(); });
                }
                else if (result == 2) {
                    showAnalyzeUrlDialog();
                }
            });
    };
    addAndMakeVisible(analyzeButton);
}

//==============================================================================
void PromptPanel::paint(juce::Graphics& g)
{
    // Background
    g.setColour(AppColours::surface);
    g.fillRoundedRectangle(getLocalBounds().toFloat(), 8.0f);
    
    // Border - highlight when dragging audio file over
    if (isDragOver)
    {
        g.setColour(AppColours::accent);
        g.drawRoundedRectangle(getLocalBounds().toFloat().reduced(1.5f), 8.0f, 3.0f);
        
        // Draw drop hint overlay
        g.setColour(AppColours::accent.withAlpha(0.1f));
        g.fillRoundedRectangle(getLocalBounds().toFloat().reduced(2.0f), 8.0f);
        
        // Drop hint text
        g.setColour(AppColours::accent);
        g.setFont(juce::Font(16.0f, juce::Font::bold));
        g.drawText("Drop audio file to analyze", getLocalBounds(), juce::Justification::centred);
    }
    else
    {
        g.setColour(AppColours::border);
        g.drawRoundedRectangle(getLocalBounds().toFloat().reduced(0.5f), 8.0f, 1.0f);
    }
}

void PromptPanel::resized()
{
    auto bounds = getLocalBounds().reduced(Layout::paddingXL);
    const int windowHeight = getParentHeight();
    
    // Use FlexBox for vertical layout to handle variable heights gracefully
    juce::FlexBox mainFlex = Layout::createColumnFlex();
    mainFlex.justifyContent = juce::FlexBox::JustifyContent::flexStart;
    
    // Title row (fixed height)
    auto titleRow = bounds.removeFromTop(20);
    promptLabel.setBounds(titleRow);
    bounds.removeFromTop(Layout::paddingSM);
    
    // Calculate available height for prompt input
    // Reserve: negative prompt label (18) + input (26) + gap (10) + 
    //          duration row (26) + gap (10) + button row (34) + margins
    int reservedHeight = 18 + 26 + 10 + 26 + 10 + 34 + Layout::paddingMD * 3;
    int availableForPrompt = bounds.getHeight() - reservedHeight;
    
    // Prompt input - use more space on taller windows
    int promptHeight = juce::jmax(50, availableForPrompt);
    promptInput.setBounds(bounds.removeFromTop(promptHeight));
    bounds.removeFromTop(Layout::paddingMD);
    
    // Negative prompt section
    negativePromptLabel.setBounds(bounds.removeFromTop(18));
    bounds.removeFromTop(2);
    negativePromptInput.setBounds(bounds.removeFromTop(26));
    bounds.removeFromTop(Layout::paddingMD);
    
    // Duration row using FlexBox for responsive spacing
    auto durationRow = bounds.removeFromTop(26);
    
    juce::FlexBox durationFlex = Layout::createRowFlex();
    durationFlex.items.add(juce::FlexItem(durationLabel).withWidth(60.0f).withHeight(26.0f));
    durationFlex.items.add(juce::FlexItem(durationSlider).withFlex(1.0f).withHeight(26.0f));
    durationFlex.performLayout(durationRow);
    
    bounds.removeFromTop(Layout::paddingMD);
    
    // Button row - Generate + Analyze buttons using FlexBox
    auto buttonRow = bounds.removeFromTop(Layout::buttonHeightLG);
    int generateWidth = juce::jmin(140, (buttonRow.getWidth() - Layout::paddingMD) / 2);
    int analyzeWidth = juce::jmin(160, (buttonRow.getWidth() - Layout::paddingMD) / 2);
    
    juce::FlexBox buttonFlex = Layout::createRowFlex(juce::FlexBox::JustifyContent::center);
    buttonFlex.items.add(juce::FlexItem(generateButton).withWidth((float)generateWidth).withHeight((float)Layout::buttonHeightMD));
    buttonFlex.items.add(juce::FlexItem().withWidth((float)Layout::paddingMD)); // Spacer
    buttonFlex.items.add(juce::FlexItem(analyzeButton).withWidth((float)analyzeWidth).withHeight((float)Layout::buttonHeightMD));
    buttonFlex.performLayout(buttonRow);
    
    // Cancel button shares position with generate button
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

void PromptPanel::appendToPrompt(const juce::String& text)
{
    juce::String current = promptInput.getText();
    if (current.isNotEmpty() && !current.endsWithChar(' '))
        current += " ";
    promptInput.setText(current + text);
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

//==============================================================================
// FileDragAndDropTarget implementation
bool PromptPanel::isInterestedInFileDrag(const juce::StringArray& files)
{
    // Accept drag if any file is an audio/MIDI file
    for (const auto& path : files)
    {
        juce::File file(path);
        if (isAudioFile(file))
            return true;
    }
    return false;
}

void PromptPanel::fileDragEnter(const juce::StringArray& /*files*/, int /*x*/, int /*y*/)
{
    isDragOver = true;
    repaint();
}

void PromptPanel::fileDragExit(const juce::StringArray& /*files*/)
{
    isDragOver = false;
    repaint();
}

void PromptPanel::filesDropped(const juce::StringArray& files, int /*x*/, int /*y*/)
{
    isDragOver = false;
    repaint();
    
    // Analyze the first valid audio file
    for (const auto& path : files)
    {
        juce::File file(path);
        if (isAudioFile(file) && file.existsAsFile())
        {
            listeners.call(&Listener::analyzeFileRequested, file);
            break;
        }
    }
}

bool PromptPanel::isAudioFile(const juce::File& file) const
{
    auto ext = file.getFileExtension().toLowerCase();
    return ext == ".wav" || ext == ".mp3" || ext == ".flac" || 
           ext == ".aiff" || ext == ".aif" || ext == ".ogg" || 
           ext == ".m4a" || ext == ".mid" || ext == ".midi";
}

void PromptPanel::showAnalyzeUrlDialog()
{
    auto* dialog = new juce::AlertWindow("Analyze URL", 
        "Enter a URL to analyze (YouTube, SoundCloud, etc.)",
        juce::MessageBoxIconType::QuestionIcon);
    
    dialog->addTextEditor("url", "", "URL:");
    dialog->addButton("Analyze", 1, juce::KeyPress(juce::KeyPress::returnKey));
    dialog->addButton("Cancel", 0, juce::KeyPress(juce::KeyPress::escapeKey));
    
    dialog->enterModalState(true, juce::ModalCallbackFunction::create(
        [this, dialog](int result) {
            if (result == 1)
            {
                auto url = dialog->getTextEditorContents("url").trim();
                if (url.isNotEmpty())
                {
                    listeners.call(&Listener::analyzeUrlRequested, url);
                }
            }
            delete dialog;
        }), true);
}
