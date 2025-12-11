/*
  ==============================================================================

    AudioSettingsDialog.cpp
    
    Implementation of the audio settings dialog.

  ==============================================================================
*/

#include "AudioSettingsDialog.h"
#include "Theme/ColourScheme.h"

//==============================================================================
AudioSettingsDialog::AudioSettingsDialog(mmg::AudioEngine& engine)
    : audioEngine(engine)
{
    // Title
    titleLabel.setText("Audio Output Settings", juce::dontSendNotification);
    titleLabel.setFont(juce::Font(18.0f, juce::Font::bold));
    titleLabel.setColour(juce::Label::textColourId, AppColours::textPrimary);
    addAndMakeVisible(titleLabel);
    
    // Info label
    infoLabel.setFont(juce::Font(12.0f));
    infoLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    infoLabel.setJustificationType(juce::Justification::topLeft);
    addAndMakeVisible(infoLabel);
    
    // Setup device selector
    setupDeviceSelector();
    
    // Close button
    closeButton.setColour(juce::TextButton::buttonColourId, AppColours::primary);
    closeButton.onClick = [this]() {
        if (auto* parent = findParentComponentOfClass<juce::DialogWindow>())
            parent->closeButtonPressed();
        else if (auto* window = findParentComponentOfClass<AudioSettingsWindow>())
            window->closeButtonPressed();
    };
    addAndMakeVisible(closeButton);
    
    // Update info
    updateInfoLabel();
    
    // Set size
    setSize(450, 380);
}

AudioSettingsDialog::~AudioSettingsDialog()
{
    deviceSelector = nullptr;
}

//==============================================================================
void AudioSettingsDialog::setupDeviceSelector()
{
    // Create the JUCE audio device selector component
    // Parameters:
    // - AudioDeviceManager
    // - Min input channels (0 = no input)
    // - Max input channels (0 = no input)
    // - Min output channels (1 = at least mono)
    // - Max output channels (2 = stereo)
    // - Show MIDI input options
    // - Show MIDI output options
    // - Show channels as stereo pairs
    // - Hide advanced options
    deviceSelector = std::make_unique<juce::AudioDeviceSelectorComponent>(
        audioEngine.getDeviceManager(),
        0, 0,     // No input channels
        1, 2,     // 1-2 output channels (mono/stereo)
        false,    // No MIDI input
        false,    // No MIDI output
        true,     // Show stereo pairs
        false     // Don't hide advanced options (show sample rate, buffer)
    );
    
    addAndMakeVisible(*deviceSelector);
}

void AudioSettingsDialog::updateInfoLabel()
{
    juce::String info;
    
    auto* device = audioEngine.getDeviceManager().getCurrentAudioDevice();
    if (device)
    {
        info += "Current Device: " + device->getName() + "\n";
        info += "Sample Rate: " + juce::String(device->getCurrentSampleRate()) + " Hz\n";
        info += "Buffer Size: " + juce::String(device->getCurrentBufferSizeSamples()) + " samples\n";
        
        double latencyMs = (device->getCurrentBufferSizeSamples() / device->getCurrentSampleRate()) * 1000.0;
        info += "Latency: ~" + juce::String(latencyMs, 1) + " ms\n";
    }
    else
    {
        info = "No audio device selected.\n\n";
        info += "Select an output device from the list above.";
    }
    
    infoLabel.setText(info, juce::dontSendNotification);
}

//==============================================================================
void AudioSettingsDialog::paint(juce::Graphics& g)
{
    // Background
    g.fillAll(AppColours::background);
    
    // Border
    g.setColour(AppColours::border);
    g.drawRect(getLocalBounds(), 1);
}

void AudioSettingsDialog::resized()
{
    auto bounds = getLocalBounds().reduced(16);
    
    // Title at top
    titleLabel.setBounds(bounds.removeFromTop(30));
    bounds.removeFromTop(8);
    
    // Close button at bottom
    auto buttonArea = bounds.removeFromBottom(35);
    closeButton.setBounds(buttonArea.removeFromRight(100).withHeight(30));
    bounds.removeFromBottom(8);
    
    // Info label at bottom (above button)
    infoLabel.setBounds(bounds.removeFromBottom(80));
    bounds.removeFromBottom(8);
    
    // Device selector takes remaining space
    if (deviceSelector)
        deviceSelector->setBounds(bounds);
}

//==============================================================================
void AudioSettingsDialog::showDialog(mmg::AudioEngine& engine, juce::Component* parent)
{
    auto* dialog = new AudioSettingsDialog(engine);
    
    juce::DialogWindow::LaunchOptions options;
    options.dialogTitle = "Audio Settings";
    options.dialogBackgroundColour = AppColours::background;
    options.content.setOwned(dialog);
    options.componentToCentreAround = parent;
    options.escapeKeyTriggersCloseButton = true;
    options.useNativeTitleBar = true;
    options.resizable = false;
    
    options.launchAsync();
}
