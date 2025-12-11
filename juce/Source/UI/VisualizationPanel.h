/*
  ==============================================================================

    VisualizationPanel.h
    
    Tabbed panel containing Piano Roll and Recent Files views.
    Phase 6: Piano Roll Visualization

  ==============================================================================
*/

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include "Visualization/PianoRollComponent.h"
#include "RecentFilesPanel.h"
#include "../Application/AppState.h"
#include "../Audio/AudioEngine.h"

//==============================================================================
/**
    Tabbed container for visualization components.
    
    Tabs:
    - Piano Roll: MIDI note visualization
    - Recent Files: List of generated files
*/
class VisualizationPanel : public juce::Component,
                           public RecentFilesPanel::Listener,
                           public PianoRollComponent::Listener
{
public:
    //==============================================================================
    VisualizationPanel(AppState& state, mmg::AudioEngine& engine);
    ~VisualizationPanel() override;

    //==============================================================================
    void paint(juce::Graphics& g) override;
    void resized() override;
    
    //==============================================================================
    /** Load MIDI file into piano roll */
    void loadMidiFile(const juce::File& midiFile);
    
    /** Set output directory for recent files panel */
    void setOutputDirectory(const juce::File& directory);
    
    /** Refresh recent files list */
    void refreshRecentFiles();
    
    /** Switch to a specific tab */
    void showTab(int index);
    
    /** Set BPM for piano roll grid */
    void setBPM(int bpm);
    
    //==============================================================================
    // Forward listener interface
    class Listener
    {
    public:
        virtual ~Listener() = default;
        virtual void fileSelected(const juce::File& file) = 0;
    };
    
    void addListener(Listener* listener);
    void removeListener(Listener* listener);

private:
    //==============================================================================
    // RecentFilesPanel::Listener
    void fileSelected(const juce::File& file) override;
    
    // PianoRollComponent::Listener
    void pianoRollNoteHovered(const MidiNoteEvent* note) override;
    void pianoRollSeekRequested(double positionSeconds) override;
    
    //==============================================================================
    AppState& appState;
    mmg::AudioEngine& audioEngine;
    juce::ListenerList<Listener> listeners;
    
    // Tab buttons
    juce::TextButton pianoRollTab { "Piano Roll" };
    juce::TextButton recentFilesTab { "Recent Files" };
    
    // Content panels
    std::unique_ptr<PianoRollComponent> pianoRoll;
    std::unique_ptr<RecentFilesPanel> recentFiles;
    
    // Track info label (shows hovered note info)
    juce::Label noteInfoLabel;
    
    // Current tab
    int currentTab = 1;  // Start with Recent Files
    
    // Tab management
    void updateTabButtons();
    
    static constexpr int tabHeight = 28;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(VisualizationPanel)
};
