/*
  ==============================================================================

    SF2Instrument.h
    
    SoundFont2 instrument loading and playback using TinySoundFont.
    MIT licensed - https://github.com/schellingb/TinySoundFont

  ==============================================================================
*/

#pragma once

#include <juce_audio_basics/juce_audio_basics.h>
#include <juce_audio_formats/juce_audio_formats.h>
#include <vector>
#include <map>

// Forward declaration for TSF
struct tsf;

namespace mmg
{

//==============================================================================
/**
    Information about a preset within an SF2 file.
*/
struct SF2PresetInfo
{
    int index;
    int bank;
    int presetNumber;
    juce::String name;
};

//==============================================================================
/**
    SF2 Instrument - loads and plays SoundFont2 files.
    
    Thread Safety:
    - Load/unload should be called from message thread
    - noteOn/noteOff/render can be called from audio thread
*/
class SF2Instrument
{
public:
    SF2Instrument();
    ~SF2Instrument();
    
    //==========================================================================
    // Loading
    //==========================================================================
    
    /** Load an SF2 file.
        @param sf2File The SoundFont2 file to load
        @returns true if loaded successfully */
    bool load(const juce::File& sf2File);
    
    /** Load an SF2 from memory.
        @param data Pointer to SF2 data
        @param size Size in bytes
        @returns true if loaded successfully */
    bool loadFromMemory(const void* data, int size);
    
    /** Unload the current soundfont. */
    void unload();
    
    /** Check if a soundfont is loaded. */
    bool isLoaded() const { return soundFont != nullptr; }
    
    /** Get the loaded file path. */
    juce::String getFilePath() const { return filePath; }
    
    //==========================================================================
    // Preset Information
    //==========================================================================
    
    /** Get the number of presets in the loaded soundfont. */
    int getNumPresets() const;
    
    /** Get preset info by index. */
    SF2PresetInfo getPresetInfo(int index) const;
    
    /** Get all presets. */
    std::vector<SF2PresetInfo> getAllPresets() const;
    
    /** Find preset by bank and program number. */
    int findPreset(int bank, int presetNumber) const;
    
    /** Set the active preset for playback. */
    void setActivePreset(int presetIndex);
    int getActivePreset() const { return activePreset; }
    
    //==========================================================================
    // Playback
    //==========================================================================
    
    /** Prepare for playback. */
    void prepareToPlay(double sampleRate, int samplesPerBlock);
    
    /** Set sample rate. */
    void setSampleRate(double sampleRate);
    
    /** Release resources. */
    void releaseResources();
    
    /** Trigger a note on.
        @param channel MIDI channel (0-15, or -1 for active preset)
        @param midiNoteNumber MIDI note (0-127)
        @param velocity Velocity (0.0 to 1.0) */
    void noteOn(int channel, int midiNoteNumber, float velocity);
    
    /** Simplified note on using active preset. */
    void noteOn(int midiNoteNumber, float velocity);
    
    /** Trigger a note off. */
    void noteOff(int channel, int midiNoteNumber);
    
    /** Simplified note off using active preset. */
    void noteOff(int midiNoteNumber);
    
    /** Stop all notes. */
    void allNotesOff();
    
    /** Render audio to buffer.
        @param buffer Output buffer (stereo)
        @param startSample Start sample in buffer
        @param numSamples Number of samples to render */
    void renderNextBlock(juce::AudioBuffer<float>& buffer, int startSample, int numSamples);
    
    //==========================================================================
    // Settings
    //==========================================================================
    
    /** Set output gain (linear, default 1.0). */
    void setGain(float newGain) { gain = newGain; }
    float getGain() const { return gain; }
    
    /** Set global volume in dB. */
    void setGlobalVolumeDb(float db);
    
    /** Enable/disable chorus effect. */
    void setChorusEnabled(bool enabled);
    
    /** Enable/disable reverb effect. */
    void setReverbEnabled(bool enabled);

private:
    tsf* soundFont = nullptr;
    juce::String filePath;
    
    double currentSampleRate = 44100.0;
    int currentBufferSize = 512;
    int activePreset = 0;
    float gain = 1.0f;
    
    // Render buffer for interleaved audio
    std::vector<float> renderBuffer;
    
    juce::CriticalSection lock;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(SF2Instrument)
};

} // namespace mmg
