/*
  ==============================================================================

    SFZInstrument.h
    
    SFZ-based sampler instrument using the parsed SFZ data.

  ==============================================================================
*/

#pragma once

#include <juce_audio_basics/juce_audio_basics.h>
#include <juce_audio_formats/juce_audio_formats.h>
#include "SFZParser.h"
#include <map>
#include <memory>
#include <vector>

namespace mmg
{

//==============================================================================
/**
    A voice for playing back one SFZ region.
*/
class SFZVoice
{
public:
    SFZVoice() = default;
    ~SFZVoice() = default;
    
    void startNote(int midiNote, float velocity, const SFZRegion* region,
                   juce::AudioBuffer<float>* sampleBuffer, double sampleRate);
    void stopNote(bool allowTailOff);
    void renderNextBlock(juce::AudioBuffer<float>& outputBuffer, int startSample, int numSamples);
    
    bool isActive() const { return active; }
    bool isPlayingNote(int note) const { return active && currentNote == note; }
    int getCurrentNote() const { return currentNote; }
    int getGroup() const { return region ? region->group : 0; }
    
private:
    bool active = false;
    int currentNote = -1;
    float currentVelocity = 0.0f;
    
    const SFZRegion* region = nullptr;
    juce::AudioBuffer<float>* sampleData = nullptr;
    double sourceSampleRate = 44100.0;
    double targetSampleRate = 44100.0;
    
    // Playback position (in source samples)
    double samplePosition = 0.0;
    double pitchRatio = 1.0;
    
    // Envelope
    enum class EnvelopeState { Attack, Decay, Sustain, Release, Off };
    EnvelopeState envState = EnvelopeState::Off;
    float envLevel = 0.0f;
    float attackRate = 0.0f;
    float decayRate = 0.0f;
    float sustainLevel = 1.0f;
    float releaseRate = 0.0f;
    
    // Volume/pan
    float gainL = 1.0f;
    float gainR = 1.0f;
    
    void calculatePitchRatio();
    void calculateEnvelopeRates();
    float processEnvelope();
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(SFZVoice)
};

//==============================================================================
/**
    SFZ-based sampler instrument.
*/
class SFZInstrument
{
public:
    SFZInstrument();
    ~SFZInstrument();
    
    /** Load an SFZ file.
        @param sfzFile Path to the .sfz file
        @returns true if loading succeeded */
    bool loadFromFile(const juce::File& sfzFile);
    
    /** Check if instrument is loaded and ready. */
    bool isLoaded() const { return loaded; }
    
    /** Get the SFZ file path. */
    juce::File getSFZFile() const { return instrumentData.sfzFile; }
    
    /** Get number of loaded regions. */
    int getNumRegions() const;
    
    /** Set the sample rate. */
    void setSampleRate(double sampleRate);
    
    /** Trigger a note on. */
    void noteOn(int midiNote, float velocity);
    
    /** Trigger a note off. */
    void noteOff(int midiNote, bool allowTailOff = true);
    
    /** Stop all notes. */
    void allNotesOff();
    
    /** Render audio.
        @param buffer Output buffer to fill
        @param startSample Start position in buffer
        @param numSamples Number of samples to render */
    void renderNextBlock(juce::AudioBuffer<float>& buffer, int startSample, int numSamples);
    
    /** Set master volume (0.0 to 1.0). */
    void setVolume(float vol) { masterVolume = juce::jlimit(0.0f, 2.0f, vol); }
    float getVolume() const { return masterVolume; }
    
    /** Get last error message. */
    juce::String getLastError() const { return lastError; }

private:
    bool loaded = false;
    juce::String lastError;
    
    SFZInstrumentData instrumentData;
    juce::AudioFormatManager formatManager;
    
    // Sample buffers - keyed by sample file path
    std::map<juce::String, std::unique_ptr<juce::AudioBuffer<float>>> sampleBuffers;
    std::map<juce::String, double> sampleRates;
    
    // Voices
    static constexpr int MaxVoices = 64;
    std::vector<std::unique_ptr<SFZVoice>> voices;
    
    double currentSampleRate = 44100.0;
    float masterVolume = 1.0f;
    
    bool loadSamples();
    SFZVoice* findFreeVoice();
    SFZVoice* findVoicePlayingNote(int note);
    void handleGroupOff(int group);
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(SFZInstrument)
};

} // namespace mmg
