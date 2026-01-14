/*
  ==============================================================================

    ArrangementView.h
    
    Professional DAW-style arrangement view combining:
    - Track list headers on the left
    - Timeline/ruler at top
    - Piano rolls for MIDI tracks
    - Waveform displays for audio tracks
    - Clip regions and automation lanes

  ==============================================================================
*/

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include "TrackHeaderComponent.h"
#include "../Visualization/PianoRollComponent.h"
#include "../TimelineComponent.h"
#include "../../Audio/AudioEngine.h"
#include "../../Audio/ExpansionInstrumentLoader.h"
#include "../../Project/ProjectState.h"

namespace UI
{

//==============================================================================
/**
    Track lane component - contains piano roll or waveform for a single track.
*/
class TrackLaneContent : public juce::Component,
                         public PianoRollComponent::Listener
{
public:
    TrackLaneContent(int trackIndex, mmg::AudioEngine& engine);
    ~TrackLaneContent() override;
    
    void setTrackIndex(int index);
    int getTrackIndex() const { return trackIndex; }
    
    void setTrackType(TrackType type);
    
    void setProjectState(Project::ProjectState* state);
    
    void setHorizontalZoom(float zoom);
    void setScrollX(double scrollX);
    
    // Callback for zoom requests from embedded PianoRoll
    std::function<void(float)> onZoomRequested;
    
    void paint(juce::Graphics& g) override;
    void resized() override;
    
    // PianoRollComponent::Listener
    void pianoRollHorizontalZoomRequested(float newZoom) override;
    
private:
    int trackIndex = 0;
    TrackType trackType = TrackType::MIDI;
    mmg::AudioEngine& audioEngine;
    Project::ProjectState* projectState = nullptr;
    
    // For MIDI tracks
    std::unique_ptr<PianoRollComponent> pianoRoll;
    
    // For Audio tracks (future)
    // std::unique_ptr<WaveformComponent> waveform;
    
    float hZoom = 1.0f;
    double scrollPosX = 0.0;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(TrackLaneContent)
};


//==============================================================================
/**
    Arrangement view - main DAW-style editor combining tracks and timeline.
*/
class ArrangementView : public juce::Component,
                        public TrackListComponent::Listener,
                        public juce::ValueTree::Listener,
                        public juce::ScrollBar::Listener
{
public:
    ArrangementView(mmg::AudioEngine& engine);
    ~ArrangementView() override;
    
    //==============================================================================
    /** Listener interface for arrangement events. */
    class Listener
    {
    public:
        virtual ~Listener() = default;
        virtual void arrangementTrackSelected(int trackIndex) { juce::ignoreUnused(trackIndex); }
        virtual void arrangementTrackPianoRollRequested(int trackIndex) = 0;  // User wants to edit track in Piano Roll
        virtual void arrangementRegenerateRequested(int startBar, int endBar, const juce::StringArray& tracks) {}  // User wants to regenerate selection
        virtual void arrangementTrackInstrumentSelected(int trackIndex, const juce::String& instrumentId) {}  // User selected an instrument for a track
        virtual void arrangementTrackLoadSF2Requested(int trackIndex) {}  // User wants to load SF2 file
        virtual void arrangementTrackLoadSFZRequested(int trackIndex) {}  // User wants to load SFZ file
    };
    
    void addListener(Listener* listener) { listeners.add(listener); }
    void removeListener(Listener* listener) { listeners.remove(listener); }
    
    //==============================================================================
    /** Bind to project state. */
    void setProjectState(Project::ProjectState* state);
    
    /** Set BPM for timeline display. */
    void setBPM(int bpm);
    
    /** Set horizontal zoom level. */
    void setHorizontalZoom(float zoom);
    float getHorizontalZoom() const { return hZoom; }
    
    /** Zoom to show the entire song duration. */
    void zoomToShowFullSong();
    
    /** Get track list component for external access. */
    TrackListComponent& getTrackList() { return trackList; }
    
    /** Set available instruments for all tracks. */
    void setAvailableInstruments(const std::map<juce::String, std::vector<const mmg::InstrumentDefinition*>>& byCategory)
    {
        trackList.setAvailableInstruments(byCategory);
    }

    /** Get selected track index. */
    int getSelectedTrackIndex() const { return trackList.getSelectedTrackIndex(); }
    
    //==============================================================================
    // Focused Track View
    /** Focus on a single track (full screen within arrangement). -1 to show all tracks. */
    void setFocusedTrack(int trackIndex);
    int getFocusedTrack() const { return focusedTrackIndex; }
    bool hasFocusedTrack() const { return focusedTrackIndex >= 0; }
    void clearFocusedTrack() { setFocusedTrack(-1); }
    
    //==============================================================================
    void paint(juce::Graphics& g) override;
    void paintOverChildren(juce::Graphics& g) override;  // Draw unified grid lines
    void resized() override;
    void mouseWheelMove(const juce::MouseEvent& event, const juce::MouseWheelDetails& wheel) override;
    void mouseDown(const juce::MouseEvent& event) override;
    
    // TrackListComponent::Listener
    void trackSelectionChanged(int trackIndex) override;
    void trackCountChanged(int newCount) override;
    void trackExpandedChanged(int trackIndex, bool expanded) override;
    void trackInstrumentSelected(int trackIndex, const juce::String& instrumentId) override;
    void trackLoadSF2Requested(int trackIndex) override;
    void trackLoadSFZRequested(int trackIndex) override;
    
    // ValueTree::Listener
    void valueTreePropertyChanged(juce::ValueTree& tree, const juce::Identifier& property) override;
    void valueTreeChildAdded(juce::ValueTree& parent, juce::ValueTree& child) override;
    void valueTreeChildRemoved(juce::ValueTree& parent, juce::ValueTree& child, int index) override;
    void valueTreeChildOrderChanged(juce::ValueTree&, int, int) override {}
    void valueTreeParentChanged(juce::ValueTree&) override {}
    
    // ScrollBar::Listener for synchronizing track list and lanes scroll
    void scrollBarMoved(juce::ScrollBar* scrollBar, double newRangeStart) override;

private:
    mmg::AudioEngine& audioEngine;
    Project::ProjectState* projectState = nullptr;
    juce::ListenerList<Listener> listeners;
    
    // Left panel - track headers
    TrackListComponent trackList;
    int trackListWidth = 200;
    
    // Top - timeline ruler
    // We'll draw a simple ruler here
    int rulerHeight = 30;
    
    // Main content - track lanes with piano rolls/waveforms
    juce::OwnedArray<TrackLaneContent> trackLanes;
    juce::Viewport lanesViewport;
    juce::Component lanesContent;
    
    // Scroll synchronization
    double scrollX = 0.0;
    float hZoom = 1.0f;
    int currentBPM = 120;
    
    // Focused track view (-1 = show all)
    int focusedTrackIndex = -1;
    
    // Scroll synchronization flag to prevent feedback loops
    bool isSyncingScroll = false;
    
    // Splitter for resizable track list
    juce::StretchableLayoutManager layoutManager;
    
    void syncTrackLanes();
    void updateLanesLayout();
    void syncScrollFromViewport();  // Sync scrollX from viewport position
    void drawTimelineRuler(juce::Graphics& g, juce::Rectangle<int> bounds);
    void showContextMenu(const juce::MouseEvent& event);
    
    // Time formatting helpers
    void timeToBarBeat(double timeSeconds, int& bar, int& beat, int& tick) const;
    juce::String formatBarBeat(double timeSeconds) const;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(ArrangementView)
};

} // namespace UI
