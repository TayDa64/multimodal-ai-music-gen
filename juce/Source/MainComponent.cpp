/*
  ==============================================================================

    MainComponent.cpp
    
    Implementation of the root UI component.

  ==============================================================================
*/

#include "MainComponent.h"
#include "UI/Theme/ColourScheme.h"

//==============================================================================
MainComponent::MainComponent(AppState& state)
    : appState(state)
{
    // Set size
    setSize(1280, 800);
    
    // Create UI components
    transportBar = std::make_unique<TransportComponent>(appState);
    addAndMakeVisible(*transportBar);
    
    promptPanel = std::make_unique<PromptPanel>(appState);
    promptPanel->addListener(this);
    addAndMakeVisible(*promptPanel);
    
    progressOverlay = std::make_unique<ProgressOverlay>(appState);
    progressOverlay->addListener(this);
    addChildComponent(*progressOverlay); // Hidden by default
    
    // Setup OSC connection
    setupOSCConnection();
    
    // Start timer for status updates
    startTimerHz(10);
}

MainComponent::~MainComponent()
{
    stopTimer();
    
    if (oscBridge)
        oscBridge->removeListener(this);
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
void MainComponent::paint(juce::Graphics& g)
{
    // Background
    g.fillAll(ColourScheme::background);
    
    // Draw placeholder areas
    drawPlaceholder(g, visualizationArea, 
                   "Visualization\n(Piano Roll / Waveform)", 
                   ColourScheme::surface);
    
    drawPlaceholder(g, bottomPanelArea, 
                   "Mixer / Instrument Browser", 
                   ColourScheme::surfaceAlt);
    
    // Connection status indicator
    auto statusArea = getLocalBounds().removeFromBottom(20).reduced(padding);
    g.setColour(ColourScheme::textSecondary);
    g.setFont(12.0f);
    
    juce::String statusText = serverConnected 
        ? juce::String(juce::CharPointer_UTF8("● Connected")) 
        : juce::String(juce::CharPointer_UTF8("○ Disconnected"));
    g.setColour(serverConnected ? ColourScheme::success : ColourScheme::textSecondary);
    g.drawText(statusText, statusArea, juce::Justification::left);
    
    g.setColour(ColourScheme::textSecondary);
    g.drawText(currentStatus, statusArea, juce::Justification::right);
}

void MainComponent::resized()
{
    auto bounds = getLocalBounds();
    
    // Reserve space for status bar
    bounds.removeFromBottom(20);
    
    // Transport bar at top
    transportBar->setBounds(bounds.removeFromTop(transportHeight));
    
    // Bottom panel
    bottomPanelArea = bounds.removeFromBottom(bottomPanelHeight);
    
    // Main content area
    auto contentArea = bounds.reduced(padding);
    
    // Prompt panel on left
    promptPanel->setBounds(contentArea.removeFromLeft(promptPanelWidth));
    
    // Visualization takes remaining space
    contentArea.removeFromLeft(padding);
    visualizationArea = contentArea;
    
    // Progress overlay covers the whole component
    progressOverlay->setBounds(getLocalBounds());
}

//==============================================================================
void MainComponent::drawPlaceholder(juce::Graphics& g, juce::Rectangle<int> area,
                                   const juce::String& label, juce::Colour colour)
{
    // Background
    g.setColour(colour);
    g.fillRoundedRectangle(area.toFloat(), 6.0f);
    
    // Border
    g.setColour(ColourScheme::border);
    g.drawRoundedRectangle(area.toFloat(), 6.0f, 1.0f);
    
    // Label
    g.setColour(ColourScheme::textSecondary.withAlpha(0.5f));
    g.setFont(16.0f);
    g.drawText(label, area, juce::Justification::centred);
}

//==============================================================================
void MainComponent::onConnectionStatusChanged(bool connected)
{
    serverConnected = connected;
    currentStatus = connected ? "Ready" : "Server not running";
    
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
        appState.setOutputFile(juce::File(result.audioPath.isNotEmpty() 
            ? result.audioPath : result.midiPath));
        
        // Show completion message
        juce::String message = "Generation complete!\n\n";
        message += "MIDI: " + result.midiPath + "\n";
        if (result.audioPath.isNotEmpty())
            message += "Audio: " + result.audioPath + "\n";
        message += "\nDuration: " + juce::String(result.duration, 1) + "s";
        
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
    currentStatus = "Error: " + message;
    
    juce::MessageManager::callAsync([this, message]()
    {
        juce::AlertWindow::showMessageBoxAsync(
            juce::MessageBoxIconType::WarningIcon,
            "Generation Error",
            message
        );
        
        repaint();
    });
}

//==============================================================================
// PromptPanel::Listener
void MainComponent::generateRequested(const juce::String& prompt)
{
    if (oscBridge && oscBridge->isConnected())
    {
        GenerationRequest request;
        request.prompt = prompt;
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
}

//==============================================================================
void MainComponent::timerCallback()
{
    // Periodic health check
    if (oscBridge && !oscBridge->isConnected())
    {
        // Try to reconnect
        oscBridge->connect();
    }
}
