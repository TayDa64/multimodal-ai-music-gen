/*
  ==============================================================================

    TransportComponent.cpp
    
    Implementation of transport controls.

  ==============================================================================
*/

#include "TransportComponent.h"
#include "Theme/ColourScheme.h"

//==============================================================================
TransportComponent::TransportComponent(AppState& state)
    : appState(state)
{
    setupButtons();
    setupSliders();
    setupLabels();
    
    appState.addListener(this);
    startTimerHz(30); // Update display at 30fps
}

TransportComponent::~TransportComponent()
{
    appState.removeListener(this);
    stopTimer();
}

//==============================================================================
void TransportComponent::setupButtons()
{
    // Play button
    playButton.setColour(juce::TextButton::buttonColourId, ColourScheme::success);
    playButton.onClick = [this] { playClicked(); };
    addAndMakeVisible(playButton);
    
    // Pause button
    pauseButton.setColour(juce::TextButton::buttonColourId, ColourScheme::warning);
    pauseButton.onClick = [this] { pauseClicked(); };
    pauseButton.setEnabled(false);
    addAndMakeVisible(pauseButton);
    
    // Stop button
    stopButton.setColour(juce::TextButton::buttonColourId, ColourScheme::error);
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
            listeners.call(&Listener::transportPositionChanged, currentPosition);
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
        listeners.call(&Listener::transportBPMChanged, newBPM);
    };
    addAndMakeVisible(bpmSlider);
}

void TransportComponent::setupLabels()
{
    // Position label
    positionLabel.setText("Position", juce::dontSendNotification);
    positionLabel.setColour(juce::Label::textColourId, ColourScheme::textSecondary);
    addAndMakeVisible(positionLabel);
    
    // BPM label
    bpmLabel.setText("BPM", juce::dontSendNotification);
    bpmLabel.setColour(juce::Label::textColourId, ColourScheme::textSecondary);
    addAndMakeVisible(bpmLabel);
    
    // Time display
    timeDisplay.setText("0:00", juce::dontSendNotification);
    timeDisplay.setFont(juce::Font(16.0f, juce::Font::bold));
    timeDisplay.setJustificationType(juce::Justification::centredRight);
    addAndMakeVisible(timeDisplay);
    
    // Duration display
    durationDisplay.setText("/ 0:00", juce::dontSendNotification);
    durationDisplay.setColour(juce::Label::textColourId, ColourScheme::textSecondary);
    durationDisplay.setJustificationType(juce::Justification::centredLeft);
    addAndMakeVisible(durationDisplay);
    
    // Status label
    statusLabel.setText("Ready", juce::dontSendNotification);
    statusLabel.setColour(juce::Label::textColourId, ColourScheme::textSecondary);
    statusLabel.setJustificationType(juce::Justification::centredLeft);
    addAndMakeVisible(statusLabel);
    
    // Connection indicator
    connectionIndicator.setText(juce::String::charToString(0x25CF) + " Disconnected", juce::dontSendNotification);
    connectionIndicator.setColour(juce::Label::textColourId, ColourScheme::error);
    connectionIndicator.setJustificationType(juce::Justification::centredRight);
    addAndMakeVisible(connectionIndicator);
}

//==============================================================================
void TransportComponent::paint(juce::Graphics& g)
{
    // Background
    g.setColour(ColourScheme::surface);
    g.fillRect(getLocalBounds());
    
    // Bottom border
    g.setColour(ColourScheme::border);
    g.drawLine(0.0f, (float)getHeight() - 0.5f, (float)getWidth(), (float)getHeight() - 0.5f, 1.0f);
}

void TransportComponent::resized()
{
    auto bounds = getLocalBounds().reduced(8, 4);
    
    // Left section - transport buttons
    auto leftSection = bounds.removeFromLeft(200);
    auto buttonHeight = 28;
    auto buttonWidth = 60;
    auto buttonY = (bounds.getHeight() - buttonHeight) / 2 + bounds.getY() - 4;
    
    playButton.setBounds(leftSection.getX(), buttonY, buttonWidth, buttonHeight);
    pauseButton.setBounds(leftSection.getX() + buttonWidth + 4, buttonY, buttonWidth, buttonHeight);
    stopButton.setBounds(leftSection.getX() + (buttonWidth + 4) * 2, buttonY, buttonWidth, buttonHeight);
    
    // Right section - BPM and status
    auto rightSection = bounds.removeFromRight(280);
    
    // Connection indicator
    connectionIndicator.setBounds(rightSection.removeFromRight(120));
    rightSection.removeFromRight(8);
    
    // BPM control
    bpmLabel.setBounds(rightSection.removeFromLeft(35).withHeight(20).withY(buttonY + 4));
    bpmSlider.setBounds(rightSection.removeFromLeft(100).withHeight(20).withY(buttonY + 4));
    
    // Center section - position
    bounds.removeFromLeft(16);
    bounds.removeFromRight(16);
    
    // Time display
    auto timeSection = bounds.removeFromLeft(100);
    timeDisplay.setBounds(timeSection.removeFromLeft(45).withHeight(20).withY(buttonY + 4));
    durationDisplay.setBounds(timeSection.withHeight(20).withY(buttonY + 4));
    
    bounds.removeFromLeft(8);
    
    // Position slider (fills remaining space)
    positionSlider.setBounds(bounds.withHeight(20).withY(buttonY + 4));
    
    // Status at bottom
    auto statusBounds = getLocalBounds().reduced(8);
    statusLabel.setBounds(statusBounds.removeFromBottom(16));
}

//==============================================================================
void TransportComponent::updateButtonStates()
{
    bool hasAudio = appState.getOutputFile().existsAsFile();
    
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
    isPlaying = true;
    updateButtonStates();
    listeners.call(&Listener::transportPlayRequested);
}

void TransportComponent::pauseClicked()
{
    isPlaying = false;
    updateButtonStates();
    listeners.call(&Listener::transportPauseRequested);
}

void TransportComponent::stopClicked()
{
    isPlaying = false;
    currentPosition = 0.0;
    updateTimeDisplay();
    updateButtonStates();
    listeners.call(&Listener::transportStopRequested);
}

//==============================================================================
void TransportComponent::onGenerationStarted()
{
    juce::MessageManager::callAsync([this] {
        statusLabel.setText("Generating...", juce::dontSendNotification);
        statusLabel.setColour(juce::Label::textColourId, ColourScheme::primary);
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
        statusLabel.setColour(juce::Label::textColourId, ColourScheme::success);
        
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
        statusLabel.setColour(juce::Label::textColourId, ColourScheme::error);
    });
}

void TransportComponent::onConnectionStatusChanged(bool connected)
{
    juce::MessageManager::callAsync([this, connected] {
        if (connected)
        {
            connectionIndicator.setText(juce::String::charToString(0x25CF) + " Connected", 
                                        juce::dontSendNotification);
            connectionIndicator.setColour(juce::Label::textColourId, ColourScheme::success);
        }
        else
        {
            connectionIndicator.setText(juce::String::charToString(0x25CF) + " Disconnected", 
                                        juce::dontSendNotification);
            connectionIndicator.setColour(juce::Label::textColourId, ColourScheme::error);
        }
    });
}

//==============================================================================
void TransportComponent::timerCallback()
{
    // Update playback position if playing
    // This would be driven by actual audio playback in the future
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
