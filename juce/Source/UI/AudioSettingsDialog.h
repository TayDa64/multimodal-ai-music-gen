/*
  ==============================================================================

    AudioSettingsDialog.h
    
    Audio device settings dialog for output device selection, sample rate,
    and buffer size configuration.
    
    Task 4.6: Audio device settings

  ==============================================================================
*/

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include <juce_audio_utils/juce_audio_utils.h>
#include "../Audio/AudioEngine.h"

//==============================================================================
/**
    Dialog window for configuring audio output settings.
    
    Provides:
    - Output device selection
    - Sample rate selection
    - Buffer size configuration
    - ASIO support (Windows)
*/
class AudioSettingsDialog : public juce::Component
{
public:
    //==============================================================================
    AudioSettingsDialog(mmg::AudioEngine& engine);
    ~AudioSettingsDialog() override;

    //==============================================================================
    void paint(juce::Graphics& g) override;
    void resized() override;
    
    //==============================================================================
    /** Show the dialog as a modal window */
    static void showDialog(mmg::AudioEngine& engine, juce::Component* parent);
    
    /** Get the recommended minimum size for this dialog */
    static juce::Rectangle<int> getRecommendedSize() { return { 0, 0, 450, 380 }; }

private:
    //==============================================================================
    mmg::AudioEngine& audioEngine;
    
    // JUCE's built-in audio device selector
    std::unique_ptr<juce::AudioDeviceSelectorComponent> deviceSelector;
    
    // Info labels
    juce::Label titleLabel;
    juce::Label infoLabel;
    
    // Close button
    juce::TextButton closeButton { "Close" };
    
    // Layout
    void setupDeviceSelector();
    void updateInfoLabel();
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(AudioSettingsDialog)
};

//==============================================================================
/**
    Dialog window wrapper for AudioSettingsDialog.
*/
class AudioSettingsWindow : public juce::DocumentWindow
{
public:
    AudioSettingsWindow(mmg::AudioEngine& engine)
        : juce::DocumentWindow("Audio Settings",
                               juce::Desktop::getInstance().getDefaultLookAndFeel()
                                   .findColour(juce::ResizableWindow::backgroundColourId),
                               juce::DocumentWindow::closeButton)
    {
        setUsingNativeTitleBar(true);
        setContentOwned(new AudioSettingsDialog(engine), true);
        setResizable(false, false);
        centreWithSize(getWidth(), getHeight());
        setVisible(true);
    }
    
    void closeButtonPressed() override
    {
        delete this;
    }

private:
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(AudioSettingsWindow)
};
