/*
  ==============================================================================

    SamplerInstrument.h
    
    Multi-sample instrument using juce::Synthesiser.
    Supports key zones with automatic pitch interpolation between samples.

  ==============================================================================
*/

#pragma once

#include <juce_audio_basics/juce_audio_basics.h>
#include <juce_audio_formats/juce_audio_formats.h>
#include "ExpansionInstrumentLoader.h"

namespace mmg
{

//==============================================================================
/**
    Custom SamplerSound that stores zone information.
*/
class ZonedSamplerSound : public juce::SynthesiserSound
{
public:
    ZonedSamplerSound(const juce::String& name,
                      juce::AudioFormatReader& source,
                      const juce::BigInteger& midiNotes,
                      int midiNoteForNormalPitch,
                      double attackTimeSecs,
                      double releaseTimeSecs,
                      double maxSampleLengthSecs);
    
    ~ZonedSamplerSound() override;
    
    const juce::String& getName() const noexcept { return name; }
    juce::AudioBuffer<float>* getAudioData() const noexcept { return data.get(); }
    
    int getMidiNoteForNormalPitch() const noexcept { return midiRootNote; }
    
    void setEnvelopeParameters(const juce::ADSR::Parameters& params);
    const juce::ADSR::Parameters& getEnvelopeParameters() const noexcept { return adsrParams; }
    
    bool appliesToNote(int midiNoteNumber) override;
    bool appliesToChannel(int midiChannel) override;

private:
    friend class ZonedSamplerVoice;
    
    juce::String name;
    std::unique_ptr<juce::AudioBuffer<float>> data;
    double sourceSampleRate;
    juce::BigInteger midiNotes;
    int length = 0, midiRootNote = 0;
    juce::ADSR::Parameters adsrParams;
    
    JUCE_LEAK_DETECTOR(ZonedSamplerSound)
};

//==============================================================================
/**
    Custom SamplerVoice with ADSR envelope and pitch interpolation.
*/
class ZonedSamplerVoice : public juce::SynthesiserVoice
{
public:
    ZonedSamplerVoice();
    ~ZonedSamplerVoice() override;
    
    bool canPlaySound(juce::SynthesiserSound* sound) override;
    
    void startNote(int midiNoteNumber, float velocity,
                   juce::SynthesiserSound* sound,
                   int currentPitchWheelPosition) override;
    
    void stopNote(float velocity, bool allowTailOff) override;
    
    void pitchWheelMoved(int newPitchWheelValue) override;
    void controllerMoved(int controllerNumber, int newControllerValue) override;
    
    void renderNextBlock(juce::AudioBuffer<float>& outputBuffer,
                         int startSample, int numSamples) override;
    
    using SynthesiserVoice::renderNextBlock;

private:
    double pitchRatio = 0.0;
    double sourceSamplePosition = 0.0;
    float lgain = 0.0f, rgain = 0.0f;
    juce::ADSR adsr;
    
    JUCE_LEAK_DETECTOR(ZonedSamplerVoice)
};

//==============================================================================
/**
    Complete sampler instrument that loads from an InstrumentDefinition.
    Manages a juce::Synthesiser with multiple ZonedSamplerSounds.
*/
class SamplerInstrument
{
public:
    SamplerInstrument();
    ~SamplerInstrument();
    
    //==========================================================================
    // Loading
    //==========================================================================
    
    /** Load an instrument from definition.
        @param definition The instrument definition with zone mappings
        @param formatManager Audio format manager for reading samples
        @returns true if loaded successfully */
    bool loadFromDefinition(const InstrumentDefinition& definition,
                            juce::AudioFormatManager& formatManager);
    
    /** Clear all loaded samples. */
    void clear();
    
    /** Check if an instrument is loaded. */
    bool isLoaded() const { return loaded; }
    
    /** Get the loaded instrument ID. */
    juce::String getInstrumentId() const { return instrumentId; }
    
    /** Get the loaded instrument name. */
    juce::String getInstrumentName() const { return instrumentName; }
    
    //==========================================================================
    // Playback
    //==========================================================================
    
    /** Prepare for playback. */
    void prepareToPlay(double sampleRate, int samplesPerBlock);
    
    /** Release resources. */
    void releaseResources();
    
    /** Render audio to buffer. */
    void renderNextBlock(juce::AudioBuffer<float>& buffer,
                         juce::MidiBuffer& midiMessages,
                         int startSample, int numSamples);
    
    /** Trigger a note on. */
    void noteOn(int channel, int midiNoteNumber, float velocity);
    
    /** Trigger a note off. */
    void noteOff(int channel, int midiNoteNumber, float velocity, bool allowTailOff = true);
    
    /** Stop all notes. */
    void allNotesOff(int channel, bool allowTailOff);
    
    //==========================================================================
    // Settings
    //==========================================================================
    
    /** Set volume (0.0 to 1.0). */
    void setVolume(float newVolume) { volume = newVolume; }
    float getVolume() const { return volume; }
    
    /** Set pan (0.0 = left, 0.5 = center, 1.0 = right). */
    void setPan(float newPan) { pan = newPan; }
    float getPan() const { return pan; }
    
    /** Set polyphony (number of voices). */
    void setPolyphony(int numVoices);
    int getPolyphony() const { return polyphony; }

private:
    juce::Synthesiser synth;
    bool loaded = false;
    juce::String instrumentId;
    juce::String instrumentName;
    
    float volume = 1.0f;
    float pan = 0.5f;
    int polyphony = 8;
    
    juce::ADSR::Parameters adsrParams;
    
    void setupVoices(int numVoices);
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(SamplerInstrument)
};

} // namespace mmg
