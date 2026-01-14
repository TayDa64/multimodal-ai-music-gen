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

    // Default synth controls (shown when a track uses "Default (Sine)")
    defaultSynthGroup.setText("Default Synth");
    defaultSynthGroup.setColour(juce::GroupComponent::textColourId, AppColours::textSecondary);
    defaultSynthGroup.setColour(juce::GroupComponent::outlineColourId, AppColours::border);
    addAndMakeVisible(defaultSynthGroup);

    defaultSynthTitle.setFont(juce::Font(11.0f).boldened());
    defaultSynthTitle.setColour(juce::Label::textColourId, AppColours::textPrimary);
    defaultSynthTitle.setJustificationType(juce::Justification::centredLeft);
    addAndMakeVisible(defaultSynthTitle);

    defaultSynthWaveformLabel.setText("Wave", juce::dontSendNotification);
    defaultSynthWaveformLabel.setFont(juce::Font(10.0f));
    defaultSynthWaveformLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(defaultSynthWaveformLabel);

    defaultSynthWaveform.addItem("Sine", 1);
    defaultSynthWaveform.addItem("Triangle", 2);
    defaultSynthWaveform.addItem("Saw", 3);
    defaultSynthWaveform.addItem("Square", 4);
    defaultSynthWaveform.setSelectedId(1, juce::dontSendNotification);
    defaultSynthWaveform.onChange = [this]() {
        if (isUpdatingDefaultSynthControls)
            return;

        const auto wf = defaultSynthWaveform.getSelectedId();
        if (wf <= 0)
            return;

        mmg::AudioEngine::DefaultSynthWaveform waveformEnum = mmg::AudioEngine::DefaultSynthWaveform::Sine;
        switch (wf)
        {
            case 1: waveformEnum = mmg::AudioEngine::DefaultSynthWaveform::Sine; break;
            case 2: waveformEnum = mmg::AudioEngine::DefaultSynthWaveform::Triangle; break;
            case 3: waveformEnum = mmg::AudioEngine::DefaultSynthWaveform::Saw; break;
            case 4: waveformEnum = mmg::AudioEngine::DefaultSynthWaveform::Square; break;
            default: break;
        }

        audioEngine.setTrackDefaultSynthWaveform(selectedTrackIndex, waveformEnum);
        persistDefaultSynthControlToProject(selectedTrackIndex, Project::IDs::defaultSynthWaveform, wf);
    };
    defaultSynthWaveform.setColour(juce::ComboBox::backgroundColourId, AppColours::inputBg);
    defaultSynthWaveform.setColour(juce::ComboBox::textColourId, AppColours::textPrimary);
    defaultSynthWaveform.setColour(juce::ComboBox::outlineColourId, AppColours::inputBorder);
    defaultSynthWaveform.setColour(juce::ComboBox::arrowColourId, AppColours::textSecondary);
    addAndMakeVisible(defaultSynthWaveform);

    auto setupSlider = [](juce::Slider& s, double min, double max, double step, const juce::String& suffix) {
        s.setSliderStyle(juce::Slider::LinearHorizontal);
        s.setTextBoxStyle(juce::Slider::TextBoxRight, false, 64, 18);
        s.setRange(min, max, step);
        s.setTextValueSuffix(suffix);

        // Ensure the control is visible and usable in the app's dark theme.
        s.setColour(juce::Slider::trackColourId, AppColours::primary.withAlpha(0.60f));
        s.setColour(juce::Slider::thumbColourId, AppColours::primaryLight);
        s.setColour(juce::Slider::backgroundColourId, AppColours::surfaceAlt);
        s.setColour(juce::Slider::textBoxTextColourId, AppColours::textPrimary);
        s.setColour(juce::Slider::textBoxBackgroundColourId, AppColours::inputBg);
        s.setColour(juce::Slider::textBoxOutlineColourId, AppColours::inputBorder);
    };

    defaultSynthAttackLabel.setText("Attack", juce::dontSendNotification);
    defaultSynthAttackLabel.setFont(juce::Font(10.0f));
    defaultSynthAttackLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(defaultSynthAttackLabel);
    setupSlider(defaultSynthAttack, 0.001, 2.0, 0.001, " s");
    defaultSynthAttack.setValue(0.001, juce::dontSendNotification);
    defaultSynthAttack.onValueChange = [this]() {
        if (isUpdatingDefaultSynthControls)
            return;
        audioEngine.setTrackDefaultSynthParam(selectedTrackIndex,
                                              mmg::AudioEngine::DefaultSynthParam::AttackSeconds,
                                              (float)defaultSynthAttack.getValue());
        persistDefaultSynthControlToProject(selectedTrackIndex, Project::IDs::defaultSynthAttack, (float)defaultSynthAttack.getValue());
    };
    addAndMakeVisible(defaultSynthAttack);

    defaultSynthReleaseLabel.setText("Release", juce::dontSendNotification);
    defaultSynthReleaseLabel.setFont(juce::Font(10.0f));
    defaultSynthReleaseLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(defaultSynthReleaseLabel);
    setupSlider(defaultSynthRelease, 0.01, 5.0, 0.001, " s");
    defaultSynthRelease.setValue(0.2, juce::dontSendNotification);
    defaultSynthRelease.onValueChange = [this]() {
        if (isUpdatingDefaultSynthControls)
            return;
        audioEngine.setTrackDefaultSynthParam(selectedTrackIndex,
                                              mmg::AudioEngine::DefaultSynthParam::ReleaseSeconds,
                                              (float)defaultSynthRelease.getValue());
        persistDefaultSynthControlToProject(selectedTrackIndex, Project::IDs::defaultSynthRelease, (float)defaultSynthRelease.getValue());
    };
    addAndMakeVisible(defaultSynthRelease);

    defaultSynthCutoffLabel.setText("Cutoff", juce::dontSendNotification);
    defaultSynthCutoffLabel.setFont(juce::Font(10.0f));
    defaultSynthCutoffLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(defaultSynthCutoffLabel);
    setupSlider(defaultSynthCutoff, 50.0, 20000.0, 1.0, " Hz");
    defaultSynthCutoff.setSkewFactorFromMidPoint(1500.0);
    defaultSynthCutoff.setValue(16000.0, juce::dontSendNotification);
    defaultSynthCutoff.onValueChange = [this]() {
        if (isUpdatingDefaultSynthControls)
            return;
        audioEngine.setTrackDefaultSynthParam(selectedTrackIndex,
                                              mmg::AudioEngine::DefaultSynthParam::CutoffHz,
                                              (float)defaultSynthCutoff.getValue());
        persistDefaultSynthControlToProject(selectedTrackIndex, Project::IDs::defaultSynthCutoff, (float)defaultSynthCutoff.getValue());
    };
    addAndMakeVisible(defaultSynthCutoff);

    defaultSynthLfoRateLabel.setText("LFO Rate", juce::dontSendNotification);
    defaultSynthLfoRateLabel.setFont(juce::Font(10.0f));
    defaultSynthLfoRateLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(defaultSynthLfoRateLabel);
    setupSlider(defaultSynthLfoRate, 0.0, 20.0, 0.01, " Hz");
    defaultSynthLfoRate.setValue(5.0, juce::dontSendNotification);
    defaultSynthLfoRate.onValueChange = [this]() {
        if (isUpdatingDefaultSynthControls)
            return;
        audioEngine.setTrackDefaultSynthParam(selectedTrackIndex,
                                              mmg::AudioEngine::DefaultSynthParam::LfoRateHz,
                                              (float)defaultSynthLfoRate.getValue());
        persistDefaultSynthControlToProject(selectedTrackIndex, Project::IDs::defaultSynthLfoRate, (float)defaultSynthLfoRate.getValue());
    };
    addAndMakeVisible(defaultSynthLfoRate);

    defaultSynthLfoDepthLabel.setText("LFO Depth", juce::dontSendNotification);
    defaultSynthLfoDepthLabel.setFont(juce::Font(10.0f));
    defaultSynthLfoDepthLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(defaultSynthLfoDepthLabel);
    setupSlider(defaultSynthLfoDepth, 0.0, 1.0, 0.001, "");
    defaultSynthLfoDepth.setValue(0.0, juce::dontSendNotification);
    defaultSynthLfoDepth.onValueChange = [this]() {
        if (isUpdatingDefaultSynthControls)
            return;
        audioEngine.setTrackDefaultSynthParam(selectedTrackIndex,
                                              mmg::AudioEngine::DefaultSynthParam::LfoDepth,
                                              (float)defaultSynthLfoDepth.getValue());
        persistDefaultSynthControlToProject(selectedTrackIndex, Project::IDs::defaultSynthLfoDepth, (float)defaultSynthLfoDepth.getValue());
    };
    addAndMakeVisible(defaultSynthLfoDepth);
    
    // Initialize with Arrange view visible
    currentTab = 0;
    updateTabButtons();
    
    // Sync initial track count to piano roll
    if (pianoRoll && arrangementView)
    {
        int trackCount = arrangementView->getTrackList().getTrackCount();
        pianoRoll->setTrackCount(trackCount);

        trackIsDrumKit.clear();
        for (int i = 0; i < trackCount; ++i)
            trackIsDrumKit.add(false);

        trackInstrumentIds.clear();
        for (int i = 0; i < trackCount; ++i)
            trackInstrumentIds.add("default_sine");
    }

    updateDefaultSynthControlsVisibility();

    // Load initial values from ProjectState (track 0) and apply to engine
    syncDefaultSynthControlsFromProject(selectedTrackIndex);
    applyDefaultSynthControlsToEngine(selectedTrackIndex);
    
    // Set default theme
    themeManager.setTheme(GenreTheme::defaultTheme());
    updateTheme();
}

void VisualizationPanel::persistDefaultSynthControlToProject(int trackIndex, const juce::Identifier& prop, const juce::var& value)
{
    auto trackNode = appState.getProjectState().getTrackNode(trackIndex);
    if (!trackNode.isValid())
        return;

    trackNode.setProperty(prop, value, nullptr);
}

void VisualizationPanel::syncDefaultSynthControlsFromProject(int trackIndex)
{
    auto trackNode = appState.getProjectState().getTrackNode(trackIndex);
    if (!trackNode.isValid())
        return;

    juce::ScopedValueSetter<bool> guard(isUpdatingDefaultSynthControls, true);

    const int wf = (int)trackNode.getProperty(Project::IDs::defaultSynthWaveform, 1);
    defaultSynthWaveform.setSelectedId(juce::jlimit(1, 4, wf), juce::dontSendNotification);

    defaultSynthAttack.setValue((double)trackNode.getProperty(Project::IDs::defaultSynthAttack, 0.001f), juce::dontSendNotification);
    defaultSynthRelease.setValue((double)trackNode.getProperty(Project::IDs::defaultSynthRelease, 0.2f), juce::dontSendNotification);
    defaultSynthCutoff.setValue((double)trackNode.getProperty(Project::IDs::defaultSynthCutoff, 16000.0f), juce::dontSendNotification);
    defaultSynthLfoRate.setValue((double)trackNode.getProperty(Project::IDs::defaultSynthLfoRate, 5.0f), juce::dontSendNotification);
    defaultSynthLfoDepth.setValue((double)trackNode.getProperty(Project::IDs::defaultSynthLfoDepth, 0.0f), juce::dontSendNotification);
}

void VisualizationPanel::applyDefaultSynthControlsToEngine(int trackIndex)
{
    const int wf = defaultSynthWaveform.getSelectedId();
    if (wf > 0)
    {
        mmg::AudioEngine::DefaultSynthWaveform waveformEnum = mmg::AudioEngine::DefaultSynthWaveform::Sine;
        switch (wf)
        {
            case 1: waveformEnum = mmg::AudioEngine::DefaultSynthWaveform::Sine; break;
            case 2: waveformEnum = mmg::AudioEngine::DefaultSynthWaveform::Triangle; break;
            case 3: waveformEnum = mmg::AudioEngine::DefaultSynthWaveform::Saw; break;
            case 4: waveformEnum = mmg::AudioEngine::DefaultSynthWaveform::Square; break;
            default: break;
        }
        audioEngine.setTrackDefaultSynthWaveform(trackIndex, waveformEnum);
    }

    audioEngine.setTrackDefaultSynthParam(trackIndex, mmg::AudioEngine::DefaultSynthParam::AttackSeconds, (float)defaultSynthAttack.getValue());
    audioEngine.setTrackDefaultSynthParam(trackIndex, mmg::AudioEngine::DefaultSynthParam::ReleaseSeconds, (float)defaultSynthRelease.getValue());
    audioEngine.setTrackDefaultSynthParam(trackIndex, mmg::AudioEngine::DefaultSynthParam::CutoffHz, (float)defaultSynthCutoff.getValue());
    audioEngine.setTrackDefaultSynthParam(trackIndex, mmg::AudioEngine::DefaultSynthParam::LfoRateHz, (float)defaultSynthLfoRate.getValue());
    audioEngine.setTrackDefaultSynthParam(trackIndex, mmg::AudioEngine::DefaultSynthParam::LfoDepth, (float)defaultSynthLfoDepth.getValue());
}

void VisualizationPanel::updatePianoRollDrumModeForCurrentSoloTrack()
{
    if (!pianoRoll)
        return;

    const int solo = pianoRoll->getSoloedTrack();
    bool shouldBeDrum = false;
    if (solo >= 0 && solo < trackIsDrumKit.size())
        shouldBeDrum = trackIsDrumKit[solo];

    pianoRoll->setDrumMode(shouldBeDrum);
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
    // Needs enough vertical space for labels + visible slider tracks/thumbs.
    // (On high DPI, the previous 92px effectively collapsed slider hit targets.)
    int synthStripHeight = defaultSynthGroup.isVisible() ? 148 : 0;
    auto synthArea = bounds.removeFromBottom(synthStripHeight);
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

    if (synthStripHeight > 0)
    {
        defaultSynthGroup.setBounds(synthArea.reduced(6, 4));

        auto inner = defaultSynthGroup.getBounds().reduced(12, 18);
        auto header = inner.removeFromTop(18);
        defaultSynthTitle.setBounds(header.removeFromLeft(240));

        // Layout controls in two rows with enough height for a draggable slider.
        const int rowGap = 10;
        const int rowHeight = juce::jmax(40, (inner.getHeight() - rowGap) / 2);
        auto row1 = inner.removeFromTop(rowHeight);
        inner.removeFromTop(rowGap);
        auto row2 = inner.removeFromTop(rowHeight);

        auto layoutLabeled = [](juce::Label& label, juce::Component& comp, juce::Rectangle<int> area) {
            auto top = area.removeFromTop(14);
            label.setBounds(top);
            comp.setBounds(area);
        };

        auto third1 = row1.getWidth() / 3;
        auto a1 = row1.removeFromLeft(third1);
        auto a2 = row1.removeFromLeft(third1);
        auto a3 = row1;

        layoutLabeled(defaultSynthWaveformLabel, defaultSynthWaveform, a1.reduced(6, 0));
        layoutLabeled(defaultSynthAttackLabel, defaultSynthAttack, a2.reduced(6, 0));
        layoutLabeled(defaultSynthReleaseLabel, defaultSynthRelease, a3.reduced(6, 0));

        auto third2 = row2.getWidth() / 3;
        auto b1 = row2.removeFromLeft(third2);
        auto b2 = row2.removeFromLeft(third2);
        auto b3 = row2;

        layoutLabeled(defaultSynthCutoffLabel, defaultSynthCutoff, b1.reduced(6, 0));
        layoutLabeled(defaultSynthLfoRateLabel, defaultSynthLfoRate, b2.reduced(6, 0));
        layoutLabeled(defaultSynthLfoDepthLabel, defaultSynthLfoDepth, b3.reduced(6, 0));
    }
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

    updateDefaultSynthControlsVisibility();
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

void VisualizationPanel::pianoRollSoloTrackChanged(int soloedTrack)
{
    // When the user selects a specific track in the Piano Roll, treat it as the active track
    // for Default Synth controls and per-track UI context.
    if (soloedTrack >= 0)
    {
        selectedTrackIndex = soloedTrack;
        updateDefaultSynthControlsVisibility();
        syncDefaultSynthControlsFromProject(soloedTrack);
        applyDefaultSynthControlsToEngine(soloedTrack);
        updatePianoRollDrumModeForCurrentSoloTrack();
    }
}

void VisualizationPanel::arrangementTrackSelected(int trackIndex)
{
    selectedTrackIndex = trackIndex;
    updateDefaultSynthControlsVisibility();

    // Sync Default Synth controls from saved per-track state
    syncDefaultSynthControlsFromProject(trackIndex);
    applyDefaultSynthControlsToEngine(trackIndex);

    if (!pianoRoll)
        return;

    pianoRoll->setAuditionTrackIndex(trackIndex);

    // In "All Tracks" mode, keep key labels aligned with the active track.
    if (pianoRoll->getSoloedTrack() < 0)
    {
        const bool isKit = (trackIndex >= 0 && trackIndex < trackIsDrumKit.size()) ? trackIsDrumKit[trackIndex] : false;
        pianoRoll->setDrumMode(isKit);
    }
}

void VisualizationPanel::arrangementTrackPianoRollRequested(int trackIndex)
{
    DBG("ArrangementView requested Piano Roll for track " << trackIndex);
    
    // Switch to Piano Roll tab and solo the requested track
    showTab(1);  // Piano Roll is tab 1
    
    if (pianoRoll)
    {
        pianoRoll->soloTrack(trackIndex);
        updatePianoRollDrumModeForCurrentSoloTrack();
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

    // Persist instrument selection at the track level
    {
        auto trackNode = appState.getProjectState().getTrackNode(trackIndex);
        if (trackNode.isValid())
            trackNode.setProperty(Project::IDs::instrumentId, instrumentId.isEmpty() ? "default_sine" : instrumentId, nullptr);
    }

    // Update local per-track mode (drum kit vs chromatic) so Piano Roll can label keys appropriately.
    bool isDrumKit = false;
    if (instrumentId.isNotEmpty() && instrumentId != "default_sine")
    {
        if (const auto* def = audioEngine.getInstrumentDefinition(instrumentId))
        {
            isDrumKit = (!def->isChromatic) || (def->category == "drums");
        }
        else
        {
            // Fallback heuristic if definition isn't available
            isDrumKit = instrumentId.containsIgnoreCase("drum") || instrumentId.containsIgnoreCase("kit");
        }
    }

    if (trackIndex >= 0)
    {
        while (trackIsDrumKit.size() <= trackIndex)
            trackIsDrumKit.add(false);
        trackIsDrumKit.set(trackIndex, isDrumKit);

        while (trackInstrumentIds.size() <= trackIndex)
            trackInstrumentIds.add("default_sine");
        trackInstrumentIds.set(trackIndex, instrumentId);
    }

    if (trackIndex == selectedTrackIndex)
        updateDefaultSynthControlsVisibility();

    // If the piano roll is currently editing this track, update labels immediately.
    if (pianoRoll && pianoRoll->getSoloedTrack() == trackIndex)
        updatePianoRollDrumModeForCurrentSoloTrack();
    
    // Forward to MainComponent via listener
    listeners.call([trackIndex, &instrumentId](Listener& l) {
        l.trackInstrumentSelected(trackIndex, instrumentId);
    });
}

void VisualizationPanel::updateDefaultSynthControlsVisibility()
{
    const bool inRelevantTab = (currentTab == 0 || currentTab == 1);
    bool isDefaultSynth = true;

    if (selectedTrackIndex >= 0)
    {
        // Prefer persisted state.
        auto trackNode = appState.getProjectState().getTrackNode(selectedTrackIndex);
        if (trackNode.isValid())
        {
            auto id = trackNode.getProperty(Project::IDs::instrumentId).toString();
            if (id.isEmpty())
                id = "default_sine";
            isDefaultSynth = (id.isEmpty() || id == "default_sine");
        }
        else if (selectedTrackIndex < trackInstrumentIds.size())
        {
            const auto& id = trackInstrumentIds.getReference(selectedTrackIndex);
            isDefaultSynth = (id.isEmpty() || id == "default_sine");
        }
    }

    const bool shouldShow = inRelevantTab && isDefaultSynth && selectedTrackIndex >= 0;

    if (defaultSynthGroup.isVisible() != shouldShow)
    {
        defaultSynthGroup.setVisible(shouldShow);
        defaultSynthTitle.setVisible(shouldShow);
        defaultSynthWaveform.setVisible(shouldShow);
        defaultSynthWaveformLabel.setVisible(shouldShow);
        defaultSynthAttack.setVisible(shouldShow);
        defaultSynthAttackLabel.setVisible(shouldShow);
        defaultSynthRelease.setVisible(shouldShow);
        defaultSynthReleaseLabel.setVisible(shouldShow);
        defaultSynthCutoff.setVisible(shouldShow);
        defaultSynthCutoffLabel.setVisible(shouldShow);
        defaultSynthLfoRate.setVisible(shouldShow);
        defaultSynthLfoRateLabel.setVisible(shouldShow);
        defaultSynthLfoDepth.setVisible(shouldShow);
        defaultSynthLfoDepthLabel.setVisible(shouldShow);

        resized();
    }

    if (shouldShow)
        defaultSynthTitle.setText("Track " + juce::String(selectedTrackIndex + 1), juce::dontSendNotification);
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
