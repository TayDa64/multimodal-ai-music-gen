/*
  ==============================================================================

    VisualizationPanel.cpp
    
    Implementation of the tabbed visualization panel.
    Phase 6: Piano Roll Visualization
    Phase 7: Waveform & Spectrum Visualization

  ==============================================================================
*/

#include "VisualizationPanel.h"
#include "Theme/ColourScheme.h"

//==============================================================================
VisualizationPanel::VisualizationPanel(AppState& state, mmg::AudioEngine& engine)
    : appState(state),
      audioEngine(engine)
{
    DBG("VisualizationPanel constructor - Phase 7 with Waveform & Spectrum");
    
    // Create piano roll
    pianoRoll = std::make_unique<PianoRollComponent>(audioEngine);
    pianoRoll->addListener(this);
    pianoRoll->setBPM(appState.getBPM());
    pianoRoll->setProjectState(&appState.getProjectState()); // Connect to project state
    addAndMakeVisible(*pianoRoll);
    
    // Create waveform visualizer
    waveform = std::make_unique<WaveformComponent>();
    waveform->setDisplayMode(WaveformComponent::DisplayMode::Filled);
    addChildComponent(*waveform);
    
    // Create spectrum analyzer
    spectrum = std::make_unique<SpectrumComponent>();
    spectrum->setDisplayMode(SpectrumComponent::DisplayMode::Glow);
    spectrum->setFrequencyScale(SpectrumComponent::FrequencyScale::Logarithmic);
    addChildComponent(*spectrum);
    
    // Create recent files panel
    recentFiles = std::make_unique<RecentFilesPanel>(appState, audioEngine);
    recentFiles->addListener(this);
    addChildComponent(*recentFiles);
    
    // Register for audio samples
    audioEngine.addVisualizationListener(this);
    
    // Setup tab buttons
    auto setupTab = [this](juce::TextButton& tab, const juce::String& name, int index) {
        tab.setButtonText(name);
        tab.setClickingTogglesState(false);
        tab.setColour(juce::TextButton::buttonColourId, AppColours::surfaceAlt);
        tab.setColour(juce::TextButton::textColourOnId, AppColours::textPrimary);
        tab.setColour(juce::TextButton::textColourOffId, AppColours::textSecondary);
        tab.onClick = [this, index]() { showTab(index); };
        addAndMakeVisible(tab);
    };
    
    setupTab(pianoRollTab, "Piano Roll", 0);
    setupTab(waveformTab, "Waveform", 1);
    setupTab(spectrumTab, "Spectrum", 2);
    setupTab(recentFilesTab, "Files", 3);
    
    // Info label
    infoLabel.setFont(juce::Font(11.0f));
    infoLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    infoLabel.setJustificationType(juce::Justification::centredRight);
    addAndMakeVisible(infoLabel);
    
    // Initialize with piano roll visible
    currentTab = 0;
    updateTabButtons();
    
    // Set default theme
    themeManager.setTheme(GenreTheme::defaultTheme());
    updateTheme();
}

VisualizationPanel::~VisualizationPanel()
{
    // Unregister from audio engine
    audioEngine.removeVisualizationListener(this);
    
    if (pianoRoll)
        pianoRoll->removeListener(this);
    if (recentFiles)
        recentFiles->removeListener(this);
}

//==============================================================================
void VisualizationPanel::paint(juce::Graphics& g)
{
    // Background
    g.fillAll(AppColours::surface);
    
    // Tab bar background
    auto tabBar = getLocalBounds().removeFromTop(tabHeight);
    g.setColour(AppColours::surfaceAlt);
    g.fillRect(tabBar);
    
    // Border below tabs
    g.setColour(AppColours::border);
    g.drawHorizontalLine(tabHeight - 1, 0.0f, (float)getWidth());
}

void VisualizationPanel::resized()
{
    auto bounds = getLocalBounds();
    
    // Tab bar
    auto tabBar = bounds.removeFromTop(tabHeight);
    
    int tabWidth = 85;
    pianoRollTab.setBounds(tabBar.removeFromLeft(tabWidth).reduced(2, 2));
    waveformTab.setBounds(tabBar.removeFromLeft(tabWidth).reduced(2, 2));
    spectrumTab.setBounds(tabBar.removeFromLeft(tabWidth).reduced(2, 2));
    recentFilesTab.setBounds(tabBar.removeFromLeft(tabWidth).reduced(2, 2));
    
    // Info label on right side of tab bar
    infoLabel.setBounds(tabBar.removeFromRight(200).reduced(4, 2));
    
    // Content area
    auto contentArea = bounds;
    
    if (pianoRoll)
        pianoRoll->setBounds(contentArea);
    if (waveform)
        waveform->setBounds(contentArea);
    if (spectrum)
        spectrum->setBounds(contentArea);
    if (recentFiles)
        recentFiles->setBounds(contentArea);
}

//==============================================================================
void VisualizationPanel::loadMidiFile(const juce::File& midiFile)
{
    DBG("VisualizationPanel::loadMidiFile: " << midiFile.getFullPathName());
    
    if (pianoRoll && midiFile.existsAsFile())
    {
        pianoRoll->loadMidiFile(midiFile);
        showTab(0);  // Switch to piano roll when loading MIDI
        DBG("  Switched to piano roll tab");
    }
    else
    {
        DBG("  ERROR: pianoRoll is null or file doesn't exist");
    }
}

void VisualizationPanel::setOutputDirectory(const juce::File& directory)
{
    if (recentFiles)
        recentFiles->setOutputDirectory(directory);
}

void VisualizationPanel::refreshRecentFiles()
{
    if (recentFiles)
        recentFiles->refresh();
}

void VisualizationPanel::showTab(int index)
{
    DBG("VisualizationPanel::showTab(" << index << ")");
    currentTab = juce::jlimit(0, numTabs - 1, index);
    
    // Update visibility
    if (pianoRoll) pianoRoll->setVisible(currentTab == 0);
    if (waveform) waveform->setVisible(currentTab == 1);
    if (spectrum) spectrum->setVisible(currentTab == 2);
    if (recentFiles) recentFiles->setVisible(currentTab == 3);
    
    updateTabButtons();
    
    // Update info label based on tab
    switch (currentTab)
    {
        case 0:
            infoLabel.setText("Hover notes for info", juce::dontSendNotification);
            break;
        case 1:
            infoLabel.setText("Real-time waveform", juce::dontSendNotification);
            break;
        case 2:
            infoLabel.setText("Spectrum analyzer", juce::dontSendNotification);
            break;
        case 3:
            infoLabel.setText("", juce::dontSendNotification);
            break;
    }
    
    repaint();
}

void VisualizationPanel::setBPM(int bpm)
{
    if (pianoRoll)
        pianoRoll->setBPM(bpm);
}

void VisualizationPanel::setGenre(const juce::String& genre)
{
    auto newTheme = GenreTheme::getThemeForGenre(genre);
    themeManager.transitionTo(newTheme, 0.5f);
    updateTheme();
    
    DBG("VisualizationPanel: Set genre theme to " << newTheme.name);
}

void VisualizationPanel::updateTabButtons()
{
    juce::Colour activeColour = AppColours::primary;
    juce::Colour inactiveColour = AppColours::surfaceAlt.darker(0.1f);
    juce::Colour activeTextColour = juce::Colours::white;
    juce::Colour inactiveTextColour = AppColours::textSecondary;
    
    auto styleTab = [&](juce::TextButton& tab, bool isActive) {
        tab.setColour(juce::TextButton::buttonColourId, 
                      isActive ? activeColour : inactiveColour);
        tab.setColour(juce::TextButton::textColourOnId, 
                      isActive ? activeTextColour : inactiveTextColour);
        tab.setColour(juce::TextButton::textColourOffId, 
                      isActive ? activeTextColour : inactiveTextColour);
        tab.repaint();
    };
    
    styleTab(pianoRollTab, currentTab == 0);
    styleTab(waveformTab, currentTab == 1);
    styleTab(spectrumTab, currentTab == 2);
    styleTab(recentFilesTab, currentTab == 3);
}

void VisualizationPanel::updateTheme()
{
    const auto& theme = themeManager.getTheme();
    
    if (waveform)
        waveform->setTheme(theme);
    if (spectrum)
        spectrum->setTheme(theme);
}

//==============================================================================
void VisualizationPanel::audioSamplesReady(const float* leftSamples, 
                                            const float* rightSamples, 
                                            int numSamples)
{
    // Called from audio thread - forward to visualizers
    if (waveform)
        waveform->pushSamples(leftSamples, rightSamples, numSamples);
    if (spectrum)
        spectrum->pushSamples(leftSamples, rightSamples, numSamples);
}

//==============================================================================
void VisualizationPanel::fileSelected(const juce::File& file)
{
    // Forward to our listeners
    listeners.call([&file](Listener& l) { l.fileSelected(file); });
    
    // If it's a MIDI file, also load it into the piano roll
    if (file.hasFileExtension(".mid;.midi"))
    {
        loadMidiFile(file);
    }
}

void VisualizationPanel::analyzeFileRequested(const juce::File& file)
{
    // Forward to our listeners
    listeners.call([&file](Listener& l) { l.analyzeFileRequested(file); });
}

void VisualizationPanel::pianoRollNoteHovered(const MidiNoteEvent* note)
{
    if (currentTab == 0)
    {
        if (note != nullptr)
        {
            juce::String info = MidiNoteEvent::getNoteName(note->noteNumber);
            info += " | Vel: " + juce::String(note->velocity);
            info += " | Track " + juce::String(note->trackIndex + 1);
            infoLabel.setText(info, juce::dontSendNotification);
        }
        else
        {
            infoLabel.setText("Hover notes for info", juce::dontSendNotification);
        }
    }
}

void VisualizationPanel::pianoRollSeekRequested(double positionSeconds)
{
    DBG("Piano roll seek to: " << positionSeconds << "s");
}

//==============================================================================
void VisualizationPanel::addListener(Listener* listener)
{
    listeners.add(listener);
}

void VisualizationPanel::removeListener(Listener* listener)
{
    listeners.remove(listener);
}
