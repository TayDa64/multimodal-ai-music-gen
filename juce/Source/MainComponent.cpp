/*
  ==============================================================================

    MainComponent.cpp
    
    Implementation of the root UI component.

  ==============================================================================
*/

#include "MainComponent.h"
#include "UI/Theme/ColourScheme.h"
#include "UI/Theme/LayoutConstants.h"

//==============================================================================
MainComponent::MainComponent(AppState& state, mmg::AudioEngine& engine)
    : appState(state),
      audioEngine(engine)
{
    appState.addListener(this);

    // Listen to project state changes
    appState.getProjectState().addStateListener(this);

    // Set size with enforced minimum dimensions for responsive design
    setSize(Layout::defaultWindowWidth, Layout::defaultWindowHeight);
    
    // Create Python manager and attempt to auto-start the server
    pythonManager = std::make_unique<PythonManager>();
    startPythonServer();
    
    // Create UI components
    transportBar = std::make_unique<TransportComponent>(appState, audioEngine);
    transportBar->addListener(this);  // Listen for Tools menu
    transportBar->setVisible(true);
    addAndMakeVisible(*transportBar);
    
    // Timeline component - hidden (we use ArrangementView's timeline ruler instead)
    // Keeping for backward compatibility but not displayed
    timelineComponent = std::make_unique<TimelineComponent>(appState, audioEngine);
    timelineComponent->setBPM(appState.getBPM());
    timelineComponent->addListener(this);
    timelineComponent->setVisible(false);  // Hidden - MPC-style single timeline in arrangement
    
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
    
    // Scan expansions immediately at startup
    scanLocalExpansions();

    // Apply any persisted per-track state (instrument + Default Synth params) to the audio engine.
    // This avoids needing to click through tracks after startup or project load.
    syncTrackAudioFromProjectState();
}

MainComponent::~MainComponent()
{
    appState.removeListener(this);
    appState.getProjectState().removeStateListener(this);
    stopTimer();
    
    // Close floating windows
    instrumentsWindow.reset();
    expansionsWindow.reset();
    controlsWindow.reset();
    
    // Send graceful shutdown to Python server before cleaning up
    stopPythonServer();
    
    if (oscBridge)
        oscBridge->removeListener(this);
    
    if (transportBar)
        transportBar->removeListener(this);
    
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
// AppState::Listener
void MainComponent::onNewProjectCreated()
{
    syncTrackAudioFromProjectState();
}

void MainComponent::onProjectLoaded(const juce::File& /*file*/)
{
    syncTrackAudioFromProjectState();
}

//==============================================================================
void MainComponent::syncTrackAudioFromProjectState()
{
    auto mixerNode = appState.getProjectState().getMixerNode();
    if (!mixerNode.isValid())
        return;

    for (const auto& child : mixerNode)
    {
        if (!child.hasType(Project::IDs::TRACK))
            continue;

        const int trackIndex = (int)child.getProperty(Project::IDs::index, 0);
        juce::String instrumentId = child.getProperty(Project::IDs::instrumentId).toString();
        if (instrumentId.isEmpty())
            instrumentId = "default_sine";

        // Reuse the same codepath as user selection so behavior stays consistent.
        trackInstrumentSelected(trackIndex, instrumentId);
    }
}

void MainComponent::applyDefaultSynthSettingsForTrackFromProjectState(int trackIndex)
{
    auto trackNode = appState.getProjectState().getTrackNode(trackIndex);
    if (!trackNode.isValid())
        return;

    const int wfId = (int)trackNode.getProperty(Project::IDs::defaultSynthWaveform, 1);
    mmg::AudioEngine::DefaultSynthWaveform waveformEnum = mmg::AudioEngine::DefaultSynthWaveform::Sine;
    switch (wfId)
    {
        case 2: waveformEnum = mmg::AudioEngine::DefaultSynthWaveform::Triangle; break;
        case 3: waveformEnum = mmg::AudioEngine::DefaultSynthWaveform::Saw; break;
        case 4: waveformEnum = mmg::AudioEngine::DefaultSynthWaveform::Square; break;
        case 1:
        default: waveformEnum = mmg::AudioEngine::DefaultSynthWaveform::Sine; break;
    }

    audioEngine.setTrackDefaultSynthWaveform(trackIndex, waveformEnum);

    audioEngine.setTrackDefaultSynthParam(trackIndex,
                                          mmg::AudioEngine::DefaultSynthParam::AttackSeconds,
                                          (float)trackNode.getProperty(Project::IDs::defaultSynthAttack, 0.001f));
    audioEngine.setTrackDefaultSynthParam(trackIndex,
                                          mmg::AudioEngine::DefaultSynthParam::ReleaseSeconds,
                                          (float)trackNode.getProperty(Project::IDs::defaultSynthRelease, 0.2f));
    audioEngine.setTrackDefaultSynthParam(trackIndex,
                                          mmg::AudioEngine::DefaultSynthParam::CutoffHz,
                                          (float)trackNode.getProperty(Project::IDs::defaultSynthCutoff, 16000.0f));
    audioEngine.setTrackDefaultSynthParam(trackIndex,
                                          mmg::AudioEngine::DefaultSynthParam::LfoRateHz,
                                          (float)trackNode.getProperty(Project::IDs::defaultSynthLfoRate, 5.0f));
    audioEngine.setTrackDefaultSynthParam(trackIndex,
                                          mmg::AudioEngine::DefaultSynthParam::LfoDepth,
                                          (float)trackNode.getProperty(Project::IDs::defaultSynthLfoDepth, 0.0f));
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
    
    // Instrument Browser - will be shown in floating window
    instrumentBrowser = std::make_unique<InstrumentBrowserPanel>(audioEngine.getDeviceManager());
    // NOT added to this component - goes in floating window
    
    // FX Chain Panel - shown in bottom panel when triggered
    fxChainPanel = std::make_unique<FXChainPanel>();
    fxChainPanel->setVisible(false);
    fxChainPanel->setProjectState(&appState.getProjectState());
    addAndMakeVisible(*fxChainPanel);
    
    // Expansion Browser Panel - will be shown in floating window
    expansionBrowser = std::make_unique<ExpansionBrowserPanel>();
    // NOT added to this component - goes in floating window
    
    // Mixer Component - shown in bottom panel when triggered
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
    if (trackNames.isEmpty())
    {
        for (int i = 0; i < 4; ++i)
            trackNames.add("Track " + juce::String(i + 1));
    }
    mixerComponent->setTracks(trackNames);
    addAndMakeVisible(*mixerComponent);
    
    // Take Lane Panel - shown in bottom panel when triggered
    takeLanePanel = std::make_unique<TakeLanePanel>();
    takeLanePanel->setVisible(false);
    addAndMakeVisible(*takeLanePanel);
    
    // Now add listeners AFTER all components are created
    genreSelector->addListener(this);
    instrumentBrowser->addListener(this);
    fxChainPanel->addListener(this);
    expansionBrowser->addListener(this);
    takeLanePanel->addListener(this);
    
    // Sync currentGenre from GenreSelector's initial state (defaults to "auto")
    currentGenre = genreSelector->getSelectedGenreId();
    
    // Request initial instrument data
    if (instrumentBrowser)
        instrumentBrowser->requestInstrumentData();
}

void MainComponent::toolsMenuItemSelected(int itemId)
{
    showToolWindow(itemId);
}

void MainComponent::showToolWindow(int toolId)
{
    // 1 = Instruments (floating), 2 = FX Chain (bottom), 3 = Expansions (floating), 4 = Mixer (bottom), 5 = Takes (bottom)
    
    switch (toolId)
    {
        case 1: // Instruments - floating window
        {
            if (!instrumentsWindow)
            {
                instrumentsWindow = std::make_unique<FloatingToolWindow>(
                    "Instruments",
                    AppColours::background,
                    instrumentBrowser.get());
                instrumentsWindow->setResizable(true, false);
                instrumentsWindow->centreWithSize(600, 500);
            }
            instrumentsWindow->setVisible(true);
            instrumentsWindow->toFront(true);
            
            // Request data if needed
            if (instrumentBrowser)
                instrumentBrowser->requestInstrumentData();
            break;
        }
        
        case 2: // FX Chain - bottom panel
        {
            if (currentBottomTool == 2 && bottomPanelVisible)
            {
                hideBottomPanel();
            }
            else
            {
                bottomPanelVisible = true;
                currentBottomTool = 2;
                if (fxChainPanel) fxChainPanel->setVisible(true);
                if (mixerComponent) mixerComponent->setVisible(false);
                if (takeLanePanel) takeLanePanel->setVisible(false);
                resized();
            }
            break;
        }
        
        case 3: // Expansions - floating window
        {
            if (!expansionsWindow)
            {
                expansionsWindow = std::make_unique<FloatingToolWindow>(
                    "Expansions",
                    AppColours::background,
                    expansionBrowser.get());
                expansionsWindow->setResizable(true, false);
                expansionsWindow->centreWithSize(700, 500);
            }
            expansionsWindow->setVisible(true);
            expansionsWindow->toFront(true);
            
            // Request expansion list
            if (expansionBrowser)
                expansionBrowser->requestExpansionList();
            break;
        }

        case 6: // Controls - floating window
        {
            if (!controlsWindow)
            {
                controlsWindow = std::make_unique<ControlsWindow>();
                if (auto* panel = controlsWindow->getControlsPanel())
                    panel->addListener(this);
            }

            updateControlsNextOverridesUi();
            controlsWindow->setVisible(true);
            controlsWindow->toFront(true);
            break;
        }
        
        case 4: // Mixer - bottom panel
        {
            if (currentBottomTool == 4 && bottomPanelVisible)
            {
                hideBottomPanel();
            }
            else
            {
                bottomPanelVisible = true;
                currentBottomTool = 4;
                if (fxChainPanel) fxChainPanel->setVisible(false);
                if (mixerComponent) mixerComponent->setVisible(true);
                if (takeLanePanel) takeLanePanel->setVisible(false);
                resized();
            }
            break;
        }
        
        case 5: // Takes - bottom panel
        {
            if (currentBottomTool == 5 && bottomPanelVisible)
            {
                hideBottomPanel();
            }
            else
            {
                bottomPanelVisible = true;
                currentBottomTool = 5;
                if (fxChainPanel) fxChainPanel->setVisible(false);
                if (mixerComponent) mixerComponent->setVisible(false);
                if (takeLanePanel) takeLanePanel->setVisible(true);
                resized();
            }
            break;
        }
    }
}

void MainComponent::controlsApplyGlobalRequested(const juce::var& overrides)
{
    if (!ensureBackendConnected("Apply global controls"))
        return;

    oscBridge->sendControlsSet(overrides);
    currentStatus = "Applied global controls";
    repaint();
}

void MainComponent::controlsClearGlobalRequested(const juce::StringArray& keys)
{
    if (!ensureBackendConnected("Clear global controls"))
        return;

    oscBridge->sendControlsClear(keys);
    currentStatus = "Cleared global controls";
    repaint();
}

bool MainComponent::ensureBackendConnected(const juce::String& actionLabel)
{
    if (oscBridge && oscBridge->isConnected())
        return true;

    const auto now = juce::Time::currentTimeMillis();

    // Always attempt to (re)connect when an action requires the backend.
    // This covers the common case where the server is started externally
    // (e.g. `npm run start:server`) so pythonManager->isRunning() is false.
    constexpr juce::int64 connectAttemptIntervalMs = 1000;
    constexpr juce::int64 connectGracePeriodMs = 2000;
    if (now - lastBackendConnectAttemptMs > connectAttemptIntervalMs)
    {
        lastBackendConnectAttemptMs = now;
        setupOSCConnection();
        repaint();
    }

    const bool pythonRunning = (pythonManager && pythonManager->isRunning());
    if (pythonRunning || (now - lastBackendConnectAttemptMs) < connectGracePeriodMs)
    {
        // Server is likely coming up or reconnecting; avoid spamming a modal warning.
        currentStatus = actionLabel + " (waiting for server connection...)";
        repaint();
        return false;
    }

    // Server isn't running; show a debounced warning.
    if (now - lastBackendNotConnectedWarningMs > 2500)
    {
        lastBackendNotConnectedWarningMs = now;
        juce::AlertWindow::showMessageBoxAsync(
            juce::MessageBoxIconType::WarningIcon,
            "Not Connected",
            "Python backend is not connected.\n\n"
            "Start the server with:\n"
            "npm run start:server\n\n"
            "(or) python -m multimodal_gen.server --verbose"
        );
    }

    currentStatus = "Server Offline";
    repaint();
    return false;
}

void MainComponent::hideBottomPanel()
{
    bottomPanelVisible = false;
    currentBottomTool = 0;
    if (fxChainPanel) fxChainPanel->setVisible(false);
    if (mixerComponent) mixerComponent->setVisible(false);
    if (takeLanePanel) takeLanePanel->setVisible(false);
    resized();
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

void MainComponent::applyAnalysisResult(const AnalyzeResult& result)
{
    // Apply BPM if confidence is above threshold (0.5)
    if (result.bpm > 0.0f && result.bpmConfidence >= 0.5f)
    {
        int bpm = static_cast<int>(result.bpm + 0.5f);  // Round to nearest int
        appState.setBPM(bpm);
        
        // Update timeline
        if (timelineComponent)
            timelineComponent->setBPM(bpm);
        
        DBG("Applied BPM from analysis: " << bpm);
    }
    
    // Apply key if confidence is above threshold
    if (result.key.isNotEmpty() && result.keyConfidence >= 0.5f)
    {
        juce::String fullKey = result.key;
        if (result.mode.isNotEmpty())
            fullKey += " " + result.mode;
        
        appState.setKey(fullKey);
        DBG("Applied key from analysis: " << fullKey);
    }
    
    // Apply estimated genre if confidence is high enough and genre selector is available
    if (result.estimatedGenre.isNotEmpty() && result.genreConfidence >= 0.6f && genreSelector)
    {
        // Map common genre names to our genre IDs
        juce::String genreId = result.estimatedGenre.toLowerCase().replace(" ", "_");
        
        // Attempt to set the genre - GenreSelector will validate
        genreSelector->setSelectedGenre(genreId);
        DBG("Applied genre from analysis: " << genreId);
    }
    
    // Apply prompt hints to prompt panel
    if (result.promptHints.isNotEmpty() && promptPanel)
    {
        promptPanel->appendToPrompt(result.promptHints);
        DBG("Applied prompt hints: " << result.promptHints);
    }
    
    // Persist analysis in ProjectState for save/load
    auto projectState = appState.getProjectState().getState();
    auto analysisNode = projectState.getOrCreateChildWithName("LastAnalysis", nullptr);
    analysisNode.setProperty("bpm", result.bpm, nullptr);
    analysisNode.setProperty("bpmConfidence", result.bpmConfidence, nullptr);
    analysisNode.setProperty("key", result.key, nullptr);
    analysisNode.setProperty("mode", result.mode, nullptr);
    analysisNode.setProperty("keyConfidence", result.keyConfidence, nullptr);
    analysisNode.setProperty("estimatedGenre", result.estimatedGenre, nullptr);
    analysisNode.setProperty("genreConfidence", result.genreConfidence, nullptr);
    analysisNode.setProperty("promptHints", result.promptHints, nullptr);
    
    currentStatus = "Analysis applied";
    repaint();
}

void MainComponent::scanLocalExpansions()
{
    // Determine expansions directory relative to the executable
    auto appDir = juce::File::getSpecialLocation(juce::File::currentExecutableFile).getParentDirectory();
    
    DBG("MainComponent::scanLocalExpansions - Starting expansion scan");
    
    // Try multiple possible expansion locations
    juce::Array<juce::File> possibleExpansionDirs = {
        // From Debug build output: .../juce/build/MultimodalMusicGen_artefacts/Debug/
        // Need to go up 5 levels to get to "AI Music Generator"
        appDir.getParentDirectory()  // MultimodalMusicGen_artefacts
              .getParentDirectory()  // build
              .getParentDirectory()  // juce  
              .getParentDirectory()  // multimodal-ai-music-gen
              .getParentDirectory()  // AI Music Generator
              .getChildFile("expansions"),
        juce::File("C:/dev/AI Music Generator/expansions")  // Absolute fallback
    };
    
    for (auto& dir : possibleExpansionDirs)
    {
        if (dir.isDirectory())
        {
            DBG("  Found expansions directory: " << dir.getFullPathName());
            int count = audioEngine.scanExpansions(dir);
            DBG("  Scanned " << count << " expansions");
            
            // Get total instrument count
            int totalInstruments = 0;
            auto instrumentsByCategory = audioEngine.getInstrumentsByCategory();
            for (const auto& [cat, instruments] : instrumentsByCategory)
            {
                DBG("    Category '" << cat << "': " << instruments.size() << " instruments");
                totalInstruments += (int)instruments.size();
            }
            
            DBG("  Total instruments loaded: " << totalInstruments);
            
            if (totalInstruments > 0)
            {
                // Pass to visualization panel (which passes to arrangement view)
                if (visualizationPanel)
                {
                    visualizationPanel->setAvailableInstruments(instrumentsByCategory);
                }
                
                currentStatus = "Loaded " + juce::String(totalInstruments) + " expansion instruments";
            }
            break;  // Stop after finding first valid directory
        }
    }
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
    
    // Current genre indicator (center) - show display name from GenreSelector
    g.setColour(AppColours::textSecondary);
    juce::String genreDisplay = currentGenre;
    if (genreSelector)
    {
        if (auto* tmpl = genreSelector->getSelectedGenre())
            genreDisplay = tmpl->displayName;
    }
    g.drawText("Genre: " + genreDisplay, statusArea.reduced(100, 0), juce::Justification::centred);
    
    // Current activity status (right side)
    g.setColour(AppColours::textSecondary);
    g.drawText(currentStatus, statusArea, juce::Justification::right);
}

void MainComponent::resized()
{
    auto bounds = getLocalBounds();
    
    if (bounds.isEmpty())
        return;  // Guard against zero-size
    
    // Enforce minimum size for responsive design
    const int effectiveWidth = juce::jmax(bounds.getWidth(), Layout::minWindowWidth);
    const int effectiveHeight = juce::jmax(bounds.getHeight(), Layout::minWindowHeight);
    
    // Get adaptive values based on window size
    const int adaptivePadding = Layout::getAdaptivePadding(effectiveWidth);
    const int adaptiveSidebarWidth = Layout::getAdaptiveSidebarWidth(effectiveWidth);
    
    // Reserve space for status bar
    bounds.removeFromBottom(Layout::statusBarHeight);
    
    // Transport bar at top (use adaptive height)
    int transportH = effectiveHeight > 700 ? Layout::transportHeightDefault : Layout::transportHeightMin;
    if (transportBar)
    {
        transportBar->setBounds(bounds.removeFromTop(transportH));
        transportBar->setVisible(true);
    }
    
    // NO separate timeline - ArrangementView has its own ruler (MPC/ProTools style)
    // timelineComponent stays hidden
    
    // Bottom panel with FX/Mixer/Takes - only when visible (toggle from Tools menu)
    if (bottomPanelVisible)
    {
        int bottomPanelHeight = Layout::getAdaptiveBottomPanelHeight(bounds.getHeight());
        auto bottomArea = bounds.removeFromBottom(bottomPanelHeight);
        bottomPanelArea = bottomArea.reduced(adaptivePadding, 0);
        
        if (fxChainPanel && currentBottomTool == 2)
            fxChainPanel->setBounds(bottomPanelArea);
        if (mixerComponent && currentBottomTool == 4)
            mixerComponent->setBounds(bottomPanelArea);
        if (takeLanePanel && currentBottomTool == 5)
            takeLanePanel->setBounds(bottomPanelArea);
    }
    
    // Main content area - use FlexBox for responsive layout
    auto contentArea = bounds.reduced(adaptivePadding);
    
    // Left column container (genre selector + prompt panel)
    auto leftColumnBounds = contentArea.removeFromLeft(adaptiveSidebarWidth);
    
    // Genre selector at top of left column (fixed height)
    if (genreSelector)
    {
        genreSelector->setBounds(leftColumnBounds.removeFromTop(60));
        genreSelector->setVisible(true);
    }
    
    leftColumnBounds.removeFromTop(adaptivePadding);
    
    // Prompt panel fills the rest of left column
    if (promptPanel)
    {
        promptPanel->setBounds(leftColumnBounds);
        promptPanel->setVisible(true);
    }
    
    // Gap between left column and visualization
    contentArea.removeFromLeft(adaptivePadding);
    
    // Visualization panel takes remaining space (now much larger without bottom tabs)
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
        }
        
        if (expansionBrowser)
        {
            DBG("MainComponent: Auto-scanning expansions...");
            // Request list first (in case server already scanned)
            requestExpansionListOSC();
            // Also trigger a scan of the default expansions directory to be safe
            // This ensures new files (like the .xpj) are picked up if added while server was off
            // Use ../expansions because server runs in multimodal-ai-music-gen subdir
            requestScanExpansionsOSC("../expansions"); 
        }
        
        initialInstrumentsRequested = true;
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
        
        // Pass takes data to TakeLanePanel if available
        if (result.takesJson.isNotEmpty() && takeLanePanel)
        {
            takeLanePanel->setAvailableTakes(result.takesJson);
            
            // Auto-show takes panel if we have takes
            if (takeLanePanel->hasTakes() && !bottomPanelVisible)
            {
                showToolWindow(5);  // 5 = Takes
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
    
    // Store last analysis result for potential apply action
    lastAnalyzeResult = result;

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
        
        msg += "\n\nWould you like to apply these settings to the current session?";
        
        // Use AlertWindow with OK/Cancel to offer Apply action
        auto* window = new juce::AlertWindow(
            "Analyze Result",
            msg,
            juce::MessageBoxIconType::InfoIcon
        );
        
        window->addButton("Apply", 1, juce::KeyPress(juce::KeyPress::returnKey));
        window->addButton("Close", 0, juce::KeyPress(juce::KeyPress::escapeKey));
        
        window->enterModalState(true, juce::ModalCallbackFunction::create([this, result](int buttonClicked)
        {
            if (buttonClicked == 1)  // Apply clicked
            {
                applyAnalysisResult(result);
            }
        }), true);

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

void MainComponent::onSchemaVersionWarning(int clientVersion, int serverVersion, const juce::String& message)
{
    juce::ignoreUnused(clientVersion, serverVersion);
    
    // Surface schema version warning in status bar (non-blocking)
    currentStatus = "Warning: " + message;
    
    juce::MessageManager::callAsync([this, message]()
    {
        // Show a toast-like notification (use AlertWindow for simplicity, but non-modal)
        juce::AlertWindow::showMessageBoxAsync(
            juce::MessageBoxIconType::WarningIcon,
            "Protocol Version Mismatch",
            message + "\n\nGeneration will proceed with best-effort compatibility."
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
    
    if (ensureBackendConnected("Generate"))
    {
        GenerationRequest request;
        request.prompt = prompt;
        request.genre = currentGenre;  // Pass genre from GenreSelector
        request.bpm = appState.getBPM();
        request.bars = appState.getDurationBars();
        request.numTakes = appState.getNumTakes();
        request.renderAudio = true;

        // Apply-once per-request overrides (sent via options)
        if (nextGenerateOverrides.isObject())
        {
            request.options = nextGenerateOverrides;

            // If duration_bars provided, keep the legacy bars field aligned for this request.
            if (auto* obj = nextGenerateOverrides.getDynamicObject())
            {
                if (obj->hasProperty("duration_bars"))
                    request.bars = (int) obj->getProperty("duration_bars");
            }

            // Clear after one use
            nextGenerateOverrides = juce::var();
            updateControlsNextOverridesUi();
        }
        
        // Collect instrument paths from loaded tracks
        auto& projectState = appState.getProjectState();
        auto mixerNode = projectState.getMixerNode();
        
        for (const auto& child : mixerNode)
        {
            if (child.hasType(Project::IDs::TRACK))
            {
                juce::String instrumentPath = child.getProperty(Project::IDs::path).toString();
                if (instrumentPath.isNotEmpty())
                {
                    request.instrumentPaths.add(instrumentPath);
                    DBG("Adding instrument to generation: " << instrumentPath);
                }
            }
        }
        
        // Also get currently selected instrument if any
        if (instrumentBrowser)
        {
            const InstrumentInfo* selected = instrumentBrowser->getSelectedInstrument();
            if (selected && selected->absolutePath.isNotEmpty())
            {
                // Avoid duplicates
                if (!request.instrumentPaths.contains(selected->absolutePath))
                {
                    request.instrumentPaths.add(selected->absolutePath);
                    DBG("Adding selected instrument to generation: " << selected->absolutePath);
                }
            }
        }
        
        oscBridge->sendGenerate(request);
        appState.setGenerating(true);
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
    
    // Note: VisualizationPanel already handles loading MIDI files into piano roll
    // We just update the status here
    
    juce::MessageManager::callAsync([this]()
    {
        repaint();
    });
}

void MainComponent::analyzeFileRequested(const juce::File& file)
{
    if (!ensureBackendConnected("Analyze"))
        return;

    currentStatus = "Analyzing: " + file.getFileName();
    oscBridge->sendAnalyzeFile(file, false);
    repaint();
}

void MainComponent::regenerateRequested(int startBar, int endBar, const juce::StringArray& tracks)
{
    DBG("MainComponent: Regenerate requested bars " << startBar << "-" << endBar);

    if (!ensureBackendConnected("Regenerate"))
        return;

    {
        RegenerationRequest request;
        request.generateRequestId();
        request.startBar = startBar;
        request.endBar = endBar;
        request.tracks = tracks;
        request.seedStrategy = "new";
        
        // Get current context from app state
        request.bpm = appState.getBPM();
        request.key = appState.getKey();
        request.genre = currentGenre;

        // Apply-once per-request overrides (merged into options)
        if (nextRegenerateOverrides.isObject())
        {
            request.extraOptions = nextRegenerateOverrides;
            nextRegenerateOverrides = juce::var();
            updateControlsNextOverridesUi();
        }
        
        oscBridge->sendRegenerate(request);
        
        currentStatus = "Regenerating bars " + juce::String(startBar) + "-" + juce::String(endBar) + "...";
        repaint();
    }
}

void MainComponent::controlsApplyNextRequestRequested(const juce::var& overrides, ControlsPanel::NextScope scope)
{
    if (scope == ControlsPanel::NextScope::GenerateOnly)
    {
        nextGenerateOverrides = overrides;
    }
    else if (scope == ControlsPanel::NextScope::RegenerateOnly)
    {
        nextRegenerateOverrides = overrides;
    }
    else
    {
        nextGenerateOverrides = overrides;
        nextRegenerateOverrides = overrides;
    }

    updateControlsNextOverridesUi();
    currentStatus = "Armed overrides for next request";
    repaint();
}

void MainComponent::controlsClearNextRequestRequested()
{
    nextGenerateOverrides = juce::var();
    nextRegenerateOverrides = juce::var();

    updateControlsNextOverridesUi();
    currentStatus = "Cleared next-request overrides";
    repaint();
}

void MainComponent::updateControlsNextOverridesUi()
{
    if (!controlsWindow)
        return;

    if (auto* panel = controlsWindow->getControlsPanel())
    {
        const bool gen = nextGenerateOverrides.isObject();
        const bool regen = nextRegenerateOverrides.isObject();
        panel->setNextOverridesIndicator(gen, regen);
    }
}

void MainComponent::trackInstrumentSelected(int trackIndex, const juce::String& instrumentId)
{
    DBG("MainComponent: Track " << trackIndex << " instrument selected: " << instrumentId);
    
    // Load the instrument for this track
    if (instrumentId == "default_sine")
    {
        // Reset to simple sine synth (quick operation, no async needed)
        audioEngine.loadTrackInstrument(trackIndex, "");

        // Apply persisted Default Synth settings immediately (so playback matches without selecting tracks).
        applyDefaultSynthSettingsForTrackFromProjectState(trackIndex);
    }
    else
    {
        // Show loading status
        currentStatus = "Loading instrument...";
        repaint();
        
        // Load instrument asynchronously to avoid blocking UI
        juce::Thread::launch([this, trackIndex, instrumentId]() {
            bool success = audioEngine.loadTrackInstrument(trackIndex, instrumentId);
            
            // Update UI on message thread
            juce::MessageManager::callAsync([this, success, instrumentId]() {
                if (success)
                {
                    currentStatus = "Ready";
                }
                else
                {
                    currentStatus = "Failed to load instrument";
                    DBG("Failed to load instrument: " << instrumentId);
                }
                repaint();
            });
        });
    }
}

void MainComponent::trackLoadSF2Requested(int trackIndex)
{
    DBG("MainComponent: Track " << trackIndex << " load SF2 requested");
    
    auto fileChooser = std::make_shared<juce::FileChooser>(
        "Load SoundFont (SF2)",
        juce::File::getSpecialLocation(juce::File::userDocumentsDirectory),
        "*.sf2"
    );
    
    fileChooser->launchAsync(juce::FileBrowserComponent::openMode | juce::FileBrowserComponent::canSelectFiles,
        [this, trackIndex, fileChooser](const juce::FileChooser& chooser) {
            auto result = chooser.getResult();
            if (result.existsAsFile())
            {
                currentStatus = "Loading SF2...";
                repaint();
                
                // Load SF2 on background thread
                juce::Thread::launch([this, trackIndex, file = result]() {
                    if (auto* track = audioEngine.getTrack(trackIndex))
                    {
                        bool success = track->loadSF2(file);
                        
                        juce::MessageManager::callAsync([this, success, fileName = file.getFileName()]() {
                            if (success)
                            {
                                currentStatus = "Loaded: " + fileName;
                            }
                            else
                            {
                                currentStatus = "Failed to load SF2";
                            }
                            repaint();
                        });
                    }
                });
            }
        });
}

void MainComponent::trackLoadSFZRequested(int trackIndex)
{
    DBG("MainComponent: Track " << trackIndex << " load SFZ requested");
    
    auto fileChooser = std::make_shared<juce::FileChooser>(
        "Load SFZ Instrument",
        juce::File::getSpecialLocation(juce::File::userDocumentsDirectory),
        "*.sfz"
    );
    
    fileChooser->launchAsync(juce::FileBrowserComponent::openMode | juce::FileBrowserComponent::canSelectFiles,
        [this, trackIndex, fileChooser](const juce::FileChooser& chooser) {
            auto result = chooser.getResult();
            if (result.existsAsFile())
            {
                currentStatus = "Loading SFZ...";
                repaint();
                
                // Load SFZ on background thread
                juce::Thread::launch([this, trackIndex, file = result]() {
                    if (auto* track = audioEngine.getTrack(trackIndex))
                    {
                        bool success = track->loadSFZ(file);
                        
                        juce::MessageManager::callAsync([this, success, fileName = file.getFileName()]() {
                            if (success)
                            {
                                currentStatus = "Loaded: " + fileName;
                            }
                            else
                            {
                                currentStatus = "Failed to load SFZ";
                            }
                            repaint();
                        });
                    }
                });
            }
        });
}

void MainComponent::analyzeUrlRequested(const juce::String& url)
{
    if (!ensureBackendConnected("Analyze URL"))
        return;

    currentStatus = "Analyzing URL...";
    oscBridge->sendAnalyzeUrl(url, false);
    repaint();
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
    if (!ensureBackendConnected("Request instruments"))
        return;

    {
        DBG("MainComponent: Requesting library instruments");

        auto findInstrumentsDirectory = []() -> juce::File {
            juce::Array<juce::File> startPoints;
            startPoints.add(juce::File::getCurrentWorkingDirectory());
            startPoints.add(juce::File::getSpecialLocation(juce::File::currentExecutableFile).getParentDirectory());

            for (auto start : startPoints)
            {
                auto dir = start;
                for (int depth = 0; depth < 10 && dir.exists(); ++depth)
                {
                    auto instrumentsDir = dir.getChildFile("instruments");
                    if (instrumentsDir.isDirectory())
                        return instrumentsDir;
                    dir = dir.getParentDirectory();
                }
            }
            return {};
        };

        juce::StringArray paths;
        if (auto instrumentsDir = findInstrumentsDirectory(); instrumentsDir.isDirectory())
            paths.add(instrumentsDir.getFullPathName());

        // If we couldn't resolve a stable absolute path, fall back to the server-side defaults.
        // (Server will error if it has no configured defaults.)
        oscBridge->sendGetInstruments(paths);
    }
}

//==============================================================================
// FXChainPanel::Listener
void MainComponent::fxChainChanged(FXChainPanel* panel)
{
    if (panel == nullptr) return;
    
    DBG("FX chain updated");
    currentStatus = "FX chain updated";
    
    // Apply FX chain to real-time MixerGraph
    auto& mixerGraph = audioEngine.getMixerGraph();
    
    // Get chains for each bus and apply to MixerGraph
    juce::StringArray buses = { "master", "drums", "bass", "melodic" };
    for (const auto& bus : buses)
    {
        auto chain = panel->getChainForBus(bus);
        
        // Convert to JSON var for MixerGraph
        juce::Array<juce::var> chainArray;
        for (const auto& fx : chain)
        {
            chainArray.add(fx.toJSON());
        }
        
        mixerGraph.setFXChainForBus(bus, juce::var(chainArray));
    }
    
    // Also send to Python backend for offline render parity
    if (oscBridge && oscBridge->isConnected())
    {
        auto fxJson = panel->toJSON();
        oscBridge->sendFXChain(fxJson);
        DBG("FX chain sent to server");
    }
    
    repaint();
}

//==============================================================================
// ExpansionBrowserPanel::Listener
void MainComponent::requestExpansionListOSC()
{
    if (!ensureBackendConnected("Request expansion list"))
        return;

    DBG("MainComponent: Requesting expansion list");
    oscBridge->sendExpansionList();
}

void MainComponent::requestInstrumentsOSC(const juce::String& expansionId)
{
    if (!ensureBackendConnected("Request expansion instruments"))
        return;

    DBG("MainComponent: Requesting instruments for expansion: " + expansionId);
    oscBridge->sendExpansionInstruments(expansionId);
}

void MainComponent::requestResolveOSC(const juce::String& instrument, const juce::String& genre)
{
    if (!ensureBackendConnected("Resolve expansion instrument"))
        return;

    DBG("MainComponent: Resolving instrument: " + instrument + " for genre: " + genre);
    oscBridge->sendExpansionResolve(instrument, genre);
}

void MainComponent::requestImportExpansionOSC(const juce::String& path)
{
    if (!ensureBackendConnected("Import expansion"))
        return;

    DBG("MainComponent: Importing expansion from: " + path);
    oscBridge->sendExpansionImport(path);

    // Refresh list after import
    juce::Timer::callAfterDelay(1000, [this]() {
        requestExpansionListOSC();
    });
}

void MainComponent::requestScanExpansionsOSC(const juce::String& directory)
{
    if (!ensureBackendConnected("Scan expansions"))
        return;

    DBG("MainComponent: Scanning expansions in: " + directory);
    oscBridge->sendExpansionScan(directory);

    // Refresh list after scan
    juce::Timer::callAfterDelay(2000, [this]() {
        requestExpansionListOSC();
    });
}

void MainComponent::requestExpansionEnableOSC(const juce::String& expansionId, bool enabled)
{
    if (!ensureBackendConnected("Enable/disable expansion"))
        return;

    DBG("MainComponent: Setting expansion " + expansionId + " enabled=" + (enabled ? "true" : "false"));
    oscBridge->sendExpansionEnable(expansionId, enabled);

    // Refresh expansion list to get updated state
    juce::Timer::callAfterDelay(500, [this]() {
        requestExpansionListOSC();
    });
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
// OSCBridge::Listener take callbacks
void MainComponent::onTakesAvailable(const juce::String& json)
{
    DBG("MainComponent: Received takes available");
    
    juce::MessageManager::callAsync([this, json]() {
        if (takeLanePanel)
        {
            takeLanePanel->setAvailableTakes(json);
            
            // Auto-show the takes panel when takes become available
            if (takeLanePanel->hasTakes() && !bottomPanelVisible)
            {
                showToolWindow(5);  // 5 = Takes
            }
        }
    });
}

void MainComponent::onTakeSelected(const juce::String& track, const juce::String& takeId)
{
    DBG("MainComponent: Take selected - " << track << " / " << takeId);
    
    juce::MessageManager::callAsync([this, track, takeId]() {
        if (takeLanePanel)
            takeLanePanel->confirmTakeSelection(track, takeId);
        
        currentStatus = "Take selected: " + track + " / " + takeId;
        repaint();
    });
}

void MainComponent::onTakeRendered(const juce::String& track, const juce::String& outputPath)
{
    DBG("MainComponent: Take rendered - " << track << " -> " << outputPath);
    
    juce::MessageManager::callAsync([this, track, outputPath]() {
        // Load the rendered audio
        juce::File audioFile(outputPath);
        if (audioFile.existsAsFile())
        {
            audioEngine.loadAudioFile(audioFile);
        }
        
        currentStatus = "Take rendered: " + track;
        repaint();
    });
}

//==============================================================================
// TakeLanePanel::Listener implementation
void MainComponent::takeSelected(const juce::String& track, const juce::String& takeId, const juce::String& midiPath)
{
    DBG("MainComponent: User selected take - " << track << " / " << takeId << " (" << midiPath << ")");

    const bool applied = applyTakeCompToProject(track, takeId, midiPath);

    // Ensure playback updates immediately (don't rely on async ValueTree callbacks).
    if (applied)
    {
        auto midi = appState.getProjectState().exportToMidiFile();
        audioEngine.loadMidiData(midi);
        hasAuditionBackupMidi = false; // selection becomes the new "main" state
    }

    // Send selection to server via OSC (for persistence / future render comp)
    if (oscBridge)
        oscBridge->sendSelectTake(track, takeId);

    currentStatus = applied
        ? ("Comp applied: " + track + " / " + takeId)
        : ("Selecting take: " + track + " / " + takeId);
    repaint();
}

void MainComponent::takePlayRequested(const juce::String& track, const juce::String& takeId, const juce::String& midiPath)
{
    DBG("MainComponent: User requested take playback - " << track << " / " << takeId << " (" << midiPath << ")");

    // Audition should not modify the main project state/visualization. Back up the current
    // project MIDI so we can restore after the audition.
    auditionBackupMidi = appState.getProjectState().exportToMidiFile();
    hasAuditionBackupMidi = true;

    juce::File midiFile(midiPath);
    if (!midiFile.existsAsFile())
    {
        // Try to resolve relative paths against common roots.
        auto cwdCandidate = juce::File::getCurrentWorkingDirectory().getChildFile(midiPath);
        if (cwdCandidate.existsAsFile())
            midiFile = cwdCandidate;
        else
        {
            auto exeDir = juce::File::getSpecialLocation(juce::File::currentExecutableFile).getParentDirectory();
            auto exeCandidate = exeDir.getChildFile(midiPath);
            if (exeCandidate.existsAsFile())
                midiFile = exeCandidate;
        }
    }

    if (!midiFile.existsAsFile())
    {
        currentStatus = "Take MIDI not found: " + track + " / " + takeId;
        repaint();
        return;
    }

    if (audioEngine.loadMidiFile(midiFile))
    {
        audioEngine.play();
        currentStatus = "Auditioning take: " + track + " / " + takeId;
    }
    else
    {
        currentStatus = "Failed to load take MIDI: " + midiFile.getFileName();
    }

    repaint();
}

void MainComponent::takeStopRequested(const juce::String& track)
{
    juce::ignoreUnused(track);
    audioEngine.stop();

    // Restore main project playback MIDI after audition.
    if (hasAuditionBackupMidi)
    {
        audioEngine.loadMidiData(auditionBackupMidi);
        hasAuditionBackupMidi = false;
    }

    currentStatus = "Audition stopped";
    repaint();
}

void MainComponent::renderTakesRequested()
{
    DBG("MainComponent: User requested render of selected takes");
    
    if (oscBridge)
    {
        // Build render request from selected takes in each track
        TakeRenderRequest request;
        request.generateRequestId();
        request.useComp = true;  // Render the current comp
        
        // Output path in project output directory
        auto outputDir = juce::File::getSpecialLocation(juce::File::currentExecutableFile)
            .getParentDirectory().getParentDirectory().getParentDirectory()
            .getParentDirectory().getChildFile("output");
        request.outputPath = outputDir.getFullPathName();
        
        oscBridge->sendRenderTake(request);
        
        currentStatus = "Rendering takes...";
        repaint();
    }
}

void MainComponent::commitCompRequested()
{
    takeCompSnapshots.clear();
    currentStatus = "Comp committed";
    repaint();
}

void MainComponent::revertCompRequested()
{
    auto& projectState = appState.getProjectState();
    for (auto& kv : takeCompSnapshots)
        projectState.restoreNotesForTrack(kv.first, kv.second);

    takeCompSnapshots.clear();
    currentStatus = "Comp reverted";
    repaint();
}

int MainComponent::resolveTrackIndexForName(const juce::String& trackName)
{
    const auto nameLower = trackName.trim().toLowerCase();

    auto mixerNode = appState.getProjectState().getMixerNode();
    if (mixerNode.isValid())
    {
        for (auto child : mixerNode)
        {
            if (!child.hasType(Project::IDs::TRACK))
                continue;
            auto n = child.getProperty(Project::IDs::name).toString().trim().toLowerCase();
            if (n.isNotEmpty() && n == nameLower)
                return (int)child.getProperty(Project::IDs::index);
        }
    }

    // Common fallbacks
    if (nameLower == "drums" || nameLower == "drum") return 0;
    if (nameLower == "bass" || nameLower == "808") return 1;
    if (nameLower == "chords" || nameLower == "keys") return 2;
    if (nameLower == "melody" || nameLower == "lead") return 3;

    return -1;
}

juce::File MainComponent::resolveTakeMidiFile(const juce::String& midiPath) const
{
    juce::File midiFile(midiPath);
    if (midiFile.existsAsFile())
        return midiFile;

    auto cwdCandidate = juce::File::getCurrentWorkingDirectory().getChildFile(midiPath);
    if (cwdCandidate.existsAsFile())
        return cwdCandidate;

    auto exeDir = juce::File::getSpecialLocation(juce::File::currentExecutableFile).getParentDirectory();
    auto exeCandidate = exeDir.getChildFile(midiPath);
    if (exeCandidate.existsAsFile())
        return exeCandidate;

    return juce::File();
}

bool MainComponent::applyTakeCompToProject(const juce::String& track, const juce::String& takeId, const juce::String& midiPath)
{
    juce::ignoreUnused(takeId);

    const int trackIndex = resolveTrackIndexForName(track);
    if (trackIndex < 0)
        return false;

    auto midiFile = resolveTakeMidiFile(midiPath);
    if (!midiFile.existsAsFile())
        return false;

    auto& projectState = appState.getProjectState();
    if (takeCompSnapshots.find(trackIndex) == takeCompSnapshots.end())
        takeCompSnapshots[trackIndex] = projectState.copyNotesForTrack(trackIndex);

    return projectState.replaceNotesForTrackFromMidiFile(trackIndex, midiFile);
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
// TimelineComponent::Listener
void MainComponent::timelineSeekRequested(double positionSeconds)
{
    audioEngine.setPlaybackPosition(positionSeconds);
}

void MainComponent::loopRegionChanged(double startSeconds, double endSeconds)
{
    // Sync loop region to PianoRoll via VisualizationPanel
    if (visualizationPanel)
    {
        if (startSeconds >= 0 && endSeconds > startSeconds)
            visualizationPanel->setLoopRegion(startSeconds, endSeconds);
        else
            visualizationPanel->clearLoopRegion();
    }
    
    DBG("MainComponent: Loop region changed: " << startSeconds << " - " << endSeconds);
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
    static bool expansionsScanned = false;
    
    if (!oscBridge)
    {
        setupOSCConnection();
        
        // Scan local expansions after OSC is set up
        if (!expansionsScanned)
        {
            scanLocalExpansions();
            expansionsScanned = true;
        }
        return;
    }
    
    // Scan expansions if not done yet
    if (!expansionsScanned)
    {
        scanLocalExpansions();
        expansionsScanned = true;
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
    // ==========================================================================
    // Skip global shortcuts if a TextEditor has keyboard focus
    // This allows normal text editing (paste, cut, copy, etc.)
    // ==========================================================================
    auto* focusedComponent = juce::Component::getCurrentlyFocusedComponent();
    if (dynamic_cast<juce::TextEditor*>(focusedComponent) != nullptr)
    {
        // Let text editing keys pass through to TextEditor
        // Only handle Escape to unfocus
        if (key.isKeyCode(juce::KeyPress::escapeKey))
        {
            focusedComponent->giveAwayKeyboardFocus();
            currentStatus = "Exited text input";
            return true;
        }
        // Don't consume any other keys - let TextEditor handle them
        return false;
    }
    
    // ==========================================================================
    // Transport Controls (DAW-standard shortcuts)
    // ==========================================================================
    
    // Space: Toggle Play/Pause
    if (key.isKeyCode(juce::KeyPress::spaceKey))
    {
        if (audioEngine.isPlaying())
            audioEngine.pause();
        else
            audioEngine.play();
        currentStatus = audioEngine.isPlaying() ? "Playing" : "Paused";
        return true;
    }
    
    // Home: Return to start (position 0)
    if (key.isKeyCode(juce::KeyPress::homeKey))
    {
        if (key.getModifiers().isShiftDown() && timelineComponent && timelineComponent->hasLoopRegion())
        {
            // Shift+Home: Go to loop start
            audioEngine.setPlaybackPosition(timelineComponent->getLoopRegionStart());
            currentStatus = "At loop start";
        }
        else
        {
            // Home: Go to start
            audioEngine.setPlaybackPosition(0.0);
            currentStatus = "At start";
        }
        return true;
    }
    
    // End: Go to end of track
    if (key.isKeyCode(juce::KeyPress::endKey))
    {
        if (key.getModifiers().isShiftDown() && timelineComponent && timelineComponent->hasLoopRegion())
        {
            // Shift+End: Go to loop end
            audioEngine.setPlaybackPosition(timelineComponent->getLoopRegionEnd());
            currentStatus = "At loop end";
        }
        else
        {
            // End: Go to end
            double duration = audioEngine.getTotalDuration();
            if (duration > 0)
            {
                audioEngine.setPlaybackPosition(duration);
                currentStatus = "At end";
            }
        }
        return true;
    }
    
    // L: Toggle loop on/off
    if (key.isKeyCode('l') && !key.getModifiers().isCommandDown())
    {
        bool currentLooping = audioEngine.isLooping();
        audioEngine.setLooping(!currentLooping);
        currentStatus = audioEngine.isLooping() ? "Loop ON" : "Loop OFF";
        return true;
    }
    
    // Delete/Backspace on loop region: Clear loop
    if ((key.isKeyCode(juce::KeyPress::deleteKey) || key.isKeyCode(juce::KeyPress::backspaceKey))
        && timelineComponent && timelineComponent->hasLoopRegion())
    {
        timelineComponent->clearLoopRegion();
        currentStatus = "Loop region cleared";
        return true;
    }
    
    // ==========================================================================
    // Navigation (Bar/Beat Skipping)
    // ==========================================================================
    
    // Arrow keys for navigation
    if (key.isKeyCode(juce::KeyPress::leftKey) || key.isKeyCode(juce::KeyPress::rightKey))
    {
        double currentPos = audioEngine.getPlaybackPosition();
        int bpm = appState.getBPM();
        double secondsPerBeat = 60.0 / bpm;
        double secondsPerBar = secondsPerBeat * 4.0;  // Assume 4/4 time
        
        double skipAmount;
        juce::String skipType;
        
        if (key.getModifiers().isShiftDown())
        {
            // Shift+Arrow: Fine control (1 beat)
            skipAmount = secondsPerBeat;
            skipType = "beat";
        }
        else if (key.getModifiers().isCommandDown())
        {
            // Ctrl+Arrow: Skip 4 bars
            skipAmount = secondsPerBar * 4.0;
            skipType = "4 bars";
        }
        else
        {
            // Arrow: Skip 1 bar
            skipAmount = secondsPerBar;
            skipType = "bar";
        }
        
        double newPos;
        if (key.isKeyCode(juce::KeyPress::rightKey))
        {
            newPos = juce::jmin(currentPos + skipAmount, audioEngine.getTotalDuration());
            currentStatus = "Skip forward " + skipType;
        }
        else
        {
            newPos = juce::jmax(currentPos - skipAmount, 0.0);
            currentStatus = "Skip back " + skipType;
        }
        
        audioEngine.setPlaybackPosition(newPos);
        return true;
    }
    
    // ==========================================================================
    // Undo/Redo (Standard shortcuts)
    // ==========================================================================
    
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
    
    // ==========================================================================
    // Quick Generation (G key)
    // ==========================================================================
    
    // G: Focus prompt panel (for quick generation)
    if (key.isKeyCode('g') && !key.getModifiers().isCommandDown() && !key.getModifiers().isAltDown())
    {
        if (promptPanel)
        {
            // This would focus the prompt input - requires grabKeyboardFocus on the TextEditor
            // For now, just indicate the intent
            currentStatus = "Press Enter in prompt to generate";
        }
        return true;
    }
    
    // Escape: Stop playback or cancel generation
    if (key.isKeyCode(juce::KeyPress::escapeKey))
    {
        if (audioEngine.isPlaying())
        {
            audioEngine.stop();
            currentStatus = "Stopped";
        }
        return true;
    }
    
    return false;
}
