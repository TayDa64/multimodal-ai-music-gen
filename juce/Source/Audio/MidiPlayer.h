/*
  ==============================================================================
    MidiPlayer.h
    
    Handles MIDI file loading and playback through a Synthesiser.
    
    Task 0.4: JUCE MIDI Playback Research
  ==============================================================================
*/

#pragma once

#include <juce_audio_basics/juce_audio_basics.h>
#include <juce_audio_formats/juce_audio_formats.h>
#include "SimpleSynthVoice.h"

namespace mmg
{

//==============================================================================
/**
    Listener interface for receiving MIDI events from MidiPlayer.
    This allows external systems (like AudioEngine's Tracks) to respond
    to MIDI events during playback.
*/
class MidiPlayerListener
{
public:
    virtual ~MidiPlayerListener() = default;
    
    /** Called when a note-on event should trigger.
        @param channel  MIDI channel (1-16), typically maps to track index
        @param note     MIDI note number (0-127)
        @param velocity Note velocity (0.0-1.0) */
    virtual void midiNoteOn(int channel, int note, float velocity) = 0;
    
    /** Called when a note-off event should trigger.
        @param channel  MIDI channel (1-16)
        @param note     MIDI note number (0-127) */
    virtual void midiNoteOff(int channel, int note) = 0;
};

//==============================================================================
/**
    MidiPlayer loads and plays MIDI files through a Synthesiser.
    
    Responsibilities:
    - Load MIDI files from disk
    - Schedule MIDI events for playback
    - Manage synthesizer voices
    - Track playback position
    - Notify listeners of MIDI events for external instrument playback
    
    Usage:
        MidiPlayer player;
        player.prepareToPlay(sampleRate, bufferSize);
        player.loadMidiFile(midiFile);
        player.setMidiListener(&audioEngine); // Route events to tracks
        player.setPlaying(true);
        // In audio callback:
        player.renderNextBlock(buffer, numSamples);
*/
class MidiPlayer
{
public:
    //==========================================================================
    MidiPlayer();
    ~MidiPlayer() = default;
    
    //==========================================================================
    // Preparation
    //==========================================================================
    
    /** Prepare for playback. Must be called before rendering. */
    void prepareToPlay(double sampleRate, int samplesPerBlock);
    
    /** Release resources when done */
    void releaseResources();
    
    //==========================================================================
    // MIDI File Loading
    //==========================================================================
    
    /** Load a MIDI file for playback.
        @returns true if loaded successfully */
    bool loadMidiFile(const juce::File& file);

    /** Set MIDI data directly from memory */
    void setMidiData(const juce::MidiFile& midi);
    
    /** Clear the currently loaded MIDI data */
    void clearMidiFile();
    
    /** Check if a MIDI file is loaded */
    bool hasMidiLoaded() const { return midiLoaded; }
    
    /** Get the file that was loaded */
    juce::File getLoadedFile() const { return loadedFile; }
    
    //==========================================================================
    // Playback Control
    //==========================================================================
    
    /** Start/stop playback */
    void setPlaying(bool shouldPlay);
    
    /** Check if currently playing */
    bool isPlaying() const { return playing; }
    
    /** Set playback position in seconds */
    void setPosition(double positionInSeconds);
    
    /** Get current playback position in seconds */
    double getPosition() const { return currentPositionSeconds; }
    
    /** Get total duration of loaded MIDI in seconds */
    double getTotalDuration() const { return totalDurationSeconds; }
    
    /** Set tempo multiplier (1.0 = normal speed) */
    void setTempoMultiplier(double multiplier) { tempoMultiplier = multiplier; }
    
    //==========================================================================
    // Audio Rendering
    //==========================================================================
    
    /** Render audio for the next block.
        Call this from your audio callback. */
    void renderNextBlock(juce::AudioBuffer<float>& buffer, int numSamples);
    
    //==========================================================================
    // Properties
    //==========================================================================
    
    /** Get the number of tracks in loaded MIDI */
    int getNumTracks() const { return midiFile.getNumTracks(); }
    
    /** Get number of MIDI events in the combined sequence */
    int getNumEvents() const { return combinedSequence.getNumEvents(); }
    
    /** Get time signature (if available) */
    int getTimeSignatureNumerator() const { return timeSignatureNumerator; }
    int getTimeSignatureDenominator() const { return timeSignatureDenominator; }
    
    /** Get BPM (detected or from MIDI) */
    double getBPM() const { return bpm; }
    
    /** Get last max sample level (for debug display) */
    float getLastMaxSample() const { return lastMaxSample.load(); }
    
    /** Get events processed in last block */
    int getLastEventsInBlock() const { return lastEventsInBlock.load(); }
    
    //==========================================================================
    // Listener for external instrument routing
    //==========================================================================
    
    /** Set the MIDI listener for routing events to external instruments.
        This allows Track SamplerInstruments to receive MIDI notes.
        @param listener  The listener to notify of MIDI events (or nullptr to disable) */
    void setMidiListener(MidiPlayerListener* listener) { midiListener = listener; }
    
    /** Check if external instrument routing is enabled */
    bool hasExternalInstruments() const { return midiListener != nullptr; }

private:
    //==========================================================================
    // Internal Methods
    //==========================================================================
    
    void processNextMidiEvents(int numSamples);
    void setupSynthesiser();
    void extractMetadata();
    
    //==========================================================================
    // Members
    //==========================================================================
    
    // Synthesiser for audio generation
    juce::Synthesiser synth;
    
    // MIDI data
    juce::MidiFile midiFile;
    juce::MidiMessageSequence combinedSequence; // All tracks merged
    juce::File loadedFile;
    bool midiLoaded { false };
    
    // Playback state
    std::atomic<bool> playing { false };
    double currentPositionSeconds { 0.0 };
    int currentEventIndex { 0 };
    double totalDurationSeconds { 0.0 };
    
    // Audio settings
    double sampleRate { 44100.0 };
    int samplesPerBlock { 512 };
    double tempoMultiplier { 1.0 };
    
    // Metadata
    double bpm { 120.0 };
    int timeSignatureNumerator { 4 };
    int timeSignatureDenominator { 4 };
    
    // Debug tracking
    std::atomic<float> lastMaxSample { 0.0f };
    std::atomic<int> lastEventsInBlock { 0 };
    
    // Voice count
    static constexpr int numVoices { 16 };
    
    // External instrument listener (for routing to Track SamplerInstruments)
    MidiPlayerListener* midiListener { nullptr };
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(MidiPlayer)
};

} // namespace mmg
