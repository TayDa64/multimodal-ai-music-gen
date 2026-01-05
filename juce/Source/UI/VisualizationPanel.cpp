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
    
    // Create arrangement view (DAW-style multi-track view)
    arrangementView = std::make_unique<UI::ArrangementView>(audioEngine);
    arrangementView->setProjectState(&appState.getProjectState());
    arrangementView->setBPM(appState.getBPM());
    arrangementView->addListener(this);  // Listen for Piano Roll requests from track expand
    addAndMakeVisible(*arrangementView);
    
    // Create piano roll
    pianoRoll = std::make_unique<PianoRollComponent>(audioEngine);
    pianoRoll->addListener(this);
    pianoRoll->setBPM(appState.getBPM());
    pianoRoll->setProjectState(&appState.getProjectState()); // Connect to project state
    addChildComponent(*pianoRoll);  // Hidden by default, Arrange tab is first
    
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
    
    setupTab(arrangeTab, "Arrange", 0);
    setupTab(pianoRollTab, "Piano Roll", 1);
    setupTab(waveformTab, "Waveform", 2);
    setupTab(spectrumTab, "Spectrum", 3);
    setupTab(recentFilesTab, "Files", 4);
    
    // Info label
    infoLabel.setFont(juce::Font(11.0f));
    infoLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    infoLabel.setJustificationType(juce::Justification::centredRight);
    addAndMakeVisible(infoLabel);
    
    // Initialize with Arrange view visible
    currentTab = 0;
    updateTabButtons();
    
    // Sync initial track count to piano roll
    if (pianoRoll && arrangementView)
    {
        int trackCount = arrangementView->getTrackList().getTrackCount();
        pianoRoll->setTrackCount(trackCount);
    }
    
    // Set default theme
    themeManager.setTheme(GenreTheme::defaultTheme());
    updateTheme();
}

VisualizationPanel::~VisualizationPanel()
{
    // Unregister from audio engine
    audioEngine.removeVisualizationListener(this);
    
    if (arrangementView)
        arrangementView->removeListener(this);
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
    
    int tabWidth = 75;
    arrangeTab.setBounds(tabBar.removeFromLeft(tabWidth).reduced(2, 2));
    pianoRollTab.setBounds(tabBar.removeFromLeft(tabWidth).reduced(2, 2));
    waveformTab.setBounds(tabBar.removeFromLeft(tabWidth).reduced(2, 2));
    spectrumTab.setBounds(tabBar.removeFromLeft(tabWidth).reduced(2, 2));
    recentFilesTab.setBounds(tabBar.removeFromLeft(tabWidth).reduced(2, 2));
    
    // Info label on right side of tab bar
    infoLabel.setBounds(tabBar.removeFromRight(200).reduced(4, 2));
    
    // Content area
    auto contentArea = bounds;
    
    if (arrangementView)
        arrangementView->setBounds(contentArea);
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
    DBG("  AppState ProjectState address: " << juce::String::toHexString((juce::pointer_sized_int)&appState.getProjectState()));
    
    if (midiFile.existsAsFile())
    {
        // Load into piano roll (which updates ProjectState)
        if (pianoRoll)
        {
            DBG("  Calling pianoRoll->loadMidiFile...");
            pianoRoll->loadMidiFile(midiFile);
            DBG("  PianoRoll load complete");
        }
        
        // Check notes in ProjectState after import
        auto& ps = appState.getProjectState();
        auto notesNode = ps.getState().getChildWithName(Project::IDs::NOTES);
        DBG("  After import: NOTES node has " << notesNode.getNumChildren() << " children");
        
        // Rebind ArrangementView to pick up new tracks from ProjectState
        if (arrangementView)
        {
            DBG("  Rebinding ArrangementView...");
            arrangementView->setProjectState(&appState.getProjectState());
            DBG("  ArrangementView rebound");
        }
        
        // Switch to Arrange view to show all tracks
        showTab(0);
        DBG("  Switched to Arrange tab");
    }
    else
    {
        DBG("  ERROR: File doesn't exist");
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
    if (arrangementView) arrangementView->setVisible(currentTab == 0);
    if (pianoRoll) pianoRoll->setVisible(currentTab == 1);
    if (waveform) waveform->setVisible(currentTab == 2);
    if (spectrum) spectrum->setVisible(currentTab == 3);
    if (recentFiles) recentFiles->setVisible(currentTab == 4);
    
    // Sync track count when switching to Piano Roll
    if (currentTab == 1 && pianoRoll && arrangementView)
    {
        int trackCount = arrangementView->getTrackList().getTrackCount();
        pianoRoll->setTrackCount(trackCount);
    }
    
    updateTabButtons();
    
    // Update info label based on tab
    switch (currentTab)
    {
        case 0:
            infoLabel.setText("Multi-track arrangement view", juce::dontSendNotification);
            break;
        case 1:
            infoLabel.setText("Hover notes for info", juce::dontSendNotification);
            break;
        case 2:
            infoLabel.setText("Real-time waveform", juce::dontSendNotification);
            break;
        case 3:
            infoLabel.setText("Spectrum analyzer", juce::dontSendNotification);
            break;
        case 4:
            infoLabel.setText("", juce::dontSendNotification);
            break;
    }
    
    repaint();
}

void VisualizationPanel::setBPM(int bpm)
{
    if (pianoRoll)
        pianoRoll->setBPM(bpm);
    if (arrangementView)
        arrangementView->setBPM(bpm);
}

void VisualizationPanel::setGenre(const juce::String& genre)
{
    auto newTheme = GenreTheme::getThemeForGenre(genre);
    themeManager.transitionTo(newTheme, 0.5f);
    updateTheme();
    
    DBG("VisualizationPanel: Set genre theme to " << newTheme.name);
}

void VisualizationPanel::setLoopRegion(double startSeconds, double endSeconds)
{
    if (pianoRoll)
        pianoRoll->setLoopRegion(startSeconds, endSeconds);
}

void VisualizationPanel::clearLoopRegion()
{
    if (pianoRoll)
        pianoRoll->clearLoopRegion();
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
    
    styleTab(arrangeTab, currentTab == 0);
    styleTab(pianoRollTab, currentTab == 1);
    styleTab(waveformTab, currentTab == 2);
    styleTab(spectrumTab, currentTab == 3);
    styleTab(recentFilesTab, currentTab == 4);
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
    // If it's a MIDI file, load it into the piano roll
    // (We handle loading here, not in listeners, to avoid double-loading)
    if (file.hasFileExtension(".mid;.midi"))
    {
        loadMidiFile(file);
    }
    
    // Forward to our listeners AFTER loading so they get the updated state
    listeners.call([&file](Listener& l) { l.fileSelected(file); });
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

void VisualizationPanel::arrangementTrackPianoRollRequested(int trackIndex)
{
    DBG("ArrangementView requested Piano Roll for track " << trackIndex);
    
    // Switch to Piano Roll tab and solo the requested track
    showTab(1);  // Piano Roll is tab 1
    
    if (pianoRoll)
    {
        pianoRoll->soloTrack(trackIndex);
        infoLabel.setText("Editing Track " + juce::String(trackIndex + 1), juce::dontSendNotification);
    }
}

void VisualizationPanel::arrangementRegenerateRequested(int startBar, int endBar, const juce::StringArray& tracks)
{
    DBG("ArrangementView requested regeneration: bars " << startBar << "-" << endBar);
    
    // Forward to MainComponent via listener
    listeners.call([startBar, endBar, &tracks](Listener& l) {
        l.regenerateRequested(startBar, endBar, tracks);
    });
}

void VisualizationPanel::arrangementTrackInstrumentSelected(int trackIndex, const juce::String& instrumentId)
{
    DBG("Track " << trackIndex << " instrument selected: " << instrumentId);
    
    // Forward to MainComponent via listener
    listeners.call([trackIndex, &instrumentId](Listener& l) {
        l.trackInstrumentSelected(trackIndex, instrumentId);
    });
}

void VisualizationPanel::arrangementTrackLoadSF2Requested(int trackIndex)
{
    DBG("Track " << trackIndex << " SF2 load requested");
    listeners.call([trackIndex](Listener& l) {
        l.trackLoadSF2Requested(trackIndex);
    });
}

void VisualizationPanel::arrangementTrackLoadSFZRequested(int trackIndex)
{
    DBG("Track " << trackIndex << " SFZ load requested");
    listeners.call([trackIndex](Listener& l) {
        l.trackLoadSFZRequested(trackIndex);
    });
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
