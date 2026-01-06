/*
  ==============================================================================

    PianoRollComponent.h
    
    Visual MIDI display with note rendering, piano keys, and playhead.
    Phase 6: Piano Roll Visualization

  ==============================================================================
*/

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include <juce_audio_basics/juce_audio_basics.h>
#include "../../Audio/AudioEngine.h"
#include "../../Project/ProjectState.h"

//==============================================================================
/**
    Represents a single MIDI note for visualization.
*/
struct MidiNoteEvent
{
    int noteNumber = 60;        // MIDI note (0-127)
    int velocity = 100;         // Note velocity (0-127)
    double startTime = 0.0;     // Start time in seconds
    double endTime = 0.0;       // End time in seconds
    int channel = 0;            // MIDI channel (0-15)
    int trackIndex = 0;         // Track index for coloring
    
    // Link to source state
    juce::ValueTree stateNode;
    
    double getDuration() const { return endTime - startTime; }
    
    // Note name helpers
    static juce::String getNoteName(int noteNum)
    {
        static const char* noteNames[] = { "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B" };
        int octave = (noteNum / 12) - 1;
        int note = noteNum % 12;
        return juce::String(noteNames[note]) + juce::String(octave);
    }
};

//==============================================================================
/**
    Piano roll visualization component showing MIDI notes on a grid.
    
    Features:
    - Piano keyboard on left side
    - Grid with beat/bar lines
    - Notes colored by velocity/track
    - Playhead following playback
    - Zoom and scroll
    - Note inspection on hover
    - Advanced Editing (Phase 5)
*/
class PianoRollComponent : public juce::Component,
                           private mmg::AudioEngine::Listener,
                           private juce::Timer,
                           public Project::ProjectState::Listener
{
public:
    //==============================================================================
    PianoRollComponent(mmg::AudioEngine& engine);
    ~PianoRollComponent() override;

    //==============================================================================
    /** Bind to project state for editing */
    void setProjectState(Project::ProjectState* state);

    /** Load MIDI data from a file (Legacy / Visualization only) */
    void loadMidiFile(const juce::File& midiFile);
    
    /** Load MIDI data from MidiFile object */
    void setMidiData(const juce::MidiFile& midiFile);
    
    /** Clear all notes */
    void clearNotes();
    
    /** Set BPM for grid calculation */
    void setBPM(int bpm);
    
    //==============================================================================
    // Loop Region
    void setLoopRegion(double startSeconds, double endSeconds);
    void clearLoopRegion();
    bool hasLoopRegion() const { return loopRegionStart >= 0 && loopRegionEnd > loopRegionStart; }
    
    //==============================================================================
    // Note Release Visualization
    /** Enable/disable note release tail visualization (ADSR decay) */
    void setShowReleaseTails(bool show) { showReleaseTails = show; repaint(); }
    bool isShowingReleaseTails() const { return showReleaseTails; }
    
    //==============================================================================
    // Zoom controls
    void setHorizontalZoom(float zoom);  // 0.1 to 10.0
    void setMinimumDuration(double seconds);  // Set minimum playable area duration
    void setVerticalZoom(float zoom);    // 0.5 to 4.0
    float getHorizontalZoom() const { return hZoom; }
    float getVerticalZoom() const { return vZoom; }
    void zoomToFit();
    
    // Scroll controls (for sync with ArrangementView)
    void setScrollX(double scrollSeconds);
    double getScrollX() const { return scrollX; }
    
    //==============================================================================
    // Track filtering
    void setTrackVisible(int trackIndex, bool visible);
    bool isTrackVisible(int trackIndex) const;
    void soloTrack(int trackIndex);  // -1 to show all
    int getTrackCount() const { return trackColors.size(); }
    void setTrackCount(int count);  // Set track count from arrangement view
    juce::Colour getTrackColour(int trackIndex) const;
    
    //==============================================================================
    // Embedded mode (for use inside ArrangementView - hides track selector)
    void setEmbeddedMode(bool embedded);
    bool isEmbeddedMode() const { return embeddedMode; }
    
    //==============================================================================
    // Component overrides
    void paint(juce::Graphics& g) override;
    void resized() override;
    void mouseDown(const juce::MouseEvent& event) override;
    void mouseUp(const juce::MouseEvent& event) override;
    void mouseDrag(const juce::MouseEvent& event) override;
    void mouseMove(const juce::MouseEvent& event) override;
    void mouseWheelMove(const juce::MouseEvent& event, const juce::MouseWheelDetails& wheel) override;
    void mouseExit(const juce::MouseEvent& event) override;
    void mouseDoubleClick(const juce::MouseEvent& event) override;
    bool keyPressed(const juce::KeyPress& key) override;

    //==============================================================================
    /** Listener for piano roll events */
    class Listener
    {
    public:
        virtual ~Listener() = default;
        virtual void pianoRollNoteHovered(const MidiNoteEvent* note) {}
        virtual void pianoRollSeekRequested(double positionSeconds) {}
        virtual void pianoRollHorizontalZoomRequested(float newZoom) {}  // For embedded mode sync
    };
    
    void addListener(Listener* listener);
    void removeListener(Listener* listener);

    //==============================================================================
    // ProjectState::Listener overrides
    void valueTreePropertyChanged(juce::ValueTree& treeWhosePropertyHasChanged, const juce::Identifier& property) override;
    void valueTreeChildAdded(juce::ValueTree& parentTree, juce::ValueTree& childWhichHasBeenAdded) override;
    void valueTreeChildRemoved(juce::ValueTree& parentTree, juce::ValueTree& childWhichHasBeenRemoved, int indexFromWhichChildWasRemoved) override;
    void valueTreeChildOrderChanged(juce::ValueTree& parentTreeWhichHasChanged, int oldIndex, int newIndex) override;
    void valueTreeParentChanged(juce::ValueTree& treeWhoseParentHasChanged) override;

private:
    //==============================================================================
    // AudioEngine::Listener
    void transportStateChanged(mmg::AudioEngine::TransportState newState) override;
    void playbackPositionChanged(double positionSeconds) override;
    void audioDeviceChanged() override {}
    
    // Timer for position updates
    void timerCallback() override;
    
    //==============================================================================
    // Drawing methods
    void drawBackground(juce::Graphics& g);
    void drawTimeRuler(juce::Graphics& g);  // Bar:Beat timeline ruler
    void drawPianoKeys(juce::Graphics& g);
    void drawGridLines(juce::Graphics& g);
    void drawLoopRegion(juce::Graphics& g);
    void drawNotes(juce::Graphics& g);
    void drawPlayhead(juce::Graphics& g);
    void drawNoteTooltip(juce::Graphics& g);
    void drawSelectionRect(juce::Graphics& g);
    
    //==============================================================================
    // Time formatting helpers
    juce::String formatBarBeat(double timeSeconds) const;
    void timeToBarBeat(double timeSeconds, int& bar, int& beat, int& tick) const;
    
    //==============================================================================
    // Coordinate conversion
    float timeToX(double timeSeconds) const;
    double xToTime(float x) const;
    float noteToY(int noteNumber) const;
    int yToNote(float y) const;
    
    // Note hit testing
    MidiNoteEvent* getNoteAt(juce::Point<float> position);
    
    //==============================================================================
    mmg::AudioEngine& audioEngine;
    juce::ListenerList<Listener> listeners;
    Project::ProjectState* projectState = nullptr;
    
    // MIDI data
    juce::Array<MidiNoteEvent> notes;
    double totalDuration = 60.0;
    double minimumDuration = 600.0;  // 10 minutes minimum for professional workflow
    int currentBPM = 120;
    
    // View state
    float hZoom = 1.0f;          // Horizontal zoom (time)
    float vZoom = 1.0f;          // Vertical zoom (notes)
    double scrollX = 0.0;        // Horizontal scroll position (seconds)
    int scrollY = 60;            // Vertical scroll position (center note)
    double playheadPosition = 0.0;
    
    // Piano key dimensions
    static constexpr int pianoKeyWidth = 60;
    static constexpr int whiteKeyHeight = 12;
    static constexpr int blackKeyWidth = 35;
    static constexpr int timeRulerHeight = 24;  // Height of bar:beat time ruler
    
    // Get effective key width (0 in embedded mode to maximize note area)
    int getEffectiveKeyWidth() const { return embeddedMode ? 0 : pianoKeyWidth; }
    
    // Get effective ruler height (shows in all modes for bar:beat display)
    int getEffectiveRulerHeight() const { return embeddedMode ? 0 : timeRulerHeight; }
    
    // Note range
    static constexpr int minNote = 21;   // A0
    static constexpr int maxNote = 108;  // C8
    
    // Track colors and visibility
    juce::Array<juce::Colour> trackColors;
    juce::Array<bool> trackVisible;
    int soloedTrack = -1;  // -1 = none
    
    // Track Selection UI
    juce::ComboBox trackSelector;
    void updateTrackList();
    bool embeddedMode = false;  // When true, hides track selector (for ArrangementView)
    
    // Mouse interaction
    MidiNoteEvent* hoveredNote = nullptr;
    juce::Point<float> lastMousePos;
    bool isDragging = false;
    juce::int64 clickStartTime = 0;  // For distinguishing click vs drag
    
    // Editing State
    juce::Array<juce::ValueTree> selectedNotes;
    bool isResizing = false;
    bool isMoving = false;
    bool isSelecting = false;
    juce::Rectangle<int> selectionRect;
    juce::Point<float> dragStartPos;
    double dragStartNoteStart = 0.0;
    int dragStartNoteNum = 0;
    
    // Loop region
    double loopRegionStart = -1.0;
    double loopRegionEnd = -1.0;
    
    // Note visualization options
    bool showReleaseTails = true;  // Show note release/decay tails
    static constexpr double defaultReleaseTime = 0.1;  // 100ms default release
    
    // Auto-zoom control - only zoom on initial load, not on incremental changes
    bool hasInitialZoom = false;
    
    // Generate track colors
    void assignTrackColors(int numTracks);
    void syncNotesFromState();
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(PianoRollComponent)
};
