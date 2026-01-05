/*
  ==============================================================================

    SFZInstrument.cpp
    
    Implementation of SFZ-based sampler instrument.

  ==============================================================================
*/

#include "SFZInstrument.h"

namespace mmg
{

//==============================================================================
// SFZVoice Implementation
//==============================================================================

void SFZVoice::startNote(int midiNote, float velocity, const SFZRegion* reg,
                         juce::AudioBuffer<float>* sampleBuffer, double sampleRate)
{
    if (reg == nullptr || sampleBuffer == nullptr || sampleBuffer->getNumSamples() == 0)
        return;
    
    active = true;
    currentNote = midiNote;
    currentVelocity = velocity;
    region = reg;
    sampleData = sampleBuffer;
    targetSampleRate = sampleRate;
    
    // Start position
    samplePosition = static_cast<double>(region->offset);
    
    // Calculate pitch ratio
    calculatePitchRatio();
    
    // Calculate envelope rates
    calculateEnvelopeRates();
    envState = EnvelopeState::Attack;
    envLevel = 0.0f;
    
    // Calculate gain with velocity curve and volume boost
    // Apply velocity curve (0.6 power for more natural response, louder low-velocity hits)
    float velocityCurve = std::pow(velocity, 0.6f);
    
    // Apply region volume (dB to linear) with +12dB boost
    float volumeGain = std::pow(10.0f, (region->volume + 12.0f) / 20.0f);
    float totalGain = velocityCurve * volumeGain * 3.0f;  // Additional 3x boost (~10dB)
    
    // Apply panning
    float pan = region->pan / 100.0f;  // -1 to +1
    gainL = totalGain * std::sqrt(0.5f * (1.0f - pan));
    gainR = totalGain * std::sqrt(0.5f * (1.0f + pan));
}

void SFZVoice::stopNote(bool allowTailOff)
{
    if (!active)
        return;
    
    if (allowTailOff && region != nullptr && region->ampeg_release > 0.001f)
    {
        envState = EnvelopeState::Release;
    }
    else
    {
        active = false;
        envState = EnvelopeState::Off;
        envLevel = 0.0f;
    }
}

void SFZVoice::renderNextBlock(juce::AudioBuffer<float>& outputBuffer, 
                                int startSample, int numSamples)
{
    if (!active || sampleData == nullptr || region == nullptr)
        return;
    
    const int numChannels = juce::jmin(outputBuffer.getNumChannels(), sampleData->getNumChannels());
    const int sampleLength = sampleData->getNumSamples();
    const int endSample = (region->end > 0) ? juce::jmin(region->end, sampleLength) : sampleLength;
    
    const float* srcL = sampleData->getReadPointer(0);
    const float* srcR = (numChannels > 1) ? sampleData->getReadPointer(1) : srcL;
    
    float* destL = outputBuffer.getWritePointer(0);
    float* destR = (outputBuffer.getNumChannels() > 1) ? outputBuffer.getWritePointer(1) : nullptr;
    
    for (int i = 0; i < numSamples; ++i)
    {
        // Process envelope
        float env = processEnvelope();
        
        if (envState == EnvelopeState::Off)
        {
            active = false;
            break;
        }
        
        // Check if we've reached the end
        int pos = static_cast<int>(samplePosition);
        if (pos >= endSample - 1)
        {
            // Handle looping
            if (region->loop_mode == "loop_continuous" || region->loop_mode == "loop_sustain")
            {
                int loopStart = region->loop_start;
                int loopEnd = (region->loop_end > 0) ? region->loop_end : endSample;
                
                if (region->loop_mode == "loop_sustain" && envState == EnvelopeState::Release)
                {
                    // Stop looping on release
                    active = false;
                    break;
                }
                
                // Wrap to loop start
                samplePosition = loopStart + std::fmod(samplePosition - loopStart, loopEnd - loopStart);
            }
            else
            {
                // No loop - fade out
                active = false;
                break;
            }
        }
        
        // Linear interpolation for sample playback
        pos = static_cast<int>(samplePosition);
        float frac = static_cast<float>(samplePosition - pos);
        
        if (pos >= 0 && pos < sampleLength - 1)
        {
            float sampleL = srcL[pos] + frac * (srcL[pos + 1] - srcL[pos]);
            float sampleR = srcR[pos] + frac * (srcR[pos + 1] - srcR[pos]);
            
            // Apply envelope and gain
            int outIdx = startSample + i;
            destL[outIdx] += sampleL * env * gainL;
            if (destR != nullptr)
                destR[outIdx] += sampleR * env * gainR;
        }
        
        // Advance position
        samplePosition += pitchRatio;
    }
}

void SFZVoice::calculatePitchRatio()
{
    if (region == nullptr)
    {
        pitchRatio = 1.0;
        return;
    }
    
    // Calculate pitch shift from root note
    int rootNote = region->pitch_keycenter;
    float pitchKeytrack = region->pitch_keytrack / 100.0f;
    int transpose = region->transpose;
    float tune = region->tune;
    
    // Semitones to shift (including transpose and pitch keytrack)
    float semitones = (currentNote - rootNote) * pitchKeytrack + transpose + (tune / 100.0f);
    
    // Convert to ratio
    pitchRatio = std::pow(2.0, semitones / 12.0);
    
    // Adjust for sample rate difference
    // (sourceSampleRate is stored when sample is loaded, would need to pass it in)
    // For now, assume sample rate matches target
}

void SFZVoice::calculateEnvelopeRates()
{
    if (region == nullptr || targetSampleRate <= 0)
        return;
    
    // Convert times to rates (time = seconds, rate = per sample)
    float attackTime = juce::jmax(0.001f, region->ampeg_attack);
    float decayTime = juce::jmax(0.001f, region->ampeg_decay);
    float releaseTime = juce::jmax(0.001f, region->ampeg_release);
    
    attackRate = 1.0f / (attackTime * static_cast<float>(targetSampleRate));
    decayRate = 1.0f / (decayTime * static_cast<float>(targetSampleRate));
    releaseRate = 1.0f / (releaseTime * static_cast<float>(targetSampleRate));
    
    sustainLevel = region->ampeg_sustain / 100.0f;
}

float SFZVoice::processEnvelope()
{
    switch (envState)
    {
        case EnvelopeState::Attack:
            envLevel += attackRate;
            if (envLevel >= 1.0f)
            {
                envLevel = 1.0f;
                envState = EnvelopeState::Decay;
            }
            break;
            
        case EnvelopeState::Decay:
            envLevel -= decayRate;
            if (envLevel <= sustainLevel)
            {
                envLevel = sustainLevel;
                envState = EnvelopeState::Sustain;
            }
            break;
            
        case EnvelopeState::Sustain:
            // Hold at sustain level
            break;
            
        case EnvelopeState::Release:
            envLevel -= releaseRate;
            if (envLevel <= 0.0f)
            {
                envLevel = 0.0f;
                envState = EnvelopeState::Off;
            }
            break;
            
        case EnvelopeState::Off:
        default:
            envLevel = 0.0f;
            break;
    }
    
    return envLevel;
}

//==============================================================================
// SFZInstrument Implementation
//==============================================================================

SFZInstrument::SFZInstrument()
{
    formatManager.registerBasicFormats();
    
    // Pre-allocate voices
    voices.reserve(MaxVoices);
    for (int i = 0; i < MaxVoices; ++i)
        voices.push_back(std::make_unique<SFZVoice>());
}

SFZInstrument::~SFZInstrument()
{
    allNotesOff();
}

bool SFZInstrument::loadFromFile(const juce::File& sfzFile)
{
    loaded = false;
    lastError.clear();
    sampleBuffers.clear();
    sampleRates.clear();
    
    // Parse SFZ file
    SFZParser parser;
    if (!parser.parse(sfzFile, instrumentData))
    {
        lastError = parser.getLastError();
        return false;
    }
    
    // Load all samples
    if (!loadSamples())
    {
        return false;
    }
    
    loaded = true;
    DBG("SFZInstrument: Loaded " + sfzFile.getFileName() + " with " + 
        juce::String(getNumRegions()) + " regions");
    
    return true;
}

int SFZInstrument::getNumRegions() const
{
    int count = 0;
    for (const auto& group : instrumentData.groups)
        count += static_cast<int>(group.regions.size());
    return count;
}

void SFZInstrument::setSampleRate(double sampleRate)
{
    currentSampleRate = sampleRate;
}

bool SFZInstrument::loadSamples()
{
    int loadedCount = 0;
    int failedCount = 0;
    
    for (const auto& group : instrumentData.groups)
    {
        for (const auto& region : group.regions)
        {
            juce::String key = region.sampleFile.getFullPathName();
            
            // Skip if already loaded
            if (sampleBuffers.find(key) != sampleBuffers.end())
                continue;
            
            // Load the sample
            if (!region.sampleFile.existsAsFile())
            {
                DBG("SFZInstrument: Sample not found: " + region.sampleFile.getFullPathName());
                failedCount++;
                continue;
            }
            
            std::unique_ptr<juce::AudioFormatReader> reader(
                formatManager.createReaderFor(region.sampleFile));
            
            if (reader == nullptr)
            {
                DBG("SFZInstrument: Could not read sample: " + region.sampleFile.getFileName());
                failedCount++;
                continue;
            }
            
            // Create buffer and read samples
            auto buffer = std::make_unique<juce::AudioBuffer<float>>(
                static_cast<int>(reader->numChannels),
                static_cast<int>(reader->lengthInSamples));
            
            reader->read(buffer.get(), 0, static_cast<int>(reader->lengthInSamples), 0, true, true);
            
            sampleRates[key] = reader->sampleRate;
            sampleBuffers[key] = std::move(buffer);
            loadedCount++;
        }
    }
    
    if (loadedCount == 0 && failedCount > 0)
    {
        lastError = "Failed to load any samples (" + juce::String(failedCount) + " failures)";
        return false;
    }
    
    DBG("SFZInstrument: Loaded " + juce::String(loadedCount) + " samples (" +
        juce::String(failedCount) + " failed)");
    
    return true;
}

void SFZInstrument::noteOn(int midiNote, float velocity)
{
    if (!loaded || velocity <= 0.0f)
        return;
    
    // Find matching regions
    auto regions = instrumentData.findRegions(midiNote, static_cast<int>(velocity * 127.0f));
    
    for (const auto* region : regions)
    {
        // Skip release triggers
        if (region->trigger == "release")
            continue;
        
        // Handle group exclusion (off_by)
        if (region->group > 0)
        {
            handleGroupOff(region->group);
        }
        
        // Find sample buffer
        juce::String key = region->sampleFile.getFullPathName();
        auto bufferIt = sampleBuffers.find(key);
        if (bufferIt == sampleBuffers.end())
            continue;
        
        // Find a free voice
        SFZVoice* voice = findFreeVoice();
        if (voice != nullptr)
        {
            voice->startNote(midiNote, velocity, region, 
                            bufferIt->second.get(), currentSampleRate);
        }
    }
}

void SFZInstrument::noteOff(int midiNote, bool allowTailOff)
{
    for (auto& voice : voices)
    {
        if (voice->isPlayingNote(midiNote))
        {
            voice->stopNote(allowTailOff);
        }
    }
}

void SFZInstrument::allNotesOff()
{
    for (auto& voice : voices)
    {
        voice->stopNote(false);
    }
}

void SFZInstrument::renderNextBlock(juce::AudioBuffer<float>& buffer, 
                                     int startSample, int numSamples)
{
    if (!loaded)
        return;
    
    // Render all active voices
    for (auto& voice : voices)
    {
        if (voice->isActive())
        {
            voice->renderNextBlock(buffer, startSample, numSamples);
        }
    }
    
    // Apply master volume
    if (std::abs(masterVolume - 1.0f) > 0.001f)
    {
        for (int ch = 0; ch < buffer.getNumChannels(); ++ch)
        {
            buffer.applyGain(ch, startSample, numSamples, masterVolume);
        }
    }
}

SFZVoice* SFZInstrument::findFreeVoice()
{
    // Find inactive voice
    for (auto& voice : voices)
    {
        if (!voice->isActive())
            return voice.get();
    }
    
    // Voice stealing - find oldest voice in release
    for (auto& voice : voices)
    {
        // Could implement more sophisticated voice stealing here
        // For now, just steal the first one
        voice->stopNote(false);
        return voice.get();
    }
    
    return nullptr;
}

SFZVoice* SFZInstrument::findVoicePlayingNote(int note)
{
    for (auto& voice : voices)
    {
        if (voice->isPlayingNote(note))
            return voice.get();
    }
    return nullptr;
}

void SFZInstrument::handleGroupOff(int group)
{
    // Stop all voices in the specified group (for exclusive groups like hi-hats)
    for (auto& voice : voices)
    {
        if (voice->isActive() && voice->getGroup() == group)
        {
            voice->stopNote(false);
        }
    }
}

} // namespace mmg
