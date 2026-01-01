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
    MidiPlayer loads and plays MIDI files through a Synthesiser.
    
    Responsibilities:
    - Load MIDI files from disk
    - Schedule MIDI events for playback
    - Manage synthesizer voices
    - Track playback position
    
    Usage:
        MidiPlayer player;
        player.prepareToPlay(sampleRate, bufferSize);
        player.loadMidiFile(midiFile);
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
    
    /** Get time signature (if available) */
    int getTimeSignatureNumerator() const { return timeSignatureNumerator; }
    int getTimeSignatureDenominator() const { return timeSignatureDenominator; }
    
    /** Get BPM (detected or from MIDI) */
    double getBPM() const { return bpm; }

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
    
    // Voice count
    static constexpr int numVoices { 16 };
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(MidiPlayer)
};

} // namespace mmg
