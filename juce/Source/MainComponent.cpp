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
/**
    Custom DocumentWindow with graceful close handling.
    Notifies parent before deletion to prevent dangling pointers.
*/
class MainComponent::GracefulDocumentWindow : public juce::DocumentWindow
{
public:
    GracefulDocumentWindow(const juce::String& name, 
                          juce::Colour backgroundColour,
                          int buttonsNeeded,
                          std::function<void()> onCloseCallback)
        : DocumentWindow(name, backgroundColour, buttonsNeeded),
          closeCallback(onCloseCallback)
    {
        setUsingNativeTitleBar(true);
        setResizable(true, false);
    }
    
    void closeButtonPressed() override
    {
        // Gracefully notify parent and schedule deletion
        if (closeCallback)
        {
            // Use MessageManager to ensure we're on the message thread
            // and that the close happens after this function returns
            juce::MessageManager::callAsync([cb = closeCallback]() 
            { 
                if (cb) cb(); 
            });
        }
    }
    
private:
    std::function<void()> closeCallback;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(GracefulDocumentWindow)
};

//==============================================================================
MainComponent::MainComponent(AppState& state, mmg::AudioEngine& engine)
    : appState(state),
      audioEngine(engine)
{
    // Listen to project state changes
    appState.getProjectState().getState().addListener(this);

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
}

MainComponent::~MainComponent()
{
    appState.getProjectState().getState().removeListener(this);
    stopTimer();
    
    // Close floating window
    expansionsWindow.reset();
    
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
    
    // Instrument Browser - shown in bottom panel when triggered
    instrumentBrowser = std::make_unique<InstrumentBrowserPanel>(audioEngine.getDeviceManager());
    instrumentBrowser->setVisible(false);
    addAndMakeVisible(*instrumentBrowser);
    
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
    
    // Now add listeners AFTER all components are created
    genreSelector->addListener(this);
    instrumentBrowser->addListener(this);
    fxChainPanel->addListener(this);
    expansionBrowser->addListener(this);
    
    // Set default genre
    genreSelector->setSelectedGenre("trap");
    
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
    // 1 = Instruments (bottom panel), 2 = FX Chain (bottom), 3 = Expansions (floating), 4 = Mixer (bottom)
    
    switch (toolId)
    {
        case 1: // Instruments - bottom panel
        {
            if (currentBottomTool == 1 && bottomPanelVisible)
            {
                hideBottomPanel();
            }
            else
            {
                bottomPanelVisible = true;
                currentBottomTool = 1;
                if (instrumentBrowser) instrumentBrowser->setVisible(true);
                if (fxChainPanel) fxChainPanel->setVisible(false);
                if (mixerComponent) mixerComponent->setVisible(false);
                resized();
                
                // Request data if needed
                if (instrumentBrowser)
                    instrumentBrowser->requestInstrumentData();
            }
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
                resized();
            }
            break;
        }
        
        case 3: // Expansions - floating window
        {
            if (!expansionsWindow)
            {
                expansionsWindow = std::make_unique<GracefulDocumentWindow>(
                    "Expansions",
                    AppColours::background,
                    juce::DocumentWindow::allButtons,
                    [this]() {
                        // Graceful close callback - reset the window pointer
                        expansionsWindow.reset();
                    });
                expansionsWindow->setContentNonOwned(expansionBrowser.get(), true);
                expansionsWindow->centreWithSize(700, 500);
            }
            expansionsWindow->setVisible(true);
            expansionsWindow->toFront(true);
            
            // Request expansion list
            if (expansionBrowser)
                expansionBrowser->requestExpansionList();
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
                resized();
            }
            break;
        }
    }
}

void MainComponent::hideBottomPanel()
{
    bottomPanelVisible = false;
    currentBottomTool = 0;
    if (instrumentBrowser) instrumentBrowser->setVisible(false);
    if (fxChainPanel) fxChainPanel->setVisible(false);
    if (mixerComponent) mixerComponent->setVisible(false);
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
    
    // Bottom panel with Instruments/FX/Mixer - only when visible (toggle from Tools menu)
    if (bottomPanelVisible)
    {
        int bottomPanelHeight = Layout::getAdaptiveBottomPanelHeight(bounds.getHeight());
        auto bottomArea = bounds.removeFromBottom(bottomPanelHeight);
        bottomPanelArea = bottomArea.reduced(adaptivePadding, 0);
        
        if (instrumentBrowser && currentBottomTool == 1)
            instrumentBrowser->setBounds(bottomPanelArea);
        if (fxChainPanel && currentBottomTool == 2)
            fxChainPanel->setBounds(bottomPanelArea);
        if (mixerComponent && currentBottomTool == 4)
            mixerComponent->setBounds(bottomPanelArea);
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
    
    if (oscBridge && oscBridge->isConnected())
    {
        GenerationRequest request;
        request.prompt = prompt;
        request.genre = currentGenre;  // Pass genre from GenreSelector
        request.bpm = appState.getBPM();
        request.bars = appState.getDurationBars();
        request.renderAudio = true;
        
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

void MainComponent::analyzeUrlRequested(const juce::String& url)
{
    if (oscBridge && oscBridge->isConnected())
    {
        currentStatus = "Analyzing URL...";
        oscBridge->sendAnalyzeUrl(url, false);
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
        // We send "instruments" to point to the default instruments folder
        oscBridge->sendGetInstruments({"instruments"});
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

void MainComponent::requestExpansionEnableOSC(const juce::String& expansionId, bool enabled)
{
    if (oscBridge && oscBridge->isConnected())
    {
        DBG("MainComponent: Setting expansion " + expansionId + " enabled=" + (enabled ? "true" : "false"));
        oscBridge->sendExpansionEnable(expansionId, enabled);
        
        // Refresh expansion list to get updated state
        juce::Timer::callAfterDelay(500, [this]() {
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
