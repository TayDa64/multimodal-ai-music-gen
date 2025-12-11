/*
  ==============================================================================

    VisualizationPanel.cpp
    
    Implementation of the tabbed visualization panel.

  ==============================================================================
*/

#include "VisualizationPanel.h"
#include "Theme/ColourScheme.h"

//==============================================================================
VisualizationPanel::VisualizationPanel(AppState& state, mmg::AudioEngine& engine)
    : appState(state),
      audioEngine(engine)
{
    // Create piano roll
    pianoRoll = std::make_unique<PianoRollComponent>(audioEngine);
    pianoRoll->addListener(this);
    pianoRoll->setBPM(appState.getBPM());
    addChildComponent(*pianoRoll);
    
    // Create recent files panel
    recentFiles = std::make_unique<RecentFilesPanel>(appState, audioEngine);
    recentFiles->addListener(this);
    addAndMakeVisible(*recentFiles);
    
    // Setup tab buttons
    pianoRollTab.setClickingTogglesState(false);
    pianoRollTab.setColour(juce::TextButton::buttonColourId, AppColours::surfaceAlt);
    pianoRollTab.onClick = [this]() { showTab(0); };
    addAndMakeVisible(pianoRollTab);
    
    recentFilesTab.setClickingTogglesState(false);
    recentFilesTab.setColour(juce::TextButton::buttonColourId, AppColours::surfaceAlt);
    recentFilesTab.onClick = [this]() { showTab(1); };
    addAndMakeVisible(recentFilesTab);
    
    // Note info label
    noteInfoLabel.setFont(juce::Font(11.0f));
    noteInfoLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    noteInfoLabel.setJustificationType(juce::Justification::centredRight);
    addAndMakeVisible(noteInfoLabel);
    
    updateTabButtons();
}

VisualizationPanel::~VisualizationPanel()
{
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
    
    int tabWidth = 100;
    pianoRollTab.setBounds(tabBar.removeFromLeft(tabWidth).reduced(2, 2));
    recentFilesTab.setBounds(tabBar.removeFromLeft(tabWidth).reduced(2, 2));
    
    // Note info label on right side of tab bar
    noteInfoLabel.setBounds(tabBar.removeFromRight(200).reduced(4, 2));
    
    // Content area
    auto contentArea = bounds;
    
    if (pianoRoll)
        pianoRoll->setBounds(contentArea);
    if (recentFiles)
        recentFiles->setBounds(contentArea);
}

//==============================================================================
void VisualizationPanel::loadMidiFile(const juce::File& midiFile)
{
    if (pianoRoll && midiFile.existsAsFile())
    {
        pianoRoll->loadMidiFile(midiFile);
        showTab(0);  // Switch to piano roll when loading MIDI
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
    currentTab = index;
    
    if (pianoRoll)
        pianoRoll->setVisible(index == 0);
    if (recentFiles)
        recentFiles->setVisible(index == 1);
    
    updateTabButtons();
}

void VisualizationPanel::setBPM(int bpm)
{
    if (pianoRoll)
        pianoRoll->setBPM(bpm);
}

void VisualizationPanel::updateTabButtons()
{
    // Highlight active tab
    juce::Colour activeColour = AppColours::primary;
    juce::Colour inactiveColour = AppColours::surfaceAlt;
    
    pianoRollTab.setColour(juce::TextButton::buttonColourId, 
                           currentTab == 0 ? activeColour : inactiveColour);
    recentFilesTab.setColour(juce::TextButton::buttonColourId, 
                              currentTab == 1 ? activeColour : inactiveColour);
    
    // Clear note info when not on piano roll
    if (currentTab != 0)
        noteInfoLabel.setText("", juce::dontSendNotification);
}

//==============================================================================
void VisualizationPanel::fileSelected(const juce::File& file)
{
    // Forward to our listeners using explicit lambda to avoid ambiguity
    listeners.call([&file](Listener& l) { l.fileSelected(file); });
    
    // If it's a MIDI file, also load it into the piano roll
    if (file.hasFileExtension(".mid;.midi"))
    {
        loadMidiFile(file);
    }
}

void VisualizationPanel::pianoRollNoteHovered(const MidiNoteEvent* note)
{
    if (note != nullptr)
    {
        juce::String info = MidiNoteEvent::getNoteName(note->noteNumber);
        info += " | Vel: " + juce::String(note->velocity);
        info += " | Track " + juce::String(note->trackIndex + 1);
        noteInfoLabel.setText(info, juce::dontSendNotification);
    }
    else
    {
        noteInfoLabel.setText("", juce::dontSendNotification);
    }
}

void VisualizationPanel::pianoRollSeekRequested(double positionSeconds)
{
    // AudioEngine is already updated by piano roll, just log for debugging
    DBG("Piano roll seek to: " << positionSeconds << "s");
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
