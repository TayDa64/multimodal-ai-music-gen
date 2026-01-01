/*
  ==============================================================================

    MainComponent.cpp
    
    Implementation of the root UI component.

  ==============================================================================
*/

#include "MainComponent.h"
#include "UI/Theme/ColourScheme.h"

//==============================================================================
MainComponent::MainComponent(AppState& state, mmg::AudioEngine& engine)
    : appState(state),
      audioEngine(engine)
{
    // Listen to project state changes
    appState.getProjectState().getState().addListener(this);

    // Set size FIRST
    setSize(1280, 800);
    
    // Create Python manager and attempt to auto-start the server
    pythonManager = std::make_unique<PythonManager>();
    startPythonServer();
    
    // Create UI components
    transportBar = std::make_unique<TransportComponent>(appState, audioEngine);
    transportBar->setVisible(true);
    addAndMakeVisible(*transportBar);
    
    // Timeline component - shows sections, beat markers, playhead
    timelineComponent = std::make_unique<TimelineComponent>(appState, audioEngine);
    timelineComponent->setBPM(appState.getBPM());
    timelineComponent->setVisible(true);
    addAndMakeVisible(*timelineComponent);
    
    promptPanel = std::make_unique<PromptPanel>(appState);
    promptPanel->addListener(this);
    promptPanel->setVisible(true);
    addAndMakeVisible(*promptPanel);
    
    // Visualization panel with tabbed interface (Piano Roll + Recent Files)
    visualizationPanel = std::make_unique<VisualizationPanel>(appState, audioEngine);
    visualizationPanel->addListener(this);
    visualizationPanel->setVisible(true);
    addAndMakeVisible(*visualizationPanel);
    
    // Set output directory for visualization panel - use a more reliable path
    auto appDir = juce::File::getSpecialLocation(juce::File::currentExecutableFile).getParentDirectory();
    
    // Try multiple possible output locations
    juce::Array<juce::File> possibleOutputDirs = {
        appDir.getParentDirectory().getParentDirectory().getParentDirectory().getParentDirectory().getChildFile("output"),
        appDir.getSiblingFile("output"),
        juce::File("C:/dev/AI Music Generator/multimodal-ai-music-gen/output")
    };
    
    for (auto& dir : possibleOutputDirs)
    {
        if (dir.isDirectory())
        {
            visualizationPanel->setOutputDirectory(dir);
            break;
        }
    }
    
    progressOverlay = std::make_unique<ProgressOverlay>(appState);
    progressOverlay->addListener(this);
    addChildComponent(*progressOverlay); // Hidden by default
    
    // NB Phase 2: Genre-aware components
    setupBottomPanel();
    
    // Force a layout update
    resized();
    
    // Start timer for status updates (OSC setup happens in first timer callback)
    startTimerHz(10);
}

MainComponent::~MainComponent()
{
    appState.getProjectState().getState().removeListener(this);
    stopTimer();
    
    // Send graceful shutdown to Python server before cleaning up
    stopPythonServer();
    
    if (oscBridge)
        oscBridge->removeListener(this);
    
    if (visualizationPanel)
        visualizationPanel->removeListener(this);
    
    if (genreSelector)
        genreSelector->removeListener(this);
    
    if (instrumentBrowser)
        instrumentBrowser->removeListener(this);
    
    if (fxChainPanel)
        fxChainPanel->removeListener(this);
    
    if (expansionBrowser)
        expansionBrowser->removeListener(this);
}

//==============================================================================
void MainComponent::setupOSCConnection()
{
    oscBridge = std::make_unique<OSCBridge>(9001, 9000);
    oscBridge->addListener(this);
    
    if (!oscBridge->connect())
    {
        DBG("Warning: Could not establish OSC connection");
    }
}

//==============================================================================
void MainComponent::setupBottomPanel()
{
    // Create all components first before adding listeners
    
    // Genre Selector - positioned above prompt panel
    genreSelector = std::make_unique<GenreSelector>();
    addAndMakeVisible(*genreSelector);
    
    // Instrument Browser
    instrumentBrowser = std::make_unique<InstrumentBrowserPanel>(audioEngine.getDeviceManager());
    addAndMakeVisible(*instrumentBrowser);
    
    // FX Chain Panel
    fxChainPanel = std::make_unique<FXChainPanel>();
    fxChainPanel->setVisible(false);  // Start hidden
    addAndMakeVisible(*fxChainPanel);
    
    // Expansion Browser Panel
    expansionBrowser = std::make_unique<ExpansionBrowserPanel>();
    expansionBrowser->setVisible(false);  // Start hidden
    addAndMakeVisible(*expansionBrowser);
    
    // Mixer Component
    mixerComponent = std::make_unique<UI::MixerComponent>();
    mixerComponent->setVisible(false);
    mixerComponent->bindToProject(appState.getProjectState());
    
    // Initialize mixer strips from project state
    juce::StringArray trackNames;
    auto mixerNode = appState.getProjectState().getMixerNode();
    for (const auto& child : mixerNode)
    {
        if (child.hasType(Project::IDs::TRACK))
            trackNames.add(child.getProperty(Project::IDs::name));
    }
    // If no tracks in project (legacy), use default names matching AudioEngine
    if (trackNames.isEmpty())
    {
        for (int i = 0; i < 4; ++i)
            trackNames.add("Track " + juce::String(i + 1));
    }
    mixerComponent->setTracks(trackNames);
    
    addAndMakeVisible(*mixerComponent);
    
    // Tab buttons for bottom panel
    instrumentsTabButton.setRadioGroupId(100);
    instrumentsTabButton.setClickingTogglesState(true);
    instrumentsTabButton.setToggleState(true, juce::dontSendNotification);
    instrumentsTabButton.setColour(juce::TextButton::buttonColourId, AppColours::surface);
    instrumentsTabButton.setColour(juce::TextButton::buttonOnColourId, AppColours::primary.darker(0.3f));
    instrumentsTabButton.onClick = [this]() {
        currentBottomTab = 0;
        updateBottomPanelTabs();
    };
    addAndMakeVisible(instrumentsTabButton);
    
    fxTabButton.setRadioGroupId(100);
    fxTabButton.setClickingTogglesState(true);
    fxTabButton.setColour(juce::TextButton::buttonColourId, AppColours::surface);
    fxTabButton.setColour(juce::TextButton::buttonOnColourId, AppColours::primary.darker(0.3f));
    fxTabButton.onClick = [this]() {
        currentBottomTab = 1;
        updateBottomPanelTabs();
    };
    addAndMakeVisible(fxTabButton);
    
    expansionsTabButton.setRadioGroupId(100);
    expansionsTabButton.setClickingTogglesState(true);
    expansionsTabButton.setColour(juce::TextButton::buttonColourId, AppColours::surface);
    expansionsTabButton.setColour(juce::TextButton::buttonOnColourId, AppColours::primary.darker(0.3f));
    expansionsTabButton.onClick = [this]() {
        currentBottomTab = 2;
        updateBottomPanelTabs();
        // Request expansion list when tab is opened
        if (expansionBrowser)
            expansionBrowser->requestExpansionList();
    };
    addAndMakeVisible(expansionsTabButton);
    
    mixerTabButton.setRadioGroupId(100);
    mixerTabButton.setClickingTogglesState(true);
    mixerTabButton.setColour(juce::TextButton::buttonColourId, AppColours::surface);
    mixerTabButton.setColour(juce::TextButton::buttonOnColourId, AppColours::primary.darker(0.3f));
    mixerTabButton.onClick = [this]() {
        currentBottomTab = 3;
        updateBottomPanelTabs();
    };
    addAndMakeVisible(mixerTabButton);
    
    // Now add listeners AFTER all components are created
    genreSelector->addListener(this);
    instrumentBrowser->addListener(this);
    fxChainPanel->addListener(this);
    expansionBrowser->addListener(this);
    
    // Set default genre (this triggers listener, but all components now exist)
    genreSelector->setSelectedGenre("trap");
    
    // Request initial instrument data
    if (instrumentBrowser)
        instrumentBrowser->requestInstrumentData();
}

void MainComponent::updateBottomPanelTabs()
{
    if (instrumentBrowser)
        instrumentBrowser->setVisible(currentBottomTab == 0);
    
    if (fxChainPanel)
        fxChainPanel->setVisible(currentBottomTab == 1);
    
    if (expansionBrowser)
        expansionBrowser->setVisible(currentBottomTab == 2);
    
    if (mixerComponent)
        mixerComponent->setVisible(currentBottomTab == 3);
    
    resized();
    repaint();
}

void MainComponent::applyGenreTheme(const juce::String& genreId)
{
    currentGenre = genreId;
    
    // Guard against being called before components are ready
    // Apply theme to visualization panel
    if (visualizationPanel)
        visualizationPanel->setGenre(genreId);
    
    // Apply genre-specific FX chain preset
    if (fxChainPanel)
        fxChainPanel->loadPreset(genreId);
    
    // Filter instruments by genre
    if (instrumentBrowser)
        instrumentBrowser->setGenreFilter(genreId);
    
    DBG("Applied genre theme: " + genreId);
}

//==============================================================================
void MainComponent::paint(juce::Graphics& g)
{
    // Background
    g.fillAll(AppColours::background);
    
    // Status bar at bottom - clear, single source of truth for connection status
    auto statusArea = getLocalBounds().removeFromBottom(24).reduced(padding, 2);
    
    // Background for status bar
    g.setColour(AppColours::surface);
    g.fillRect(statusArea.expanded(padding, 2));
    
    // Connection status (left side) - use clear icon and text
    juce::String connectionText;
    juce::Colour connectionColour;
    if (serverConnected)
    {
        connectionText = juce::String(juce::CharPointer_UTF8("● Server Connected"));
        connectionColour = AppColours::success;
    }
    else
    {
        connectionText = juce::String(juce::CharPointer_UTF8("○ Server Offline - Start with: python main.py --server"));
        connectionColour = AppColours::warning;
    }
    
    g.setFont(12.0f);
    g.setColour(connectionColour);
    g.drawText(connectionText, statusArea.removeFromLeft(400), juce::Justification::left);
    
    // Current genre indicator (center)
    g.setColour(AppColours::textSecondary);
    g.drawText("Genre: " + currentGenre, statusArea.reduced(100, 0), juce::Justification::centred);
    
    // Current activity status (right side)
    g.setColour(AppColours::textSecondary);
    g.drawText(currentStatus, statusArea, juce::Justification::right);
}

void MainComponent::resized()
{
    auto bounds = getLocalBounds();
    
    if (bounds.isEmpty())
        return;  // Guard against zero-size
    
    // Reserve space for status bar (slightly taller for better readability)
    bounds.removeFromBottom(24);
    
    // Transport bar at top (50px)
    if (transportBar)
    {
        transportBar->setBounds(bounds.removeFromTop(transportHeight));
        transportBar->setVisible(true);
    }
    
    // Timeline below transport (65px)
    if (timelineComponent)
    {
        timelineComponent->setBounds(bounds.removeFromTop(timelineHeight).reduced(padding, 0));
        timelineComponent->setVisible(true);
    }
    
    // Bottom panel with tabs
    // Make it responsive: take 1/3 of height, but at least 280px
    int bottomPanelHeight = juce::jmax(280, bounds.getHeight() / 3);
    auto bottomArea = bounds.removeFromBottom(bottomPanelHeight);
    
    // Tab buttons for bottom panel
    auto tabRow = bottomArea.removeFromTop(30);
    int tabWidth = 100;
    instrumentsTabButton.setBounds(tabRow.removeFromLeft(tabWidth).reduced(2, 4));
    fxTabButton.setBounds(tabRow.removeFromLeft(tabWidth).reduced(2, 4));
    expansionsTabButton.setBounds(tabRow.removeFromLeft(tabWidth).reduced(2, 4));
    mixerTabButton.setBounds(tabRow.removeFromLeft(tabWidth).reduced(2, 4));
    
    // Bottom panel content
    bottomPanelArea = bottomArea.reduced(padding, 0);
    if (instrumentBrowser && currentBottomTab == 0)
        instrumentBrowser->setBounds(bottomPanelArea);
    if (fxChainPanel && currentBottomTab == 1)
        fxChainPanel->setBounds(bottomPanelArea);
    if (expansionBrowser && currentBottomTab == 2)
        expansionBrowser->setBounds(bottomPanelArea);
    if (mixerComponent && currentBottomTab == 3)
        mixerComponent->setBounds(bottomPanelArea);
    
    // Main content area - what remains
    auto contentArea = bounds.reduced(padding);
    
    // Left column: Genre selector + Prompt panel (320px)
    auto leftColumn = contentArea.removeFromLeft(promptPanelWidth);
    
    // Genre selector at top of left column (60px)
    if (genreSelector)
    {
        genreSelector->setBounds(leftColumn.removeFromTop(60));
        genreSelector->setVisible(true);
    }
    
    leftColumn.removeFromTop(padding);
    
    // Prompt panel fills the rest of left column
    if (promptPanel)
    {
        promptPanel->setBounds(leftColumn);
        promptPanel->setVisible(true);
    }
    
    // Gap between prompt and visualization
    contentArea.removeFromLeft(padding);
    
    // Visualization panel takes remaining space
    visualizationArea = contentArea;
    
    if (visualizationPanel)
    {
        visualizationPanel->setBounds(visualizationArea);
        visualizationPanel->setVisible(true);
    }
    
    // Progress overlay covers the whole component
    if (progressOverlay)
        progressOverlay->setBounds(getLocalBounds());
    
    // Force repaint
    repaint();
}

//==============================================================================
void MainComponent::drawPlaceholder(juce::Graphics& g, juce::Rectangle<int> area,
                                   const juce::String& label, juce::Colour colour)
{
    // Background
    g.setColour(colour);
    g.fillRoundedRectangle(area.toFloat(), 6.0f);
    
    // Border
    g.setColour(AppColours::border);
    g.drawRoundedRectangle(area.toFloat(), 6.0f, 1.0f);
    
    // Label
    g.setColour(AppColours::textSecondary.withAlpha(0.5f));
    g.setFont(16.0f);
    g.drawText(label, area, juce::Justification::centred);
}

//==============================================================================
void MainComponent::onConnectionStatusChanged(bool connected)
{
    serverConnected = connected;
    currentStatus = connected ? "Ready" : "Server not running";
    
    if (connected && !initialInstrumentsRequested)
    {
        if (instrumentBrowser)
        {
            DBG("MainComponent: Auto-scanning instruments...");
            instrumentBrowser->requestInstrumentData();
            initialInstrumentsRequested = true;
        }
    }
    
    juce::MessageManager::callAsync([this]()
    {
        repaint();
    });
}

void MainComponent::onProgress(float percent, const juce::String& step, const juce::String& message)
{
    currentProgress = percent;
    currentStatus = message;
    
    juce::MessageManager::callAsync([this]()
    {
        repaint();
    });
}

void MainComponent::onGenerationComplete(const GenerationResult& result)
{
    currentProgress = 1.0f;
    currentStatus = "Generation complete!";
    
    juce::MessageManager::callAsync([this, result]()
    {
        // Update app state with output file
        juce::File outputFile(result.audioPath.isNotEmpty() 
            ? result.audioPath : result.midiPath);
        appState.setOutputFile(outputFile);
        
        // IMPORTANT: Notify all AppState listeners that generation is complete
        // This must happen BEFORE setGenerating(false) to ensure proper UI reset
        appState.notifyGenerationCompleted(outputFile);
        
        // Now reset generating state
        appState.setGenerating(false);
        
        // Refresh the visualization panel to show the new file
        if (visualizationPanel)
            visualizationPanel->refreshRecentFiles();
        
        // Load the generated MIDI file for playback and visualization
        if (result.midiPath.isNotEmpty())
        {
            juce::File midiFile(result.midiPath);
            if (midiFile.existsAsFile())
            {
                audioEngine.loadMidiFile(midiFile);
                // Also load into piano roll
                if (visualizationPanel)
                    visualizationPanel->loadMidiFile(midiFile);
            }
        }
        
        // Show completion message (no callback to prevent accidental triggers)
        juce::String message = "Generation complete!\n\n";
        message += "MIDI: " + result.midiPath + "\n";
        if (result.audioPath.isNotEmpty())
            message += "Audio: " + result.audioPath + "\n";
        message += "\nDuration: " + juce::String(result.duration, 1) + "s";
        message += "\n\nThe file has been added to Recent Files.";
        
        juce::AlertWindow::showMessageBoxAsync(
            juce::MessageBoxIconType::InfoIcon,
            "Success",
            message
        );
        
        repaint();
    });
}

void MainComponent::onError(int code, const juce::String& message)
{
    juce::ignoreUnused(code);
    currentStatus = "Error: " + message;
    
    juce::MessageManager::callAsync([this, message]()
    {
        // Notify all AppState listeners about the error first
        appState.notifyGenerationError(message);
        
        // Then reset generating state
        appState.setGenerating(false);
        
        juce::AlertWindow::showMessageBoxAsync(
            juce::MessageBoxIconType::WarningIcon,
            "Generation Error",
            message
        );
        
        repaint();
    });
}

void MainComponent::onAnalyzeResultReceived(const AnalyzeResult& result)
{
    currentStatus = "Analysis complete";

    juce::MessageManager::callAsync([this, result]()
    {
        juce::String msg;
        msg += "Analysis complete!\n\n";
        if (result.bpm > 0.0f)
            msg += "BPM: " + juce::String(result.bpm, 1) + " (conf " + juce::String(result.bpmConfidence, 2) + ")\n";
        if (result.key.isNotEmpty())
            msg += "Key: " + result.key + " " + result.mode + " (conf " + juce::String(result.keyConfidence, 2) + ")\n";
        if (result.estimatedGenre.isNotEmpty())
            msg += "Estimated genre: " + result.estimatedGenre + " (conf " + juce::String(result.genreConfidence, 2) + ")\n";
        if (result.styleTags.size() > 0)
            msg += "Style tags: " + result.styleTags.joinIntoString(", ") + "\n";
        if (result.promptHints.isNotEmpty())
            msg += "\nPrompt hints: " + result.promptHints;

        juce::AlertWindow::showMessageBoxAsync(
            juce::MessageBoxIconType::InfoIcon,
            "Analyze",
            msg
        );

        repaint();
    });
}

void MainComponent::onAnalyzeError(int code, const juce::String& message)
{
    currentStatus = "Analyze error";

    juce::MessageManager::callAsync([this, code, message]()
    {
        juce::ignoreUnused(code);
        juce::AlertWindow::showMessageBoxAsync(
            juce::MessageBoxIconType::WarningIcon,
            "Analyze Error",
            message
        );
        repaint();
    });
}

//==============================================================================
// PromptPanel::Listener
void MainComponent::generateRequested(const juce::String& prompt)
{
    // Prevent duplicate generation requests
    if (appState.isGenerating())
    {
        DBG("Generation already in progress, ignoring request");
        return;
    }
    
    if (oscBridge && oscBridge->isConnected())
    {
        GenerationRequest request;
        request.prompt = prompt;
        request.genre = currentGenre;  // Pass genre from GenreSelector
        request.bpm = appState.getBPM();
        request.bars = appState.getDurationBars();
        request.renderAudio = true;
        
        oscBridge->sendGenerate(request);
        appState.setGenerating(true);
    }
    else
    {
        juce::AlertWindow::showMessageBoxAsync(
            juce::MessageBoxIconType::WarningIcon,
            "Not Connected",
            "Python backend is not connected.\n\n"
            "Start the server with:\n"
            "python main.py --server --verbose"
        );
    }
}

void MainComponent::cancelRequested()
{
    if (oscBridge)
    {
        oscBridge->sendCancel();
    }
    
    // Notify listeners about the cancellation (treated as an error for UI reset purposes)
    appState.notifyGenerationError("Cancelled by user");
    
    // Reset generating state immediately on user cancel
    appState.setGenerating(false);
    currentStatus = "Generation cancelled";
    
    juce::MessageManager::callAsync([this]()
    {
        repaint();
    });
}

//==============================================================================
// VisualizationPanel::Listener
void MainComponent::fileSelected(const juce::File& file)
{
    currentStatus = "Loaded: " + file.getFileName();
    
    // If it's a MIDI file, load it into the piano roll
    if (file.hasFileExtension(".mid;.midi") && visualizationPanel)
    {
        visualizationPanel->loadMidiFile(file);
    }
    
    juce::MessageManager::callAsync([this]()
    {
        repaint();
    });
}

void MainComponent::analyzeFileRequested(const juce::File& file)
{
    if (oscBridge && oscBridge->isConnected())
    {
        currentStatus = "Analyzing: " + file.getFileName();
        oscBridge->sendAnalyzeFile(file, false);
        repaint();
    }
    else
    {
        juce::AlertWindow::showMessageBoxAsync(
            juce::MessageBoxIconType::WarningIcon,
            "Not Connected",
            "Python backend is not connected.\n\n"
            "Start the server with:\n"
            "python main.py --server --verbose"
        );
    }
}

//==============================================================================
// GenreSelector::Listener
void MainComponent::genreChanged(const juce::String& genreId, const GenreTemplate& genre)
{
    DBG("Genre changed to: " + genreId);
    applyGenreTheme(genreId);
    
    // Update app state BPM based on genre template
    int midBpm = (genre.bpmMin + genre.bpmMax) / 2;
    appState.setBPM(midBpm);
    
    currentStatus = "Genre: " + genre.displayName;
    repaint();
}

//==============================================================================
// InstrumentBrowserPanel::Listener
void MainComponent::instrumentChosen(const InstrumentInfo& info)
{
    DBG("Instrument chosen: " + info.name + " (" + info.category + ")");
    currentStatus = "Selected: " + info.name;
    
    juce::File sampleFile(info.absolutePath);
    if (sampleFile.existsAsFile())
    {
        int trackIndex = 0;
        if (mixerComponent)
            trackIndex = mixerComponent->getSelectedTrackIndex();
            
        audioEngine.loadInstrument(trackIndex, sampleFile, info.name);
        currentStatus = "Loaded " + info.name + " to Track " + juce::String(trackIndex + 1);
        
        // Update ProjectState to reflect the change in the mixer
        auto trackNode = appState.getProjectState().getTrackNode(trackIndex);
        if (trackNode.isValid())
        {
            trackNode.setProperty(Project::IDs::name, info.name, nullptr);
            // Also store the path for persistence
            trackNode.setProperty(Project::IDs::path, info.absolutePath, nullptr);
        }
    }
    else
    {
        currentStatus = "File not found: " + info.filename;
    }
    
    repaint();
}

void MainComponent::onInstrumentsLoaded(const juce::String& json)
{
    DBG("MainComponent: Instruments loaded from server");
    if (instrumentBrowser)
    {
        instrumentBrowser->loadFromJSON(json);
        currentStatus = "Instrument library loaded";
        repaint();
    }
}

void MainComponent::requestLibraryInstruments()
{
    if (oscBridge && oscBridge->isConnected())
    {
        DBG("MainComponent: Requesting library instruments");
        // Request instruments from default paths (configured in server)
        // We send an empty list to imply "default/all"
        oscBridge->sendGetInstruments({});
    }
    else
    {
        DBG("MainComponent: Cannot request instruments - not connected");
    }
}

//==============================================================================
// FXChainPanel::Listener
void MainComponent::fxChainChanged(FXChainPanel* panel)
{
    if (panel == nullptr) return;
    
    DBG("FX chain updated");
    currentStatus = "FX chain updated";
    
    // TODO: Send FX chain to Python backend via OSC
    // auto fxJson = panel->toJSON();
    // oscBridge->sendFXChain(fxJson);
    
    repaint();
}

//==============================================================================
// ExpansionBrowserPanel::Listener
void MainComponent::requestExpansionListOSC()
{
    if (oscBridge && oscBridge->isConnected())
    {
        DBG("MainComponent: Requesting expansion list");
        oscBridge->sendExpansionList();
    }
    else
    {
        DBG("MainComponent: Cannot request expansions - not connected");
    }
}

void MainComponent::requestInstrumentsOSC(const juce::String& expansionId)
{
    if (oscBridge && oscBridge->isConnected())
    {
        DBG("MainComponent: Requesting instruments for expansion: " + expansionId);
        oscBridge->sendExpansionInstruments(expansionId);
    }
}

void MainComponent::requestResolveOSC(const juce::String& instrument, const juce::String& genre)
{
    if (oscBridge && oscBridge->isConnected())
    {
        DBG("MainComponent: Resolving instrument: " + instrument + " for genre: " + genre);
        oscBridge->sendExpansionResolve(instrument, genre);
    }
}

void MainComponent::requestImportExpansionOSC(const juce::String& path)
{
    if (oscBridge && oscBridge->isConnected())
    {
        DBG("MainComponent: Importing expansion from: " + path);
        oscBridge->sendExpansionImport(path);
        
        // Refresh list after import
        juce::Timer::callAfterDelay(1000, [this]() {
            requestExpansionListOSC();
        });
    }
}

void MainComponent::requestScanExpansionsOSC(const juce::String& directory)
{
    if (oscBridge && oscBridge->isConnected())
    {
        DBG("MainComponent: Scanning expansions in: " + directory);
        oscBridge->sendExpansionScan(directory);
        
        // Refresh list after scan
        juce::Timer::callAfterDelay(2000, [this]() {
            requestExpansionListOSC();
        });
    }
}

//==============================================================================
// OSCBridge::Listener expansion callbacks
void MainComponent::onExpansionListReceived(const juce::String& json)
{
    DBG("MainComponent: Received expansion list");
    
    juce::MessageManager::callAsync([this, json]() {
        if (expansionBrowser)
            expansionBrowser->loadExpansionsFromJSON(json);
    });
}

void MainComponent::onExpansionInstrumentsReceived(const juce::String& json)
{
    DBG("MainComponent: Received expansion instruments");
    
    juce::MessageManager::callAsync([this, json]() {
        if (expansionBrowser)
            expansionBrowser->loadInstrumentsFromJSON(json);
    });
}

void MainComponent::onExpansionResolveReceived(const juce::String& json)
{
    DBG("MainComponent: Received resolution result");
    
    juce::MessageManager::callAsync([this, json]() {
        if (expansionBrowser)
            expansionBrowser->showResolutionResult(json);
    });
}

//==============================================================================
// ProjectState::Listener overrides
void MainComponent::valueTreePropertyChanged(juce::ValueTree& tree, const juce::Identifier& property)
{
    if (tree.hasType(Project::IDs::TRACK))
    {
        int index = tree.getProperty(Project::IDs::index);
        if (auto* track = audioEngine.getTrack(index))
        {
            if (property == Project::IDs::volume)
                track->setVolume(tree.getProperty(property));
            else if (property == Project::IDs::mute)
                track->setMute(tree.getProperty(property));
            else if (property == Project::IDs::solo)
                track->setSolo(tree.getProperty(property));
        }
    }
    else if (tree.hasType(Project::IDs::NOTE))
    {
        // Note changed (moved, resized)
        juce::MessageManager::callAsync([this]() {
            auto midi = appState.getProjectState().exportToMidiFile();
            audioEngine.loadMidiData(midi);
        });
    }
}

void MainComponent::valueTreeChildAdded(juce::ValueTree& parent, juce::ValueTree& child)
{
    if (child.hasType(Project::IDs::NOTE))
    {
        juce::MessageManager::callAsync([this]() {
            auto midi = appState.getProjectState().exportToMidiFile();
            audioEngine.loadMidiData(midi);
        });
    }
}

void MainComponent::valueTreeChildRemoved(juce::ValueTree& parent, juce::ValueTree& child, int index)
{
    if (child.hasType(Project::IDs::NOTE))
    {
        juce::MessageManager::callAsync([this]() {
            auto midi = appState.getProjectState().exportToMidiFile();
            audioEngine.loadMidiData(midi);
        });
    }
}

//==============================================================================
void MainComponent::startPythonServer()
{
    if (pythonManager && !pythonManager->isRunning())
    {
        DBG("MainComponent: Attempting to auto-start Python server...");
        
        // Try to start the server on port 9000 (OSC receive port)
        bool started = pythonManager->startServer({}, {}, 9000, true);  // verbose=true
        
        if (started)
        {
            DBG("MainComponent: Python server started successfully");
            currentStatus = "Server starting...";
        }
        else
        {
            DBG("MainComponent: Could not auto-start Python server");
            currentStatus = "Server not found - start manually with: python main.py --server";
        }
    }
}

void MainComponent::stopPythonServer()
{
    // Send graceful shutdown via OSC first
    if (oscBridge && oscBridge->isConnected())
    {
        DBG("MainComponent: Sending shutdown command to Python server...");
        oscBridge->sendShutdown();
        
        // Give the server a moment to process the shutdown
        juce::Thread::sleep(500);
    }
    
    // Then stop the managed process
    if (pythonManager)
    {
        DBG("MainComponent: Stopping Python server process...");
        pythonManager->stopServer();
    }
}

//==============================================================================
void MainComponent::timerCallback()
{
    // Delayed OSC setup on first timer call
    if (!oscBridge)
    {
        setupOSCConnection();
        return;
    }
    
    // Periodic health check
    if (!oscBridge->isConnected())
    {
        // Try to reconnect
        oscBridge->connect();
    }
}

//==============================================================================
bool MainComponent::keyPressed(const juce::KeyPress& key)
{
    // Undo: Ctrl+Z (or Cmd+Z on Mac)
    if (key.isKeyCode('z') && key.getModifiers().isCommandDown())
    {
        if (key.getModifiers().isShiftDown())
        {
            // Redo: Ctrl+Shift+Z
            appState.getProjectState().redo();
            currentStatus = "Redo";
        }
        else
        {
            // Undo: Ctrl+Z
            appState.getProjectState().undo();
            currentStatus = "Undo";
        }
        repaint();
        return true;
    }
    
    // Redo: Ctrl+Y (Windows standard)
    if (key.isKeyCode('y') && key.getModifiers().isCommandDown())
    {
        appState.getProjectState().redo();
        currentStatus = "Redo";
        repaint();
        return true;
    }
    
    return false;
}
