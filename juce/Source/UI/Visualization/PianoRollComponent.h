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
*/
class PianoRollComponent : public juce::Component,
                           private mmg::AudioEngine::Listener,
                           private juce::Timer
{
public:
    //==============================================================================
    PianoRollComponent(mmg::AudioEngine& engine);
    ~PianoRollComponent() override;

    //==============================================================================
    /** Load MIDI data from a file */
    void loadMidiFile(const juce::File& midiFile);
    
    /** Load MIDI data from MidiFile object */
    void setMidiData(const juce::MidiFile& midiFile);
    
    /** Clear all notes */
    void clearNotes();
    
    /** Set BPM for grid calculation */
    void setBPM(int bpm);
    
    //==============================================================================
    // Zoom controls
    void setHorizontalZoom(float zoom);  // 0.1 to 10.0
    void setVerticalZoom(float zoom);    // 0.5 to 4.0
    float getHorizontalZoom() const { return hZoom; }
    float getVerticalZoom() const { return vZoom; }
    void zoomToFit();
    
    //==============================================================================
    // Track filtering
    void setTrackVisible(int trackIndex, bool visible);
    bool isTrackVisible(int trackIndex) const;
    void soloTrack(int trackIndex);  // -1 to show all
    int getTrackCount() const { return trackColors.size(); }
    juce::Colour getTrackColour(int trackIndex) const;
    
    //==============================================================================
    // Component overrides
    void paint(juce::Graphics& g) override;
    void resized() override;
    void mouseDown(const juce::MouseEvent& event) override;
    void mouseDrag(const juce::MouseEvent& event) override;
    void mouseMove(const juce::MouseEvent& event) override;
    void mouseWheelMove(const juce::MouseEvent& event, const juce::MouseWheelDetails& wheel) override;
    void mouseExit(const juce::MouseEvent& event) override;

    //==============================================================================
    /** Listener for piano roll events */
    class Listener
    {
    public:
        virtual ~Listener() = default;
        virtual void pianoRollNoteHovered(const MidiNoteEvent* note) {}
        virtual void pianoRollSeekRequested(double positionSeconds) {}
    };
    
    void addListener(Listener* listener);
    void removeListener(Listener* listener);

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
    void drawPianoKeys(juce::Graphics& g);
    void drawGridLines(juce::Graphics& g);
    void drawNotes(juce::Graphics& g);
    void drawPlayhead(juce::Graphics& g);
    void drawNoteTooltip(juce::Graphics& g);
    
    //==============================================================================
    // Coordinate conversion
    float timeToX(double timeSeconds) const;
    double xToTime(float x) const;
    float noteToY(int noteNumber) const;
    int yToNote(float y) const;
    
    // Note hit testing
    const MidiNoteEvent* getNoteAt(juce::Point<float> position) const;
    
    //==============================================================================
    mmg::AudioEngine& audioEngine;
    juce::ListenerList<Listener> listeners;
    
    // MIDI data
    juce::Array<MidiNoteEvent> notes;
    double totalDuration = 60.0;
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
    
    // Note range
    static constexpr int minNote = 21;   // A0
    static constexpr int maxNote = 108;  // C8
    
    // Track colors and visibility
    juce::Array<juce::Colour> trackColors;
    juce::Array<bool> trackVisible;
    int soloedTrack = -1;  // -1 = none
    
    // Mouse interaction
    const MidiNoteEvent* hoveredNote = nullptr;
    juce::Point<float> lastMousePos;
    bool isDragging = false;
    
    // Generate track colors
    void assignTrackColors(int numTracks);
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(PianoRollComponent)
};
