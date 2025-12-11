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
    DBG("VisualizationPanel constructor");
    
    // Create piano roll
    pianoRoll = std::make_unique<PianoRollComponent>(audioEngine);
    pianoRoll->addListener(this);
    pianoRoll->setBPM(appState.getBPM());
    addChildComponent(*pianoRoll);  // Start hidden
    
    // Create recent files panel
    recentFiles = std::make_unique<RecentFilesPanel>(appState, audioEngine);
    recentFiles->addListener(this);
    addAndMakeVisible(*recentFiles);  // Start visible
    
    // Setup tab buttons with distinct styling
    pianoRollTab.setClickingTogglesState(false);
    pianoRollTab.setColour(juce::TextButton::buttonColourId, AppColours::surfaceAlt);
    pianoRollTab.setColour(juce::TextButton::textColourOnId, AppColours::textPrimary);
    pianoRollTab.setColour(juce::TextButton::textColourOffId, AppColours::textSecondary);
    pianoRollTab.onClick = [this]() { 
        DBG("Piano Roll tab clicked");
        showTab(0); 
    };
    addAndMakeVisible(pianoRollTab);
    
    recentFilesTab.setClickingTogglesState(false);
    recentFilesTab.setColour(juce::TextButton::buttonColourId, AppColours::surfaceAlt);
    recentFilesTab.setColour(juce::TextButton::textColourOnId, AppColours::textPrimary);
    recentFilesTab.setColour(juce::TextButton::textColourOffId, AppColours::textSecondary);
    recentFilesTab.onClick = [this]() { 
        DBG("Recent Files tab clicked");
        showTab(1); 
    };
    addAndMakeVisible(recentFilesTab);
    
    // Note info label
    noteInfoLabel.setFont(juce::Font(11.0f));
    noteInfoLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    noteInfoLabel.setJustificationType(juce::Justification::centredRight);
    addAndMakeVisible(noteInfoLabel);
    
    // Initialize tab state
    currentTab = 1;  // Start with Recent Files visible
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
    DBG("VisualizationPanel::loadMidiFile: " << midiFile.getFullPathName());
    
    if (pianoRoll && midiFile.existsAsFile())
    {
        pianoRoll->loadMidiFile(midiFile);
        showTab(0);  // Switch to piano roll when loading MIDI
        DBG("  Switched to piano roll tab");
    }
    else
    {
        DBG("  ERROR: pianoRoll is null or file doesn't exist");
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
    DBG("VisualizationPanel::showTab(" << index << ")");
    currentTab = index;
    
    if (pianoRoll)
    {
        pianoRoll->setVisible(index == 0);
        if (index == 0)
        {
            pianoRoll->repaint();
            DBG("  Piano roll now visible, bounds: " << pianoRoll->getBounds().toString());
        }
    }
    if (recentFiles)
    {
        recentFiles->setVisible(index == 1);
    }
    
    updateTabButtons();
    repaint();
}

void VisualizationPanel::setBPM(int bpm)
{
    if (pianoRoll)
        pianoRoll->setBPM(bpm);
}

void VisualizationPanel::updateTabButtons()
{
    // Highlight active tab with distinct colors
    juce::Colour activeColour = AppColours::primary;
    juce::Colour inactiveColour = AppColours::surfaceAlt.darker(0.1f);
    juce::Colour activeTextColour = juce::Colours::white;
    juce::Colour inactiveTextColour = AppColours::textSecondary;
    
    pianoRollTab.setColour(juce::TextButton::buttonColourId, 
                           currentTab == 0 ? activeColour : inactiveColour);
    pianoRollTab.setColour(juce::TextButton::textColourOnId, 
                           currentTab == 0 ? activeTextColour : inactiveTextColour);
    pianoRollTab.setColour(juce::TextButton::textColourOffId, 
                           currentTab == 0 ? activeTextColour : inactiveTextColour);
    
    recentFilesTab.setColour(juce::TextButton::buttonColourId, 
                              currentTab == 1 ? activeColour : inactiveColour);
    recentFilesTab.setColour(juce::TextButton::textColourOnId, 
                              currentTab == 1 ? activeTextColour : inactiveTextColour);
    recentFilesTab.setColour(juce::TextButton::textColourOffId, 
                              currentTab == 1 ? activeTextColour : inactiveTextColour);
    
    // Force button repaint
    pianoRollTab.repaint();
    recentFilesTab.repaint();
    
    // Clear note info when not on piano roll
    if (currentTab != 0)
        noteInfoLabel.setText("", juce::dontSendNotification);
    
    DBG("Tab buttons updated, currentTab=" << currentTab);
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
