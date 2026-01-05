/*
  ==============================================================================

    SF2Instrument.cpp
    
    Implementation of SF2 instrument using TinySoundFont.

  ==============================================================================
*/

// Include TSF implementation in this translation unit only
#define TSF_IMPLEMENTATION
#include "External/tsf.h"

#include "SF2Instrument.h"

namespace mmg
{

//==============================================================================
SF2Instrument::SF2Instrument()
{
}

SF2Instrument::~SF2Instrument()
{
    unload();
}

//==============================================================================
// Loading
//==============================================================================

bool SF2Instrument::load(const juce::File& sf2File)
{
    unload();
    
    if (!sf2File.existsAsFile())
    {
        DBG("SF2Instrument: File not found: " << sf2File.getFullPathName());
        return false;
    }
    
    const juce::ScopedLock sl(lock);
    
    // Load the soundfont
    soundFont = tsf_load_filename(sf2File.getFullPathName().toRawUTF8());
    
    if (soundFont == nullptr)
    {
        DBG("SF2Instrument: Failed to load: " << sf2File.getFullPathName());
        return false;
    }
    
    filePath = sf2File.getFullPathName();
    
    // Configure output
    tsf_set_output(soundFont, TSF_STEREO_INTERLEAVED, 
                   static_cast<int>(currentSampleRate), 0.0f);
    
    // Apply gain boost for better audibility (SF2 samples are often quiet)
    tsf_set_volume(soundFont, 4.0f);  // +12dB boost
    
    DBG("SF2Instrument: Loaded " << sf2File.getFileName() 
        << " with " << getNumPresets() << " presets");
    
    return true;
}

bool SF2Instrument::loadFromMemory(const void* data, int size)
{
    unload();
    
    const juce::ScopedLock sl(lock);
    
    soundFont = tsf_load_memory(data, size);
    
    if (soundFont == nullptr)
    {
        DBG("SF2Instrument: Failed to load from memory");
        return false;
    }
    
    filePath = "<memory>";
    
    tsf_set_output(soundFont, TSF_STEREO_INTERLEAVED,
                   static_cast<int>(currentSampleRate), 0.0f);
    tsf_set_volume(soundFont, 4.0f);  // +12dB boost
    
    return true;
}

void SF2Instrument::unload()
{
    const juce::ScopedLock sl(lock);
    
    if (soundFont != nullptr)
    {
        tsf_close(soundFont);
        soundFont = nullptr;
    }
    
    filePath.clear();
    activePreset = 0;
}

//==============================================================================
// Preset Information
//==============================================================================

int SF2Instrument::getNumPresets() const
{
    if (soundFont == nullptr)
        return 0;
    return tsf_get_presetcount(soundFont);
}

SF2PresetInfo SF2Instrument::getPresetInfo(int index) const
{
    SF2PresetInfo info;
    info.index = index;
    info.bank = 0;
    info.presetNumber = index;
    
    if (soundFont != nullptr && index >= 0 && index < getNumPresets())
    {
        info.name = juce::String(tsf_get_presetname(soundFont, index));
        // TSF doesn't expose bank/preset number directly, use index
    }
    
    return info;
}

std::vector<SF2PresetInfo> SF2Instrument::getAllPresets() const
{
    std::vector<SF2PresetInfo> presets;
    int count = getNumPresets();
    presets.reserve(count);
    
    for (int i = 0; i < count; ++i)
    {
        presets.push_back(getPresetInfo(i));
    }
    
    return presets;
}

int SF2Instrument::findPreset(int bank, int presetNumber) const
{
    if (soundFont == nullptr)
        return -1;
    return tsf_get_presetindex(soundFont, bank, presetNumber);
}

void SF2Instrument::setActivePreset(int presetIndex)
{
    if (presetIndex >= 0 && presetIndex < getNumPresets())
    {
        activePreset = presetIndex;
    }
}

//==============================================================================
// Playback
//==============================================================================

void SF2Instrument::prepareToPlay(double sampleRate, int samplesPerBlock)
{
    currentSampleRate = sampleRate;
    currentBufferSize = samplesPerBlock;
    
    // Resize render buffer for interleaved stereo
    renderBuffer.resize(samplesPerBlock * 2, 0.0f);
    
    const juce::ScopedLock sl(lock);
    
    if (soundFont != nullptr)
    {
        tsf_set_output(soundFont, TSF_STEREO_INTERLEAVED,
                       static_cast<int>(sampleRate), 0.0f);
    }
}

void SF2Instrument::setSampleRate(double sampleRate)
{
    currentSampleRate = sampleRate;
    
    const juce::ScopedLock sl(lock);
    
    if (soundFont != nullptr)
    {
        tsf_set_output(soundFont, TSF_STEREO_INTERLEAVED,
                       static_cast<int>(sampleRate), 0.0f);
    }
}

void SF2Instrument::releaseResources()
{
    renderBuffer.clear();
    renderBuffer.shrink_to_fit();
}

void SF2Instrument::noteOn(int channel, int midiNoteNumber, float velocity)
{
    const juce::ScopedLock sl(lock);
    
    if (soundFont == nullptr)
        return;
    
    // If channel is -1, use the active preset
    if (channel < 0)
    {
        tsf_note_on(soundFont, activePreset, midiNoteNumber, velocity);
    }
    else
    {
        // Use channel as preset index (common for GM compatibility)
        tsf_note_on(soundFont, channel, midiNoteNumber, velocity);
    }
}

void SF2Instrument::noteOn(int midiNoteNumber, float velocity)
{
    noteOn(-1, midiNoteNumber, velocity);
}

void SF2Instrument::noteOff(int channel, int midiNoteNumber)
{
    const juce::ScopedLock sl(lock);
    
    if (soundFont == nullptr)
        return;
    
    if (channel < 0)
    {
        tsf_note_off(soundFont, activePreset, midiNoteNumber);
    }
    else
    {
        tsf_note_off(soundFont, channel, midiNoteNumber);
    }
}

void SF2Instrument::noteOff(int midiNoteNumber)
{
    noteOff(-1, midiNoteNumber);
}

void SF2Instrument::allNotesOff()
{
    const juce::ScopedLock sl(lock);
    
    if (soundFont != nullptr)
    {
        tsf_reset(soundFont);
    }
}

void SF2Instrument::renderNextBlock(juce::AudioBuffer<float>& buffer, int startSample, int numSamples)
{
    const juce::ScopedLock sl(lock);
    
    if (soundFont == nullptr || numSamples <= 0)
        return;
    
    // Ensure render buffer is large enough
    if (renderBuffer.size() < static_cast<size_t>(numSamples * 2))
    {
        renderBuffer.resize(numSamples * 2);
    }
    
    // Clear render buffer
    std::fill(renderBuffer.begin(), renderBuffer.begin() + numSamples * 2, 0.0f);
    
    // Render TSF output to interleaved buffer
    tsf_render_float(soundFont, renderBuffer.data(), numSamples, 0);
    
    // De-interleave and mix into output buffer
    auto* leftOut = buffer.getWritePointer(0, startSample);
    auto* rightOut = buffer.getNumChannels() > 1 ? buffer.getWritePointer(1, startSample) : nullptr;
    
    for (int i = 0; i < numSamples; ++i)
    {
        float left = renderBuffer[i * 2] * gain;
        float right = renderBuffer[i * 2 + 1] * gain;
        
        leftOut[i] += left;
        if (rightOut != nullptr)
            rightOut[i] += right;
    }
}

//==============================================================================
// Settings
//==============================================================================

void SF2Instrument::setGlobalVolumeDb(float db)
{
    const juce::ScopedLock sl(lock);
    
    if (soundFont != nullptr)
    {
        float linear = juce::Decibels::decibelsToGain(db);
        tsf_set_volume(soundFont, linear);
    }
}

void SF2Instrument::setChorusEnabled(bool /*enabled*/)
{
    // TinySoundFont doesn't support effects - would need external processing
}

void SF2Instrument::setReverbEnabled(bool /*enabled*/)
{
    // TinySoundFont doesn't support effects - would need external processing
}

} // namespace mmg
