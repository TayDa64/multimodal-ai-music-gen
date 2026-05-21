/*
  ==============================================================================

    TransportComponent.cpp
    
    Implementation of transport controls.

  ==============================================================================
*/

#include "TransportComponent.h"
#include "Theme/ColourScheme.h"
#include "Theme/LayoutConstants.h"
#include "AudioSettingsDialog.h"

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
    playButton.setTooltip("Play the loaded audio file/reference or dry MIDI preview.");
    playButton.onClick = [this] { playClicked(); };
    addAndMakeVisible(playButton);
    
    // Pause button
    pauseButton.setColour(juce::TextButton::buttonColourId, AppColours::warning);
    pauseButton.setTooltip("Pause the current audio file/reference or dry MIDI preview.");
    pauseButton.onClick = [this] { pauseClicked(); };
    pauseButton.setEnabled(false);
    addAndMakeVisible(pauseButton);
    
    // Stop button
    stopButton.setColour(juce::TextButton::buttonColourId, AppColours::error);
    stopButton.setTooltip("Stop playback and return to the start of the current audio file/reference or dry MIDI preview.");
    stopButton.onClick = [this] { stopClicked(); };
    stopButton.setEnabled(false);
    addAndMakeVisible(stopButton);

    // Loop button
    loopButton.setColour(juce::ToggleButton::textColourId, AppColours::textSecondary);
    loopButton.setColour(juce::ToggleButton::tickColourId, AppColours::primary);
    loopButton.setTooltip("Loop the currently loaded preview/reference.");
    loopButton.onClick = [this] {
        audioEngine.setLooping(loopButton.getToggleState());
    };
    addAndMakeVisible(loopButton);
    
    // Tools dropdown button (MPC-style - replaces bottom tabs)
    toolsButton.setColour(juce::TextButton::buttonColourId, AppColours::surface.brighter(0.1f));
    toolsButton.setColour(juce::TextButton::textColourOffId, AppColours::textPrimary);
    toolsButton.onClick = [this] {
        juce::PopupMenu menu;
        menu.addItem(1, "Instruments", true, false);
        menu.addItem(2, "FX Chain", true, false);
        menu.addItem(3, "Expansions", true, false);
        menu.addItem(4, "Mixer", true, false);
        menu.addItem(5, "Takes", true, false);
        menu.addItem(6, "Controls", true, false);
        menu.addSeparator();
        menu.addItem(7, "Mastering Suite", true, false);  // New 8-feature mastering suite
        
        menu.showMenuAsync(juce::PopupMenu::Options()
            .withTargetComponent(&toolsButton)
            .withMinimumWidth(140),
            [this](int result) {
                if (result > 0)
                    listeners.call(&Listener::toolsMenuItemSelected, result);
            });
    };
    addAndMakeVisible(toolsButton);
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
    testToneButton.setTooltip("Play a dry test tone through the audio device. This does not use live FX or mastering.");
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
    loadMidiButton.setTooltip("Load a MIDI file for dry/unmastered preview only (no live FX/mastering).");
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
                        setStatusText("Loaded dry/unmastered MIDI preview: " + file.getFileName()
                                          + " (no live FX/mastering)",
                                      AppColours::success);
                        
                        // Disable test tone when loading MIDI
                        testToneButton.setToggleState(false, juce::dontSendNotification);
                        audioEngine.setTestToneEnabled(false);
                    }
                    else
                    {
                        setStatusText("Failed to load MIDI", AppColours::error);
                    }
                }
            });
    };
    addAndMakeVisible(loadMidiButton);
    
    // Audio settings button
    audioSettingsButton.setColour(juce::TextButton::buttonColourId, AppColours::surfaceAlt);
    audioSettingsButton.setTooltip("Audio Settings");
    audioSettingsButton.onClick = [this] {
        AudioSettingsDialog::showDialog(audioEngine, this);
    };
    addAndMakeVisible(audioSettingsButton);
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
    
    // Bar:Beat display
    barBeatDisplay.setText("1:1", juce::dontSendNotification);
    barBeatDisplay.setFont(juce::Font(12.0f));
    barBeatDisplay.setColour(juce::Label::textColourId, AppColours::primary);
    barBeatDisplay.setJustificationType(juce::Justification::centred);
    barBeatDisplay.setTooltip("Bar : Beat");
    addAndMakeVisible(barBeatDisplay);
    
    // Duration display
    durationDisplay.setText("/ 0:00", juce::dontSendNotification);
    durationDisplay.setColour(juce::Label::textColourId, AppColours::textSecondary);
    durationDisplay.setJustificationType(juce::Justification::centredLeft);
    addAndMakeVisible(durationDisplay);
    
    // Status label (shows playback status like "Ready", "Playing", "Loaded: file.mid")
    statusLabel.setJustificationType(juce::Justification::centredLeft);
    setStatusText("Ready", AppColours::textSecondary);
    addAndMakeVisible(statusLabel);

    capabilityLabel.setFont(juce::Font(10.0f));
    capabilityLabel.setColour(juce::Label::textColourId, AppColours::textSecondary.withAlpha(0.9f));
    capabilityLabel.setJustificationType(juce::Justification::centredLeft);
    capabilityLabel.setText(getCapabilityHelperText(), juce::dontSendNotification);
    capabilityLabel.setTooltip(buildStatusTooltip("Playback scope reference"));
    addAndMakeVisible(capabilityLabel);
    
    // Connection indicator - REMOVED (now shown only in main status bar)
    // This avoids duplicate status indicators which confuse users
    connectionIndicator.setVisible(false);
}

void TransportComponent::setStatusText(const juce::String& text, juce::Colour colour)
{
    statusLabel.setText(text, juce::dontSendNotification);
    statusLabel.setColour(juce::Label::textColourId, colour);
    statusLabel.setTooltip(buildStatusTooltip(text));
}

juce::String TransportComponent::getCapabilityHelperText() const
{
    return "Scope: backend WAV/reference = mastered offline | live MIDI = dry/no live FX/mastering | external audio = generic reference";
}

juce::String TransportComponent::buildStatusTooltip(const juce::String& status) const
{
    return status
        + "\n\nPlayback scope:\n"
        + "- Backend-generated WAV/reference = mastered offline path\n"
        + "- Live MIDI preview = dry/unmastered with no live FX/mastering\n"
        + "- External loaded audio = generic audio file/reference unless provenance is known";
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
    auto bounds = getLocalBounds().reduced(Layout::paddingMD, 2);
    auto helperArea = bounds.removeFromBottom(12);
    capabilityLabel.setBounds(helperArea);

    const int buttonHeight = Layout::buttonHeightMD;
    const int buttonWidth = 60;
    const int smallButtonWidth = 50;
    const int centerY = bounds.getCentreY() - buttonHeight / 2;
    
    // Use FlexBox for responsive layout
    // Left section - transport buttons + Tools dropdown
    juce::FlexBox leftFlex = Layout::createRowFlex();
    leftFlex.items.add(juce::FlexItem(playButton).withWidth((float)buttonWidth).withHeight((float)buttonHeight));
    leftFlex.items.add(juce::FlexItem().withWidth(4.0f));  // Gap
    leftFlex.items.add(juce::FlexItem(pauseButton).withWidth((float)buttonWidth).withHeight((float)buttonHeight));
    leftFlex.items.add(juce::FlexItem().withWidth(4.0f));
    leftFlex.items.add(juce::FlexItem(stopButton).withWidth((float)buttonWidth).withHeight((float)buttonHeight));
    leftFlex.items.add(juce::FlexItem().withWidth(4.0f));
    leftFlex.items.add(juce::FlexItem(loopButton).withWidth((float)smallButtonWidth).withHeight((float)buttonHeight));
    leftFlex.items.add(juce::FlexItem().withWidth(8.0f));
    leftFlex.items.add(juce::FlexItem(loadMidiButton).withWidth(70.0f).withHeight((float)buttonHeight));
    leftFlex.items.add(juce::FlexItem().withWidth(4.0f));
    leftFlex.items.add(juce::FlexItem(audioSettingsButton).withWidth(30.0f).withHeight((float)buttonHeight));
    leftFlex.items.add(juce::FlexItem().withWidth(12.0f));  // Larger gap before Tools
    leftFlex.items.add(juce::FlexItem(toolsButton).withWidth(60.0f).withHeight((float)buttonHeight));  // Tools dropdown
    
    // Calculate left section width (increased to accommodate Tools)
    int leftSectionWidth = juce::jmin(440, bounds.getWidth() / 2);
    auto leftSection = bounds.removeFromLeft(leftSectionWidth);
    leftFlex.performLayout(leftSection.withY(centerY).withHeight(buttonHeight));
    
    // Right section - Status, BPM, test tone. Keep BPM/test-tone fixed and let
    // the truthful mastered/unmastered status label expand when room permits.
    const int fixedRightControlsWidth = 35 + 100 + 8 + 90 + 8;
    const int minStatusLabelWidth = 180;
    const int maxStatusLabelWidth = 320;
    const int minCenterSectionWidth = 220;
    const int minRightSectionWidth = fixedRightControlsWidth + minStatusLabelWidth;
    const int maxRightSectionWidth = fixedRightControlsWidth + maxStatusLabelWidth;
    const int availableForRight = bounds.getWidth() - minCenterSectionWidth;
    int rightSectionWidth = juce::jlimit(minRightSectionWidth,
                                        maxRightSectionWidth,
                                        juce::jmax(minRightSectionWidth, availableForRight));
    rightSectionWidth = juce::jmin(rightSectionWidth, bounds.getWidth());
    const float statusLabelWidth = (float)juce::jmax(0, rightSectionWidth - fixedRightControlsWidth);
    auto rightSection = bounds.removeFromRight(rightSectionWidth);
    
    juce::FlexBox rightFlex = Layout::createRowFlex(juce::FlexBox::JustifyContent::flexEnd);
    rightFlex.items.add(juce::FlexItem(bpmLabel).withWidth(35.0f).withHeight(20.0f));
    rightFlex.items.add(juce::FlexItem(bpmSlider).withWidth(100.0f).withHeight(20.0f));
    rightFlex.items.add(juce::FlexItem().withWidth(8.0f));
    rightFlex.items.add(juce::FlexItem(testToneButton).withWidth(90.0f).withHeight(20.0f));
    rightFlex.items.add(juce::FlexItem().withWidth(8.0f));
    rightFlex.items.add(juce::FlexItem(statusLabel).withWidth(statusLabelWidth).withHeight(20.0f));
    rightFlex.performLayout(rightSection.withY(centerY + 4).withHeight(20));
    
    // Center section - time display and position slider
    bounds.removeFromLeft(Layout::paddingLG);
    bounds.removeFromRight(Layout::paddingLG);
    
    // Time display section (fixed width)
    auto timeSection = bounds.removeFromLeft(130);
    
    juce::FlexBox timeFlex = Layout::createRowFlex();
    timeFlex.items.add(juce::FlexItem(timeDisplay).withWidth(45.0f).withHeight(20.0f));
    timeFlex.items.add(juce::FlexItem(durationDisplay).withWidth(45.0f).withHeight(20.0f));
    timeFlex.items.add(juce::FlexItem(barBeatDisplay).withFlex(1.0f).withHeight(20.0f));
    timeFlex.performLayout(timeSection.withY(centerY + 4).withHeight(20));
    
    bounds.removeFromLeft(Layout::paddingMD);
    
    // Position slider (fills remaining space)
    positionSlider.setBounds(bounds.withY(centerY + 4).withHeight(20));
}

//==============================================================================
void TransportComponent::updateButtonStates()
{
    // Enable play if the engine has MIDI or an audio file loaded.
    bool hasAudio = audioEngine.hasAudioFileLoaded() || audioEngine.hasMidiLoaded();
    
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
    
    // Calculate bar:beat display
    int bpm = appState.getBPM();
    if (bpm > 0)
    {
        double secondsPerBeat = 60.0 / bpm;
        double totalBeats = currentPosition / secondsPerBeat;
        
        int bar = (int)(totalBeats / 4.0) + 1;  // 4 beats per bar
        int beat = (int)std::fmod(totalBeats, 4.0) + 1;
        
        barBeatDisplay.setText(juce::String(bar) + ":" + juce::String(beat), 
                               juce::dontSendNotification);
    }
    
    if (totalDuration > 0)
        positionSlider.setValue(currentPosition / totalDuration, juce::dontSendNotification);
}

//==============================================================================
void TransportComponent::playClicked()
{
    // Debug: Show state before playing
    bool hasLoadedAudio = audioEngine.hasAudioFileLoaded();
    bool hasMidi = audioEngine.hasMidiLoaded();
    double duration = audioEngine.getTotalDuration();
    
    if (!hasLoadedAudio && !hasMidi)
    {
        setStatusText("No audio or MIDI loaded - generate or load a file first", AppColours::error);
        return;
    }
    
    audioEngine.play();
    isPlaying = true;
    updateButtonStates();
    
    setStatusText(juce::String(hasLoadedAudio
                                   ? "Playing loaded audio file/reference... (dur: "
                                   : "Playing dry/unmastered MIDI preview... (dur: ")
                      + juce::String(duration, 1)
                      + (hasLoadedAudio ? "s)" : "s, no live FX/mastering)"),
                  AppColours::success);
    
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
        setStatusText("Generating...", AppColours::primary);
    });
}

void TransportComponent::onGenerationProgress(const GenerationProgress& progress)
{
    juce::MessageManager::callAsync([this, progress] {
        setStatusText(progress.stepName + " (" +
                          juce::String((int)(progress.progress * 100)) + "%)",
                      AppColours::primary);
    });
}

void TransportComponent::onGenerationCompleted(const juce::File& outputFile)
{
    juce::MessageManager::callAsync([this, outputFile] {
        const bool outputIsAudio = outputFile.hasFileExtension(".wav;.wave;.aiff;.aif;.flac;.mp3;.ogg");
        const bool outputIsMidi = outputFile.hasFileExtension(".mid;.midi");
        const juce::String readyStatus = outputIsAudio
            ? "Ready backend mastered reference: " + outputFile.getFileName()
            : (outputIsMidi
                   ? "Ready dry/unmastered MIDI preview/fallback: " + outputFile.getFileName()
                         + " (no live FX/mastering)"
                   : "Ready: " + outputFile.getFileName());
        setStatusText(readyStatus, AppColours::success);
        
        // Get actual duration from AudioEngine if MIDI or audio is loaded
        if (audioEngine.hasAudioFileLoaded() || audioEngine.hasMidiLoaded())
        {
            totalDuration = audioEngine.getTotalDuration();
        }
        else
        {
            // Fallback to calculated duration from BPM and bars
            totalDuration = (double)appState.getDurationBars() * 60.0 / (double)appState.getBPM() * 4.0;
        }
        
        currentPosition = 0.0;
        updateTimeDisplay();
        updateButtonStates();
    });
}

void TransportComponent::onGenerationError(const juce::String& error)
{
    juce::MessageManager::callAsync([this, error] {
        setStatusText("Error: " + error, AppColours::error);
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
                // Sync test tone button state AND engine state
                audioEngine.setTestToneEnabled(false);
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
    const bool hasLoadedAudio = audioEngine.hasAudioFileLoaded();
    const bool hasMidi = audioEngine.hasMidiLoaded();
    const bool hasPlayableMedia = hasLoadedAudio || hasMidi;

    if (audioEngine.isPlaying() && hasPlayableMedia)
    {
        currentPosition = audioEngine.getPlaybackPosition();
        totalDuration = audioEngine.getTotalDuration();
        updateTimeDisplay();
        
        // Show detailed playback debug status with honest mastering-path labeling.
        setStatusText(juce::String(hasLoadedAudio
                                       ? "Playing loaded audio file/reference: "
                                       : "Playing dry/unmastered MIDI preview (no live FX/mastering): ")
                          + audioEngine.getPlaybackDebugStatus(),
                      AppColours::success);
    }
    
    // Check if button states need update (e.g. if MIDI was loaded externally)
    if (hasPlayableMedia != lastHasAudioState)
    {
        lastHasAudioState = hasPlayableMedia;
        updateButtonStates();
        
        // Update status when playable media is loaded
        if (hasLoadedAudio)
        {
            setStatusText("Loaded audio file/reference: "
                              + juce::String(audioEngine.getTotalDuration(), 1) + "s",
                          AppColours::success);
        }
        else if (hasMidi)
        {
            setStatusText("Dry/unmastered MIDI preview loaded: "
                              + juce::String(audioEngine.getTotalDuration(), 1)
                              + "s (no live FX/mastering)",
                          AppColours::success);
        }
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
