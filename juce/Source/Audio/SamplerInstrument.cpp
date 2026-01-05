/*
  ==============================================================================

    SamplerInstrument.cpp
    
    Implementation of multi-sample instrument with key zones.

  ==============================================================================
*/

#include "SamplerInstrument.h"

namespace mmg
{

//==============================================================================
// ZonedSamplerSound
//==============================================================================

ZonedSamplerSound::ZonedSamplerSound(const juce::String& soundName,
                                     juce::AudioFormatReader& source,
                                     const juce::BigInteger& notes,
                                     int midiNoteForNormalPitch,
                                     double attackTimeSecs,
                                     double releaseTimeSecs,
                                     double maxSampleLengthSecs)
    : name(soundName),
      sourceSampleRate(source.sampleRate),
      midiNotes(notes),
      midiRootNote(midiNoteForNormalPitch)
{
    // Calculate sample length
    int numSamples = (int)juce::jmin((juce::int64)source.lengthInSamples,
                                     (juce::int64)(maxSampleLengthSecs * source.sampleRate));
    
    length = numSamples;
    
    // Read audio data
    data = std::make_unique<juce::AudioBuffer<float>>(
        juce::jmin(2, (int)source.numChannels), numSamples + 4);
    
    source.read(data.get(), 0, numSamples + 4, 0, true, true);
    
    // Set ADSR parameters
    adsrParams.attack = (float)attackTimeSecs;
    adsrParams.decay = 0.0f;
    adsrParams.sustain = 1.0f;
    adsrParams.release = (float)releaseTimeSecs;
}

ZonedSamplerSound::~ZonedSamplerSound() {}

void ZonedSamplerSound::setEnvelopeParameters(const juce::ADSR::Parameters& params)
{
    adsrParams = params;
}

bool ZonedSamplerSound::appliesToNote(int midiNoteNumber)
{
    return midiNotes[midiNoteNumber];
}

bool ZonedSamplerSound::appliesToChannel(int /*midiChannel*/)
{
    return true;
}

//==============================================================================
// ZonedSamplerVoice
//==============================================================================

ZonedSamplerVoice::ZonedSamplerVoice() {}
ZonedSamplerVoice::~ZonedSamplerVoice() {}

bool ZonedSamplerVoice::canPlaySound(juce::SynthesiserSound* sound)
{
    return dynamic_cast<const ZonedSamplerSound*>(sound) != nullptr;
}

void ZonedSamplerVoice::startNote(int midiNoteNumber, float velocity,
                                  juce::SynthesiserSound* s,
                                  int /*currentPitchWheelPosition*/)
{
    if (auto* sound = dynamic_cast<const ZonedSamplerSound*>(s))
    {
        // Calculate pitch ratio based on distance from root note
        double rootFreq = juce::MidiMessage::getMidiNoteInHertz(sound->midiRootNote);
        double noteFreq = juce::MidiMessage::getMidiNoteInHertz(midiNoteNumber);
        
        pitchRatio = noteFreq / rootFreq * (sound->sourceSampleRate / getSampleRate());
        
        sourceSamplePosition = 0.0;
        
        // Velocity-sensitive gain with stereo spread
        lgain = velocity;
        rgain = velocity;
        
        // Setup and trigger envelope
        adsr.setParameters(sound->adsrParams);
        adsr.setSampleRate(getSampleRate());
        adsr.noteOn();
    }
    else
    {
        jassertfalse; // this shouldn't happen
    }
}

void ZonedSamplerVoice::stopNote(float /*velocity*/, bool allowTailOff)
{
    if (allowTailOff)
    {
        adsr.noteOff();
    }
    else
    {
        clearCurrentNote();
        adsr.reset();
    }
}

void ZonedSamplerVoice::pitchWheelMoved(int /*newPitchWheelValue*/) {}
void ZonedSamplerVoice::controllerMoved(int /*controllerNumber*/, int /*newControllerValue*/) {}

void ZonedSamplerVoice::renderNextBlock(juce::AudioBuffer<float>& outputBuffer,
                                         int startSample, int numSamples)
{
    if (auto* playingSound = dynamic_cast<ZonedSamplerSound*>(getCurrentlyPlayingSound().get()))
    {
        auto* data = playingSound->getAudioData();
        const float* const inL = data->getReadPointer(0);
        const float* const inR = data->getNumChannels() > 1 ? data->getReadPointer(1) : nullptr;
        
        float* outL = outputBuffer.getWritePointer(0, startSample);
        float* outR = outputBuffer.getNumChannels() > 1 ? outputBuffer.getWritePointer(1, startSample) : nullptr;
        
        while (--numSamples >= 0)
        {
            auto pos = (int)sourceSamplePosition;
            auto alpha = (float)(sourceSamplePosition - pos);
            auto invAlpha = 1.0f - alpha;
            
            // Simple linear interpolation
            float l = (inL[pos] * invAlpha + inL[pos + 1] * alpha);
            float r = (inR != nullptr) ? (inR[pos] * invAlpha + inR[pos + 1] * alpha) : l;
            
            // Apply envelope
            auto envelopeValue = adsr.getNextSample();
            
            l *= lgain * envelopeValue;
            r *= rgain * envelopeValue;
            
            if (outR != nullptr)
            {
                *outL++ += l;
                *outR++ += r;
            }
            else
            {
                *outL++ += (l + r) * 0.5f;
            }
            
            sourceSamplePosition += pitchRatio;
            
            // Check if we've reached the end of the sample
            if (sourceSamplePosition > playingSound->length)
            {
                stopNote(0.0f, false);
                break;
            }
        }
        
        // Check if envelope has finished
        if (!adsr.isActive())
            clearCurrentNote();
    }
}

//==============================================================================
// SamplerInstrument
//==============================================================================

SamplerInstrument::SamplerInstrument()
{
    // Default ADSR
    adsrParams.attack = 0.001f;
    adsrParams.decay = 0.0f;
    adsrParams.sustain = 1.0f;
    adsrParams.release = 0.1f;
    
    setupVoices(polyphony);
}

SamplerInstrument::~SamplerInstrument()
{
    clear();
}

bool SamplerInstrument::loadFromDefinition(const InstrumentDefinition& definition,
                                           juce::AudioFormatManager& formatManager)
{
    clear();
    
    instrumentId = definition.id;
    instrumentName = definition.name;
    
    // Update ADSR from definition
    adsrParams.attack = definition.attack;
    adsrParams.decay = definition.decay;
    adsrParams.sustain = definition.sustain;
    adsrParams.release = definition.release;
    
    // Set polyphony
    setPolyphony(definition.polyphony);
    
    int loadedZones = 0;
    
    // Load each sample zone
    for (const auto& zone : definition.zones)
    {
        if (!zone.sampleFile.existsAsFile())
        {
            DBG("SamplerInstrument: Sample not found: " << zone.sampleFile.getFullPathName());
            continue;
        }
        
        std::unique_ptr<juce::AudioFormatReader> reader(
            formatManager.createReaderFor(zone.sampleFile));
        
        if (!reader)
        {
            DBG("SamplerInstrument: Could not read: " << zone.sampleFile.getFileName());
            continue;
        }
        
        // Create note range for this zone
        juce::BigInteger midiNotes;
        midiNotes.setRange(zone.lowNote, zone.highNote - zone.lowNote + 1, true);
        
        // Create sound with zone parameters
        auto* sound = new ZonedSamplerSound(zone.sampleName,
                                            *reader,
                                            midiNotes,
                                            zone.rootNote,
                                            adsrParams.attack,
                                            adsrParams.release,
                                            10.0); // Max 10 second samples
        
        sound->setEnvelopeParameters(adsrParams);
        synth.addSound(sound);
        
        loadedZones++;
        DBG("  Loaded zone: " << zone.sampleName << " (notes " << zone.lowNote 
            << "-" << zone.highNote << ", root " << zone.rootNote << ")");
    }
    
    loaded = loadedZones > 0;
    
    if (loaded)
    {
        DBG("SamplerInstrument: Loaded " << instrumentName << " with " 
            << loadedZones << " zones");
    }
    
    return loaded;
}

void SamplerInstrument::clear()
{
    synth.clearSounds();
    loaded = false;
    instrumentId.clear();
    instrumentName.clear();
}

void SamplerInstrument::prepareToPlay(double sampleRate, int /*samplesPerBlock*/)
{
    synth.setCurrentPlaybackSampleRate(sampleRate);
}

void SamplerInstrument::releaseResources()
{
    // Nothing specific needed
}

void SamplerInstrument::renderNextBlock(juce::AudioBuffer<float>& buffer,
                                        juce::MidiBuffer& midiMessages,
                                        int startSample, int numSamples)
{
    synth.renderNextBlock(buffer, midiMessages, startSample, numSamples);
    
    // Apply volume
    if (volume != 1.0f)
    {
        buffer.applyGain(startSample, numSamples, volume);
    }
    
    // Apply pan if stereo
    if (buffer.getNumChannels() >= 2 && pan != 0.5f)
    {
        float leftGain = (pan <= 0.5f) ? 1.0f : 2.0f * (1.0f - pan);
        float rightGain = (pan >= 0.5f) ? 1.0f : 2.0f * pan;
        
        buffer.applyGain(0, startSample, numSamples, leftGain);
        buffer.applyGain(1, startSample, numSamples, rightGain);
    }
}

void SamplerInstrument::noteOn(int channel, int midiNoteNumber, float velocity)
{
    synth.noteOn(channel, midiNoteNumber, velocity);
}

void SamplerInstrument::noteOff(int channel, int midiNoteNumber, float velocity, bool allowTailOff)
{
    synth.noteOff(channel, midiNoteNumber, velocity, allowTailOff);
}

void SamplerInstrument::allNotesOff(int channel, bool allowTailOff)
{
    synth.allNotesOff(channel, allowTailOff);
}

void SamplerInstrument::setPolyphony(int numVoices)
{
    if (numVoices != polyphony && numVoices > 0)
    {
        polyphony = numVoices;
        setupVoices(polyphony);
    }
}

void SamplerInstrument::setupVoices(int numVoices)
{
    synth.clearVoices();
    
    for (int i = 0; i < numVoices; ++i)
        synth.addVoice(new ZonedSamplerVoice());
}

} // namespace mmg
