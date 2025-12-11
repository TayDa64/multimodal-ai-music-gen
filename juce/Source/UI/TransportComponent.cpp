/*
  ==============================================================================

    TransportComponent.cpp
    
    Implementation of transport controls.

  ==============================================================================
*/

#include "TransportComponent.h"
#include "Theme/ColourScheme.h"

//==============================================================================
TransportComponent::TransportComponent(AppState& state, mmg::AudioEngine& engine)
    : appState(state),
      audioEngine(engine)
{
    setupButtons();
    setupSliders();
    setupLabels();
    
    appState.addListener(this);
    audioEngine.addListener(this);
    startTimerHz(30); // Update display at 30fps
}

TransportComponent::~TransportComponent()
{
    appState.removeListener(this);
    audioEngine.removeListener(this);
    stopTimer();
}

//==============================================================================
void TransportComponent::setupButtons()
{
    // Play button
    playButton.setColour(juce::TextButton::buttonColourId, AppColours::success);
    playButton.onClick = [this] { playClicked(); };
    addAndMakeVisible(playButton);
    
    // Pause button
    pauseButton.setColour(juce::TextButton::buttonColourId, AppColours::warning);
    pauseButton.onClick = [this] { pauseClicked(); };
    pauseButton.setEnabled(false);
    addAndMakeVisible(pauseButton);
    
    // Stop button
    stopButton.setColour(juce::TextButton::buttonColourId, AppColours::error);
    stopButton.onClick = [this] { stopClicked(); };
    stopButton.setEnabled(false);
    addAndMakeVisible(stopButton);
}

void TransportComponent::setupSliders()
{
    // Position slider
    positionSlider.setSliderStyle(juce::Slider::LinearHorizontal);
    positionSlider.setTextBoxStyle(juce::Slider::NoTextBox, true, 0, 0);
    positionSlider.setRange(0.0, 1.0, 0.001);
    positionSlider.setValue(0.0);
    positionSlider.onValueChange = [this] {
        if (!isPlaying)
        {
            currentPosition = positionSlider.getValue() * totalDuration;
            updateTimeDisplay();
            listeners.call(&TransportComponent::Listener::transportPositionChanged, currentPosition);
        }
    };
    addAndMakeVisible(positionSlider);
    
    // BPM slider
    bpmSlider.setSliderStyle(juce::Slider::LinearHorizontal);
    bpmSlider.setTextBoxStyle(juce::Slider::TextBoxRight, false, 45, 20);
    bpmSlider.setRange(60, 200, 1);
    bpmSlider.setValue(appState.getBPM());
    bpmSlider.onValueChange = [this] {
        int newBPM = (int)bpmSlider.getValue();
        appState.setBPM(newBPM);
        listeners.call(&TransportComponent::Listener::transportBPMChanged, newBPM);
    };
    addAndMakeVisible(bpmSlider);
    
    // Test tone toggle (for verifying audio output works)
    testToneButton.setColour(juce::ToggleButton::textColourId, AppColours::textSecondary);
    testToneButton.setColour(juce::ToggleButton::tickColourId, AppColours::primary);
    testToneButton.onClick = [this] {
        bool enabled = testToneButton.getToggleState();
        audioEngine.setTestToneEnabled(enabled);
        if (enabled && !audioEngine.isPlaying())
        {
            audioEngine.play(); // Start playback to hear the test tone
        }
        else if (!enabled && audioEngine.isPlaying())
        {
            audioEngine.stop();
        }
    };
    addAndMakeVisible(testToneButton);
    
    // Load MIDI button (for testing MIDI playback)
    loadMidiButton.setColour(juce::TextButton::buttonColourId, AppColours::primary);
    loadMidiButton.onClick = [this] {
        // Open file chooser for MIDI files
        auto chooser = std::make_shared<juce::FileChooser>(
            "Select a MIDI file...",
            juce::File::getSpecialLocation(juce::File::userDocumentsDirectory),
            "*.mid;*.midi"
        );
        
        chooser->launchAsync(juce::FileBrowserComponent::openMode | juce::FileBrowserComponent::canSelectFiles,
            [this, chooser](const juce::FileChooser& fc)
            {
                auto file = fc.getResult();
                if (file.existsAsFile())
                {
                    if (audioEngine.loadMidiFile(file))
                    {
                        totalDuration = audioEngine.getTotalDuration();
                        currentPosition = 0.0;
                        updateTimeDisplay();
                        updateButtonStates();
                        statusLabel.setText("Loaded: " + file.getFileName(), juce::dontSendNotification);
                        statusLabel.setColour(juce::Label::textColourId, AppColours::success);
                        
                        // Disable test tone when loading MIDI
                        testToneButton.setToggleState(false, juce::dontSendNotification);
                        audioEngine.setTestToneEnabled(false);
                    }
                    else
                    {
                        statusLabel.setText("Failed to load MIDI", juce::dontSendNotification);
                        statusLabel.setColour(juce::Label::textColourId, AppColours::error);
                    }
                }
            });
    };
    addAndMakeVisible(loadMidiButton);
}

void TransportComponent::setupLabels()
{
    // Position label
    positionLabel.setText("Position", juce::dontSendNotification);
    positionLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(positionLabel);
    
    // BPM label
    bpmLabel.setText("BPM", juce::dontSendNotification);
    bpmLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(bpmLabel);
    
    // Time display
    timeDisplay.setText("0:00", juce::dontSendNotification);
    timeDisplay.setFont(juce::Font(16.0f, juce::Font::bold));
    timeDisplay.setJustificationType(juce::Justification::centredRight);
    addAndMakeVisible(timeDisplay);
    
    // Duration display
    durationDisplay.setText("/ 0:00", juce::dontSendNotification);
    durationDisplay.setColour(juce::Label::textColourId, AppColours::textSecondary);
    durationDisplay.setJustificationType(juce::Justification::centredLeft);
    addAndMakeVisible(durationDisplay);
    
    // Status label (shows playback status like "Ready", "Playing", "Loaded: file.mid")
    statusLabel.setText("Ready", juce::dontSendNotification);
    statusLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    statusLabel.setJustificationType(juce::Justification::centredRight);
    addAndMakeVisible(statusLabel);
    
    // Connection indicator - REMOVED (now shown only in main status bar)
    // This avoids duplicate status indicators which confuse users
    connectionIndicator.setVisible(false);
}

//==============================================================================
void TransportComponent::paint(juce::Graphics& g)
{
    // Background
    g.setColour(AppColours::surface);
    g.fillRect(getLocalBounds());
    
    // Bottom border
    g.setColour(AppColours::border);
    g.drawLine(0.0f, (float)getHeight() - 0.5f, (float)getWidth(), (float)getHeight() - 0.5f, 1.0f);
}

void TransportComponent::resized()
{
    auto bounds = getLocalBounds().reduced(8, 4);
    auto buttonHeight = 28;
    auto buttonWidth = 60;
    auto centerY = bounds.getCentreY() - buttonHeight / 2;
    
    // Left section - transport buttons + load MIDI
    auto leftSection = bounds.removeFromLeft(280);
    
    playButton.setBounds(leftSection.getX(), centerY, buttonWidth, buttonHeight);
    pauseButton.setBounds(leftSection.getX() + buttonWidth + 4, centerY, buttonWidth, buttonHeight);
    stopButton.setBounds(leftSection.getX() + (buttonWidth + 4) * 2, centerY, buttonWidth, buttonHeight);
    loadMidiButton.setBounds(leftSection.getX() + (buttonWidth + 4) * 3, centerY, 70, buttonHeight);
    
    // Right section - Status, BPM, test tone
    auto rightSection = bounds.removeFromRight(340);
    
    // Status label (right-aligned) - shows "Ready", "Playing", "Loaded: file.mid"
    statusLabel.setBounds(rightSection.removeFromRight(140).withHeight(20).withY(centerY + 4));
    rightSection.removeFromRight(8);
    
    // Test tone button
    testToneButton.setBounds(rightSection.removeFromRight(90).withHeight(20).withY(centerY + 4));
    rightSection.removeFromRight(8);
    
    // BPM control
    bpmLabel.setBounds(rightSection.removeFromLeft(35).withHeight(20).withY(centerY + 4));
    bpmSlider.setBounds(rightSection.removeFromLeft(100).withHeight(20).withY(centerY + 4));
    
    // Center section - time display and position slider
    bounds.removeFromLeft(16);
    bounds.removeFromRight(16);
    
    // Time display
    auto timeSection = bounds.removeFromLeft(100);
    timeDisplay.setBounds(timeSection.removeFromLeft(45).withHeight(20).withY(centerY + 4));
    durationDisplay.setBounds(timeSection.withHeight(20).withY(centerY + 4));
    
    bounds.removeFromLeft(8);
    
    // Position slider (fills remaining space)
    positionSlider.setBounds(bounds.withHeight(20).withY(centerY + 4));
}

//==============================================================================
void TransportComponent::updateButtonStates()
{
    // Enable play if we have MIDI loaded or an audio file
    bool hasAudio = appState.getOutputFile().existsAsFile() || audioEngine.hasMidiLoaded();
    
    playButton.setEnabled(hasAudio && !isPlaying);
    pauseButton.setEnabled(hasAudio && isPlaying);
    stopButton.setEnabled(hasAudio && (isPlaying || currentPosition > 0));
    positionSlider.setEnabled(hasAudio);
}

void TransportComponent::updateTimeDisplay()
{
    // Format time as M:SS
    int currentSecs = (int)currentPosition;
    int totalSecs = (int)totalDuration;
    
    juce::String currentStr = juce::String(currentSecs / 60) + ":" + 
                              juce::String(currentSecs % 60).paddedLeft('0', 2);
    juce::String totalStr = juce::String(totalSecs / 60) + ":" + 
                            juce::String(totalSecs % 60).paddedLeft('0', 2);
    
    timeDisplay.setText(currentStr, juce::dontSendNotification);
    durationDisplay.setText("/ " + totalStr, juce::dontSendNotification);
    
    if (totalDuration > 0)
        positionSlider.setValue(currentPosition / totalDuration, juce::dontSendNotification);
}

//==============================================================================
void TransportComponent::playClicked()
{
    audioEngine.play();
    isPlaying = true;
    updateButtonStates();
    listeners.call(&TransportComponent::Listener::transportPlayRequested);
}

void TransportComponent::pauseClicked()
{
    audioEngine.pause();
    isPlaying = false;
    updateButtonStates();
    listeners.call(&TransportComponent::Listener::transportPauseRequested);
}

void TransportComponent::stopClicked()
{
    audioEngine.stop();
    isPlaying = false;
    currentPosition = 0.0;
    updateTimeDisplay();
    updateButtonStates();
    listeners.call(&TransportComponent::Listener::transportStopRequested);
}

//==============================================================================
void TransportComponent::onGenerationStarted()
{
    juce::MessageManager::callAsync([this] {
        statusLabel.setText("Generating...", juce::dontSendNotification);
        statusLabel.setColour(juce::Label::textColourId, AppColours::primary);
    });
}

void TransportComponent::onGenerationProgress(const GenerationProgress& progress)
{
    juce::MessageManager::callAsync([this, progress] {
        statusLabel.setText(progress.stepName + " (" + 
                           juce::String((int)(progress.progress * 100)) + "%)",
                           juce::dontSendNotification);
    });
}

void TransportComponent::onGenerationCompleted(const juce::File& outputFile)
{
    juce::MessageManager::callAsync([this, outputFile] {
        statusLabel.setText("Ready: " + outputFile.getFileName(), juce::dontSendNotification);
        statusLabel.setColour(juce::Label::textColourId, AppColours::success);
        
        // TODO: Get actual duration from audio file
        totalDuration = (double)appState.getDurationBars() * 60.0 / (double)appState.getBPM() * 4.0;
        currentPosition = 0.0;
        updateTimeDisplay();
        updateButtonStates();
    });
}

void TransportComponent::onGenerationError(const juce::String& error)
{
    juce::MessageManager::callAsync([this, error] {
        statusLabel.setText("Error: " + error, juce::dontSendNotification);
        statusLabel.setColour(juce::Label::textColourId, AppColours::error);
    });
}

void TransportComponent::onConnectionStatusChanged(bool /*connected*/)
{
    // Connection status now shown in main status bar only
    // This prevents duplicate/confusing status indicators
}

//==============================================================================
// AudioEngine::Listener
void TransportComponent::transportStateChanged(mmg::AudioEngine::TransportState newState)
{
    juce::MessageManager::callAsync([this, newState] {
        using State = mmg::AudioEngine::TransportState;
        
        switch (newState)
        {
            case State::Playing:
                isPlaying = true;
                playButton.setEnabled(false);
                pauseButton.setEnabled(true);
                stopButton.setEnabled(true);
                break;
                
            case State::Paused:
                isPlaying = false;
                playButton.setEnabled(true);
                pauseButton.setEnabled(false);
                stopButton.setEnabled(true);
                break;
                
            case State::Stopped:
                isPlaying = false;
                playButton.setEnabled(true);
                pauseButton.setEnabled(false);
                stopButton.setEnabled(false);
                currentPosition = 0.0;
                updateTimeDisplay();
                // Sync test tone button state
                testToneButton.setToggleState(false, juce::dontSendNotification);
                break;
                
            default:
                break;
        }
    });
}

void TransportComponent::audioDeviceChanged()
{
    // Could update UI to show current audio device info
    DBG("TransportComponent: Audio device changed");
}

//==============================================================================
void TransportComponent::timerCallback()
{
    // Update playback position if playing
    if (audioEngine.isPlaying() && audioEngine.hasMidiLoaded())
    {
        currentPosition = audioEngine.getPlaybackPosition();
        totalDuration = audioEngine.getTotalDuration();
        updateTimeDisplay();
    }
}

//==============================================================================
void TransportComponent::addListener(Listener* listener)
{
    listeners.add(listener);
}

void TransportComponent::removeListener(Listener* listener)
{
    listeners.remove(listener);
}
