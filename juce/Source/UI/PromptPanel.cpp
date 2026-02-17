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
    setupHistoryButton();
    setupStatusPanel();
    
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
            listeners.call(&PromptPanel::Listener::generateRequested, getCombinedPrompt());
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
            listeners.call(&PromptPanel::Listener::generateRequested, getCombinedPrompt());
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

    // Takes label
    takesLabel.setText("Takes", juce::dontSendNotification);
    takesLabel.setFont(juce::Font(12.0f));
    takesLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(takesLabel);

    // Takes slider
    takesSlider.setSliderStyle(juce::Slider::LinearHorizontal);
    takesSlider.setTextBoxStyle(juce::Slider::TextBoxRight, false, 60, 20);
    takesSlider.setRange(1, 8, 1);
    takesSlider.setValue(appState.getNumTakes());
    takesSlider.setTextValueSuffix(" takes");
    takesSlider.onValueChange = [this] {
        int takes = (int)takesSlider.getValue();
        appState.setNumTakes(takes);
    };
    addAndMakeVisible(takesSlider);
    
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
            
            // Save to history before generating
            int selectedGenreIdx = genreSelector.getSelectedId() - 1;
            juce::String genreName = "";
            if (selectedGenreIdx >= 0 && selectedGenreIdx < (int)genrePresets.size())
                genreName = genrePresets[selectedGenreIdx].name;
            
            historyManager.addPrompt(
                promptInput.getText(),  // Save main prompt only (not combined)
                genreName,
                appState.getBPM(),
                appState.getKey()
            );
            
            appState.setPrompt(finalPrompt);
            listeners.call(&PromptPanel::Listener::generateRequested, finalPrompt);
        }
    };
    // Enable button even when disconnected - will show error message if clicked
    generateButton.setEnabled(true);
    generateButton.setVisible(true);
    addAndMakeVisible(generateButton);
    
    // Cancel button - only shown during generation
    cancelButton.setColour(juce::TextButton::buttonColourId, AppColours::error);
    cancelButton.onClick = [this] {
        listeners.call(&PromptPanel::Listener::cancelRequested);
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
                                listeners.call(&PromptPanel::Listener::analyzeFileRequested, file);
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

void PromptPanel::setupHistoryButton()
{
    // History button - shows recent prompts dropdown
    historyButton.setColour(juce::TextButton::buttonColourId, AppColours::surface.brighter(0.1f));
    historyButton.setColour(juce::TextButton::textColourOffId, AppColours::textSecondary);
    historyButton.setTooltip("Show recent prompts (favorites and history)");
    historyButton.onClick = [this] {
        showHistoryPopup();
    };
    addAndMakeVisible(historyButton);
}

void PromptPanel::setupStatusPanel()
{
    generationStatusLabel.setText("Generation: Idle", juce::dontSendNotification);
    generationStatusLabel.setFont(juce::Font(12.0f, juce::Font::bold));
    generationStatusLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(generationStatusLabel);

    generationDetailLabel.setText("No request yet", juce::dontSendNotification);
    generationDetailLabel.setFont(juce::Font(11.0f));
    generationDetailLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(generationDetailLabel);
}

void PromptPanel::showHistoryPopup()
{
    // Create popup menu with history items
    juce::PopupMenu menu;
    
    auto prompts = historyManager.getRecentPrompts(15);
    
    if (prompts.empty())
    {
        menu.addItem(-1, "(No prompt history)", false, false);
    }
    else
    {
        // Favorites section
        auto favorites = historyManager.getFavorites();
        if (!favorites.empty())
        {
            menu.addSectionHeader("Favorites");
            for (int i = 0; i < (int)favorites.size() && i < 5; i++)
            {
                juce::String displayText = favorites[i].prompt;
                if (displayText.length() > 50)
                    displayText = displayText.substring(0, 47) + "...";
                
                // Use star emoji for favorites
                menu.addItem(1000 + i, juce::String::fromUTF8("\xe2\x98\x85 ") + displayText);
            }
            menu.addSeparator();
        }
        
        // Recent section
        menu.addSectionHeader("Recent");
        int itemId = 1;
        for (const auto& entry : prompts)
        {
            if (!entry.isFavorite)  // Skip favorites (already shown above)
            {
                juce::String displayText = entry.prompt;
                if (displayText.length() > 50)
                    displayText = displayText.substring(0, 47) + "...";
                
                juce::String metaInfo = " [" + juce::String(entry.bpm) + " BPM";
                if (entry.genre.isNotEmpty())
                    metaInfo += ", " + entry.genre;
                metaInfo += "]";
                
                menu.addItem(itemId, displayText + metaInfo);
                itemId++;
                
                if (itemId > 10) break;  // Limit non-favorites shown
            }
        }
        
        menu.addSeparator();
        menu.addItem(-2, "Clear History...", historyManager.getHistorySize() > historyManager.getFavoritesCount());
    }
    
    menu.showMenuAsync(juce::PopupMenu::Options()
        .withTargetComponent(&historyButton)
        .withMinimumWidth(300),
        [this, prompts](int result) {
            if (result > 0)
            {
                // Find and apply the selected prompt
                const PromptEntry* selected = nullptr;
                
                if (result >= 1000)
                {
                    // Favorite was selected
                    auto favorites = historyManager.getFavorites();
                    int favIndex = result - 1000;
                    if (favIndex < (int)favorites.size())
                        selected = &favorites[favIndex];
                }
                else
                {
                    // Recent was selected
                    int nonFavIndex = 0;
                    for (const auto& entry : prompts)
                    {
                        if (!entry.isFavorite)
                        {
                            nonFavIndex++;
                            if (nonFavIndex == result)
                            {
                                selected = &entry;
                                break;
                            }
                        }
                    }
                }
                
                if (selected)
                {
                    promptSelected(*selected);
                }
            }
            else if (result == -2)
            {
                // Clear history
                juce::AlertWindow::showOkCancelBox(
                    juce::MessageBoxIconType::QuestionIcon,
                    "Clear History",
                    "Clear all prompt history? Favorites will be kept.",
                    "Clear", "Cancel", this,
                    juce::ModalCallbackFunction::create([this](int r) {
                        if (r == 1)
                            historyManager.clearHistory();
                    }));
            }
        });
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
    // Reserve: negative prompt label (18) + input (26) + gap +
    //          duration row (26) + takes row (26) + gap + button row (34)
    //          + status row (22) + margins
    int reservedHeight = 18 + 26 + 10 + 26 + 26 + 10 + 34 + 22 + Layout::paddingMD * 3;
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

    // Takes row
    auto takesRow = bounds.removeFromTop(26);
    juce::FlexBox takesFlex = Layout::createRowFlex();
    takesFlex.items.add(juce::FlexItem(takesLabel).withWidth(60.0f).withHeight(26.0f));
    takesFlex.items.add(juce::FlexItem(takesSlider).withFlex(1.0f).withHeight(26.0f));
    takesFlex.performLayout(takesRow);

    bounds.removeFromTop(Layout::paddingMD);
    
    // Button row - Generate + History + Analyze buttons using FlexBox
    auto buttonRow = bounds.removeFromTop(Layout::buttonHeightLG);
    int generateWidth = juce::jmin(120, (buttonRow.getWidth() - Layout::paddingMD * 2) / 3);
    int historyWidth = juce::jmin(80, (buttonRow.getWidth() - Layout::paddingMD * 2) / 3);
    int analyzeWidth = juce::jmin(140, (buttonRow.getWidth() - Layout::paddingMD * 2) / 3);
    
    juce::FlexBox buttonFlex = Layout::createRowFlex(juce::FlexBox::JustifyContent::center);
    buttonFlex.items.add(juce::FlexItem(generateButton).withWidth((float)generateWidth).withHeight((float)Layout::buttonHeightMD));
    buttonFlex.items.add(juce::FlexItem().withWidth((float)Layout::paddingSM)); // Spacer
    buttonFlex.items.add(juce::FlexItem(historyButton).withWidth((float)historyWidth).withHeight((float)Layout::buttonHeightMD));
    buttonFlex.items.add(juce::FlexItem().withWidth((float)Layout::paddingSM)); // Spacer
    buttonFlex.items.add(juce::FlexItem(analyzeButton).withWidth((float)analyzeWidth).withHeight((float)Layout::buttonHeightMD));
    buttonFlex.performLayout(buttonRow);
    
    // Cancel button shares position with generate button
    cancelButton.setBounds(generateButton.getBounds());

    bounds.removeFromTop(Layout::paddingSM);

    // Status row
    auto statusRow = bounds.removeFromTop(22);
    auto statusLeft = statusRow.removeFromLeft(140);
    generationStatusLabel.setBounds(statusLeft);
    generationDetailLabel.setBounds(statusRow);
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
void PromptPanel::promptSelected(const PromptEntry& entry)
{
    // Apply the selected prompt to the input fields
    setPromptText(entry.prompt);
    
    // Update app state with the stored parameters
    if (entry.bpm > 0)
        appState.setBPM(entry.bpm);
    
    if (entry.key.isNotEmpty())
        appState.setKey(entry.key);
    
    // Note: Genre is handled separately by the main GenreSelector
    // We could emit a signal to update it, but for now just apply prompt
    
    DBG("Prompt selected from history: " + entry.prompt);
}

//==============================================================================
void PromptPanel::onGenerationStarted()
{
    juce::MessageManager::callAsync([this] {
        isGenerating = true;
        hasAck = false;
        generateButton.setVisible(false);
        cancelButton.setVisible(true);
        promptInput.setEnabled(false);
        negativePromptInput.setEnabled(false);
        genreSelector.setEnabled(false);
        durationSlider.setEnabled(false);
        updateGenerationStatus("Request sent", "Waiting for server response...");
    });
}

void PromptPanel::onGenerationProgress(const GenerationProgress& progress)
{
    lastProgress = progress;
    if (!hasAck)
    {
        hasAck = true;
        updateGenerationStatus("Ack received", progress.message.isNotEmpty() ? progress.message : "Generation started");
        return;
    }

    juce::String detail = progress.stepName;
    if (progress.progress > 0.0f)
    {
        detail += " (" + juce::String((int)(progress.progress * 100.0f)) + "%)";
    }
    if (progress.message.isNotEmpty())
    {
        detail += " - " + progress.message;
    }
    updateGenerationStatus("Generating", detail);
}

void PromptPanel::onGenerationCompleted(const juce::File& outputFile)
{
    juce::MessageManager::callAsync([this, outputFile] {
        DBG("PromptPanel::onGenerationCompleted - resetting UI state");
        isGenerating = false;
        juce::String detail = outputFile.existsAsFile()
            ? ("Saved: " + outputFile.getFileName())
            : "Generation finished";
        updateGenerationStatus("Complete", detail);
        
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

void PromptPanel::onGenerationError(const juce::String& error)
{
    juce::MessageManager::callAsync([this, error] {
        DBG("PromptPanel::onGenerationError - resetting UI state");
        isGenerating = false;
        juce::String detail = error.isNotEmpty() ? error : "Generation failed or cancelled";
        updateGenerationStatus("Error", detail);
        
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
        if (!connected && !isGenerating)
        {
            updateGenerationStatus("Offline", "Server not connected");
        }
    });
}

void PromptPanel::updateGenerationStatus(const juce::String& status, const juce::String& detail)
{
    juce::MessageManager::callAsync([this, status, detail] {
        generationStatusLabel.setText("Generation: " + status, juce::dontSendNotification);
        generationDetailLabel.setText(detail.isNotEmpty() ? detail : " ", juce::dontSendNotification);
        if (status == "Error")
        {
            generationStatusLabel.setColour(juce::Label::textColourId, AppColours::error);
        }
        else if (status == "Complete")
        {
            generationStatusLabel.setColour(juce::Label::textColourId, AppColours::success);
        }
        else
        {
            generationStatusLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
        }
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
            listeners.call(&PromptPanel::Listener::analyzeFileRequested, file);
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
                    listeners.call(&PromptPanel::Listener::analyzeUrlRequested, url);
                }
            }
            delete dialog;
        }), true);
}
