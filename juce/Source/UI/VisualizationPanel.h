/*
  ==============================================================================

    VisualizationPanel.h
    
    Tabbed panel containing Piano Roll, Waveform, Spectrum, and Recent Files views.
    Phase 6: Piano Roll Visualization
    Phase 7: Waveform & Spectrum Visualization

  ==============================================================================
*/

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include "Visualization/PianoRollComponent.h"
#include "Visualization/WaveformComponent.h"
#include "Visualization/SpectrumComponent.h"
#include "Visualization/GenreTheme.h"
#include "TrackList/ArrangementView.h"
#include "RecentFilesPanel.h"
#include "../Application/AppState.h"
#include "../Audio/AudioEngine.h"

//==============================================================================
/**
    Tabbed container for visualization components.
    
    Tabs:
    - Piano Roll: MIDI note visualization
    - Waveform: Real-time audio waveform
    - Spectrum: FFT frequency analyzer
    - Recent Files: List of generated files
*/
class VisualizationPanel : public juce::Component,
                           public RecentFilesPanel::Listener,
                           public PianoRollComponent::Listener,
                           public UI::ArrangementView::Listener,
                           private mmg::AudioEngine::VisualizationListener
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
    
    /** Switch to a specific tab (0=Piano Roll, 1=Waveform, 2=Spectrum, 3=Files) */
    void showTab(int index);
    
    /** Set BPM for piano roll grid */
    void setBPM(int bpm);
    
    /** Set genre for themed visualizations */
    void setGenre(const juce::String& genre);
    
    /** Set/clear loop region on piano roll */
    void setLoopRegion(double startSeconds, double endSeconds);
    void clearLoopRegion();
    
    //==============================================================================
    // Forward listener interface
    class Listener
    {
    public:
        virtual ~Listener() = default;
        virtual void fileSelected(const juce::File& file) = 0;
        virtual void analyzeFileRequested(const juce::File& file) { juce::ignoreUnused(file); }
        virtual void regenerateRequested(int startBar, int endBar, const juce::StringArray& tracks) { juce::ignoreUnused(startBar, endBar, tracks); }
    };
    
    void addListener(Listener* listener);
    void removeListener(Listener* listener);

private:
    //==============================================================================
    // RecentFilesPanel::Listener
    void fileSelected(const juce::File& file) override;
    void analyzeFileRequested(const juce::File& file) override;
    
    // PianoRollComponent::Listener
    void pianoRollNoteHovered(const MidiNoteEvent* note) override;
    void pianoRollSeekRequested(double positionSeconds) override;
    
    // ArrangementView::Listener
    void arrangementTrackPianoRollRequested(int trackIndex) override;
    void arrangementRegenerateRequested(int startBar, int endBar, const juce::StringArray& tracks) override;
    
    // AudioEngine::VisualizationListener (called from audio thread)
    void audioSamplesReady(const float* leftSamples, 
                           const float* rightSamples, 
                           int numSamples) override;
    
    //==============================================================================
    AppState& appState;
    mmg::AudioEngine& audioEngine;
    juce::ListenerList<Listener> listeners;
    
    // Theme manager for smooth transitions
    GenreThemeManager themeManager;
    
    // Tab buttons
    juce::TextButton arrangeTab { "Arrange" };
    juce::TextButton pianoRollTab { "Piano Roll" };
    juce::TextButton waveformTab { "Waveform" };
    juce::TextButton spectrumTab { "Spectrum" };
    juce::TextButton recentFilesTab { "Files" };
    
    // Content panels
    std::unique_ptr<UI::ArrangementView> arrangementView;
    std::unique_ptr<PianoRollComponent> pianoRoll;
    std::unique_ptr<WaveformComponent> waveform;
    std::unique_ptr<SpectrumComponent> spectrum;
    std::unique_ptr<RecentFilesPanel> recentFiles;
    
    // Track info label (shows hovered note info or visualization mode)
    juce::Label infoLabel;
    
    // Current tab
    int currentTab = 0;  // Start with Piano Roll
    
    // Tab management
    void updateTabButtons();
    void updateTheme();
    
    static constexpr int tabHeight = 28;
    static constexpr int numTabs = 5;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(VisualizationPanel)
};
