/*
  ==============================================================================
    AudioEngine.cpp
    
    Implementation of the central audio engine.
    
    Task 0.3: JUCE Audio Architecture Prototype
    Task 0.4: MIDI Playback Integration
  ==============================================================================
*/

#include "AudioEngine.h"

#include <cmath>

namespace mmg
{

//==============================================================================
// Default Synth ("Default (Sine)")
//==============================================================================
struct DefaultSynthSound : public juce::SynthesiserSound
{
    bool appliesToNote (int) override { return true; }
    bool appliesToChannel (int) override { return true; }
};

struct DefaultSynthVoice : public juce::SynthesiserVoice
{
    explicit DefaultSynthVoice(mmg::AudioEngine::Track::DefaultSynthState& state)
        : synthState(state)
    {
    }

    bool canPlaySound (juce::SynthesiserSound* sound) override
    {
        return dynamic_cast<DefaultSynthSound*> (sound) != nullptr;
    }

    void startNote (int midiNoteNumber, float velocity,
                    juce::SynthesiserSound*, int /*currentPitchWheelPosition*/) override
    {
        phase = 0.0;
        lfoPhase = 0.0;
        currentFreqHz = juce::MidiMessage::getMidiNoteInHertz(midiNoteNumber);
        level = juce::jlimit(0.0, 1.0, (double)velocity) * 0.8;
        lpLast = 0.0f;

        juce::ADSR::Parameters envParams;
        envParams.attack = juce::jlimit(0.0f, 10.0f, synthState.attackSeconds.load());
        envParams.decay = 0.0f;
        envParams.sustain = 1.0f;
        envParams.release = juce::jlimit(0.001f, 30.0f, synthState.releaseSeconds.load());

        envelope.setSampleRate(getSampleRate());
        envelope.setParameters(envParams);
        envelope.noteOn();
    }

    void stopNote (float /*velocity*/, bool allowTailOff) override
    {
        if (allowTailOff)
        {
            envelope.noteOff();
        }
        else
        {
            envelope.reset();
            clearCurrentNote();
        }
    }

    void pitchWheelMoved (int) override {}
    void controllerMoved (int, int) override {}

    void renderNextBlock (juce::AudioBuffer<float>& outputBuffer, int startSample, int numSamples) override
    {
        const double sampleRate = getSampleRate();
        if (sampleRate <= 0.0)
            return;

        const int waveform = synthState.waveform.load();
        const float cutoffHz = juce::jlimit(40.0f, 20000.0f, synthState.cutoffHz.load());
        const float lfoRateHz = juce::jlimit(0.0f, 40.0f, synthState.lfoRateHz.load());
        const float lfoDepth = juce::jlimit(0.0f, 1.0f, synthState.lfoDepth.load());

        // One-pole lowpass coefficient
        const float alpha = std::exp(-2.0f * (float)juce::MathConstants<double>::pi * cutoffHz / (float)sampleRate);

        while (--numSamples >= 0)
        {
            const float env = envelope.getNextSample();
            if (!envelope.isActive())
            {
                clearCurrentNote();
                break;
            }

            // Oscillator
            float osc = 0.0f;
            const float phaseNorm = (float)(phase / (2.0 * juce::MathConstants<double>::pi));
            const float frac = phaseNorm - std::floor(phaseNorm);

            switch (waveform)
            {
                case (int)mmg::AudioEngine::DefaultSynthWaveform::Triangle:
                {
                    // Triangle in [-1,1]
                    osc = 4.0f * std::fabs(frac - 0.5f) - 1.0f;
                    break;
                }
                case (int)mmg::AudioEngine::DefaultSynthWaveform::Saw:
                {
                    osc = 2.0f * frac - 1.0f;
                    break;
                }
                case (int)mmg::AudioEngine::DefaultSynthWaveform::Square:
                {
                    osc = (frac < 0.5f) ? 1.0f : -1.0f;
                    break;
                }
                case (int)mmg::AudioEngine::DefaultSynthWaveform::Sine:
                default:
                {
                    osc = std::sin((float)phase);
                    break;
                }
            }

            // Simple amplitude LFO (tremolo)
            float lfo = 1.0f;
            if (lfoRateHz > 0.0f && lfoDepth > 0.0f)
            {
                const float lfoSin = std::sin((float)lfoPhase);
                lfo = 1.0f - lfoDepth + lfoDepth * (0.5f * (lfoSin + 1.0f));
            }

            float sample = osc * (float)level * env * lfo;

            // One-pole lowpass
            lpLast = (1.0f - alpha) * sample + alpha * lpLast;
            sample = lpLast;

            for (auto i = outputBuffer.getNumChannels(); --i >= 0;)
                outputBuffer.addSample(i, startSample, sample);

            phase += (2.0 * juce::MathConstants<double>::pi * currentFreqHz) / sampleRate;
            if (phase >= 2.0 * juce::MathConstants<double>::pi)
                phase -= 2.0 * juce::MathConstants<double>::pi;

            if (lfoRateHz > 0.0f)
            {
                lfoPhase += (2.0 * juce::MathConstants<double>::pi * (double)lfoRateHz) / sampleRate;
                if (lfoPhase >= 2.0 * juce::MathConstants<double>::pi)
                    lfoPhase -= 2.0 * juce::MathConstants<double>::pi;
            }

            ++startSample;
        }
    }

    mmg::AudioEngine::Track::DefaultSynthState& synthState;
    juce::ADSR envelope;

    double currentFreqHz = 440.0;
    double phase = 0.0;
    double lfoPhase = 0.0;
    double level = 0.0;
    float lpLast = 0.0f;
};

//==============================================================================
// AudioEngine::Track Implementation
//==============================================================================

AudioEngine::Track::Track(int id, const juce::String& name, juce::AudioFormatManager& formatMgr)
    : id(id), name(name), formatManager(formatMgr)
{
    // Setup simple sine synth as fallback
    simpleSynth.clearVoices();
    for (int i = 0; i < 8; ++i)
        simpleSynth.addVoice(new DefaultSynthVoice(defaultSynth));
        
    simpleSynth.clearSounds();
    simpleSynth.addSound(new DefaultSynthSound());
    
    activeInstrumentType = InstrumentType::SimpleSynth;
}

void AudioEngine::Track::setDefaultSynthWaveform(DefaultSynthWaveform waveform)
{
    defaultSynth.waveform.store((int)waveform);
}

void AudioEngine::Track::setDefaultSynthParam(DefaultSynthParam param, float value)
{
    switch (param)
    {
        case DefaultSynthParam::AttackSeconds:
            defaultSynth.attackSeconds.store(value);
            break;
        case DefaultSynthParam::ReleaseSeconds:
            defaultSynth.releaseSeconds.store(value);
            break;
        case DefaultSynthParam::CutoffHz:
            defaultSynth.cutoffHz.store(value);
            break;
        case DefaultSynthParam::LfoRateHz:
            defaultSynth.lfoRateHz.store(value);
            break;
        case DefaultSynthParam::LfoDepth:
            defaultSynth.lfoDepth.store(value);
            break;
        default:
            break;
    }
}

AudioEngine::Track::~Track() {}

void AudioEngine::Track::prepareToPlay(double sampleRate, int samplesPerBlock)
{
    simpleSynth.setCurrentPlaybackSampleRate(sampleRate);
    sampler.prepareToPlay(sampleRate, samplesPerBlock);
    
    if (sf2Instrument)
        sf2Instrument->setSampleRate(sampleRate);
    if (sfzInstrument)
        sfzInstrument->setSampleRate(sampleRate);
}

void AudioEngine::Track::releaseResources() 
{
    {
        const juce::ScopedLock sl(trackLock);
        // Ensure any sustaining voices are released immediately.
        midiBuffer.clear();
        simpleSynth.allNotesOff(0, true);
        sampler.allNotesOff(0, true);
    }

    sampler.releaseResources();
    if (sf2Instrument)
        sf2Instrument->allNotesOff();
    if (sfzInstrument)
        sfzInstrument->allNotesOff();
}

void AudioEngine::Track::renderNextBlock(juce::AudioBuffer<float>& outputBuffer, int startSample, int numSamples)
{
    if (muted.load())
    {
        // Zero out metering when muted
        rmsLevel.store(0.0f);
        peakLevel.store(0.0f);
        return;
    }
        
    // Render synth to a temp buffer
    juce::AudioBuffer<float> tempBuffer(outputBuffer.getNumChannels(), numSamples);
    tempBuffer.clear();
    
    {
        const juce::ScopedLock sl(trackLock);
        
        switch (activeInstrumentType)
        {
            case InstrumentType::SF2:
                if (sf2Instrument && sf2Instrument->isLoaded())
                {
                    sf2Instrument->renderNextBlock(tempBuffer, 0, numSamples);
                }
                break;
                
            case InstrumentType::SFZ:
                if (sfzInstrument && sfzInstrument->isLoaded())
                {
                    sfzInstrument->renderNextBlock(tempBuffer, 0, numSamples);
                }
                break;
                
            case InstrumentType::ExpansionSampler:
                if (sampler.isLoaded())
                {
                    sampler.renderNextBlock(tempBuffer, midiBuffer, 0, numSamples);
                }
                break;
                
            case InstrumentType::SimpleSynth:
            case InstrumentType::None:
            default:
                simpleSynth.renderNextBlock(tempBuffer, midiBuffer, 0, numSamples);
                break;
        }
        midiBuffer.clear();
    }
    
    // Apply volume
    tempBuffer.applyGain(volume.load());
    
    // Compute RMS and peak for metering (average across channels)
    {
        float rms = 0.0f;
        float peak = 0.0f;
        int numChannels = tempBuffer.getNumChannels();
        
        for (int ch = 0; ch < numChannels; ++ch)
        {
            rms += tempBuffer.getRMSLevel(ch, 0, numSamples);
            peak = juce::jmax(peak, tempBuffer.getMagnitude(ch, 0, numSamples));
        }
        
        if (numChannels > 0)
            rms /= (float)numChannels;
        
        rmsLevel.store(rms);
        peakLevel.store(peak);
    }
    
    // Mix into output
    for (int ch = 0; ch < outputBuffer.getNumChannels(); ++ch)
    {
        outputBuffer.addFrom(ch, startSample, tempBuffer, ch, 0, numSamples);
    }
}

void AudioEngine::Track::noteOn(int note, float velocity)
{
    const juce::ScopedLock sl(trackLock);
    
    switch (activeInstrumentType)
    {
        case InstrumentType::SF2:
            if (sf2Instrument)
                sf2Instrument->noteOn(note, velocity);
            break;
            
        case InstrumentType::SFZ:
            if (sfzInstrument)
                sfzInstrument->noteOn(note, velocity);
            break;
            
        default:
            midiBuffer.addEvent(juce::MidiMessage::noteOn(1, note, velocity), 0);
            break;
    }
}

void AudioEngine::Track::noteOff(int note)
{
    const juce::ScopedLock sl(trackLock);
    
    switch (activeInstrumentType)
    {
        case InstrumentType::SF2:
            if (sf2Instrument)
                sf2Instrument->noteOff(note);
            break;
            
        case InstrumentType::SFZ:
            if (sfzInstrument)
                sfzInstrument->noteOff(note);
            break;
            
        default:
            midiBuffer.addEvent(juce::MidiMessage::noteOff(1, note), 0);
            break;
    }
}

void AudioEngine::Track::setVolume(float newVolume) { volume = newVolume; }
void AudioEngine::Track::setMute(bool shouldMute) { muted = shouldMute; }
void AudioEngine::Track::setSolo(bool shouldSolo) { soloed = shouldSolo; }

bool AudioEngine::Track::loadInstrumentById(const juce::String& instrumentId, 
                                            const ExpansionInstrumentLoader& loader,
                                            juce::AudioFormatManager& fmtManager)
{
    const auto* instrument = loader.getInstrument(instrumentId);
    if (!instrument)
    {
        DBG("Track " << id << ": Instrument not found: " << instrumentId);
        return false;
    }
    
    const juce::ScopedLock sl(trackLock);
    
    if (sampler.loadFromDefinition(*instrument, fmtManager))
    {
        currentInstrumentId = instrumentId;
        currentInstrumentName = instrument->name;
        useSimpleSynth = false;
        activeInstrumentType = InstrumentType::ExpansionSampler;
        
        DBG("Track " << id << ": Loaded " << instrument->name);
        return true;
    }
    
    DBG("Track " << id << ": Failed to load " << instrumentId);
    return false;
}

bool AudioEngine::Track::loadSF2(const juce::File& sf2File, int preset)
{
    const juce::ScopedLock sl(trackLock);
    
    if (!sf2Instrument)
        sf2Instrument = std::make_unique<SF2Instrument>();
    
    if (sf2Instrument->load(sf2File))
    {
        // Set the preset if specified
        if (preset >= 0 && preset < sf2Instrument->getNumPresets())
            sf2Instrument->setActivePreset(preset);
        
        currentInstrumentId = "sf2:" + sf2File.getFileNameWithoutExtension();
        currentInstrumentName = sf2File.getFileNameWithoutExtension();
        
        if (sf2Instrument->getNumPresets() > preset)
        {
            auto presetInfo = sf2Instrument->getPresetInfo(preset);
            if (presetInfo.name.isNotEmpty())
                currentInstrumentName = presetInfo.name;
        }
        
        activeInstrumentType = InstrumentType::SF2;
        useSimpleSynth = false;
        
        DBG("Track " << id << ": Loaded SF2 " << sf2File.getFileName() << " preset " << preset);
        return true;
    }
    
    DBG("Track " << id << ": Failed to load SF2 " << sf2File.getFileName());
    return false;
}

bool AudioEngine::Track::loadSFZ(const juce::File& sfzFile)
{
    const juce::ScopedLock sl(trackLock);
    
    if (!sfzInstrument)
        sfzInstrument = std::make_unique<SFZInstrument>();
    
    if (sfzInstrument->loadFromFile(sfzFile))
    {
        currentInstrumentId = "sfz:" + sfzFile.getFileNameWithoutExtension();
        currentInstrumentName = sfzFile.getFileNameWithoutExtension();
        activeInstrumentType = InstrumentType::SFZ;
        useSimpleSynth = false;
        
        DBG("Track " << id << ": Loaded SFZ " << sfzFile.getFileName() << 
            " with " << sfzInstrument->getNumRegions() << " regions");
        return true;
    }
    
    DBG("Track " << id << ": Failed to load SFZ " << sfzFile.getFileName() << 
        ": " << sfzInstrument->getLastError());
    return false;
}

void AudioEngine::Track::loadSample(const juce::File& file, juce::AudioFormatManager& fmtManager)
{
    const juce::ScopedLock sl(trackLock);
    
    std::unique_ptr<juce::AudioFormatReader> reader(fmtManager.createReaderFor(file));
    if (reader)
    {
        simpleSynth.clearSounds();
        simpleSynth.clearVoices();
        
        // Map to all notes
        juce::BigInteger allNotes;
        allNotes.setRange(0, 128, true);
        
        // Create SamplerSound
        // Base note 60 (C3), Attack 0.0s, Release 0.1s, Max length 10.0s
        simpleSynth.addSound(new juce::SamplerSound("Sample", *reader, allNotes, 60, 0.0, 0.1, 10.0));
        
        // Add SamplerVoices
        for (int i = 0; i < 8; ++i)
            simpleSynth.addVoice(new juce::SamplerVoice());
        
        useSimpleSynth = true;
        activeInstrumentType = InstrumentType::SimpleSynth;
        currentInstrumentId.clear();
        currentInstrumentName = file.getFileNameWithoutExtension();
            
        DBG("Track " << id << ": Loaded sample " << file.getFileName());
    }
    else
    {
        DBG("Track " << id << ": Failed to load sample " << file.getFileName());
    }
}

//==============================================================================
AudioEngine::AudioEngine()
{
    // Register audio format readers (WAV, AIFF, etc.) - CRITICAL for sample loading!
    formatManager.registerBasicFormats();
    DBG("AudioEngine: Registered " << formatManager.getNumKnownFormats() << " audio formats");
    
    // Register as listener for device changes
    deviceManager.addChangeListener(this);
    
    // Register as MIDI listener to route notes to Track instruments
    midiPlayer.setMidiListener(this);
    // We have per-track instruments (including a sine fallback), so keep MidiPlayer's
    // internal synth muted to avoid masking/doubling.
    midiPlayer.setRenderInternalSynth(false);
    
    // Initialize visualization listeners to nullptr
    for (auto& listener : visualizationListeners)
        listener.store(nullptr);
        
    // Initialize Tracks
    for (int i = 0; i < 4; ++i)
    {
        addTrack("Track " + juce::String(i + 1));
    }
}

AudioEngine::~AudioEngine()
{
    shutdown();
    deviceManager.removeChangeListener(this);
}

//==============================================================================
// Initialization
//==============================================================================

juce::String AudioEngine::initialise()
{
    if (initialised.load())
        return {}; // Already initialized
    
    // Initialize with default devices
    // 0 input channels, 2 output channels (stereo)
    auto result = deviceManager.initialiseWithDefaultDevices(0, 2);
    
    if (result.isNotEmpty())
    {
        DBG("AudioEngine: Failed to initialize: " + result);
        return result;
    }
    
    // Connect audio source player to device manager
    deviceManager.addAudioCallback(&sourcePlayer);
    sourcePlayer.setSource(this);
    
    // Get initial audio settings
    if (auto* device = deviceManager.getCurrentAudioDevice())
    {
        currentSampleRate = device->getCurrentSampleRate();
        currentBufferSize = device->getCurrentBufferSizeSamples();
        
        DBG("AudioEngine: Initialized successfully");
        DBG("  Sample Rate: " << currentSampleRate);
        DBG("  Buffer Size: " << currentBufferSize);
        DBG("  Device: " << device->getName());
    }
    
    initialised = true;
    return {};
}

void AudioEngine::shutdown()
{
    if (!initialised.load())
        return;
    
    stop();
    
    sourcePlayer.setSource(nullptr);
    deviceManager.removeAudioCallback(&sourcePlayer);
    deviceManager.closeAudioDevice();
    
    initialised = false;
    DBG("AudioEngine: Shutdown complete");
}

//==============================================================================
// Transport Controls
//==============================================================================

void AudioEngine::play()
{
    DBG("AudioEngine::play() called");
    DBG("  initialised: " << (initialised.load() ? "YES" : "NO"));
    DBG("  hasMidiLoaded: " << (midiPlayer.hasMidiLoaded() ? "YES" : "NO"));
    DBG("  testToneEnabled: " << (testToneEnabled.load() ? "YES" : "NO"));
    
    if (!initialised.load())
    {
        DBG("  ABORT: not initialised");
        return;
    }
        
    setTransportState(TransportState::Starting);
    setTransportState(TransportState::Playing);
    DBG("  Transport state set to Playing");
}

void AudioEngine::pause()
{
    if (!initialised.load())
        return;
        
    if (transportState.load() == TransportState::Playing)
    {
        setTransportState(TransportState::Pausing);
        setTransportState(TransportState::Paused);
    }
}

void AudioEngine::stop()
{
    if (!initialised.load())
        return;
        
    auto currentState = transportState.load();
    if (currentState != TransportState::Stopped)
    {
        setTransportState(TransportState::Stopping);

        // Stop any always-on sources (e.g., test tone)
        setTestToneEnabled(false);
        
        // Stop MIDI playback
        midiPlayer.setPlaying(false);
        midiPlayer.setPosition(0.0);
        
        // Send all notes off to stop any sustaining sounds
        {
            const juce::ScopedLock sl(tracksLock);
            for (auto& track : tracks)
            {
                if (track)
                    track->releaseResources();
            }
        }
        
        // Reset test tone
        testTonePhase = 0.0;
        
        setTransportState(TransportState::Stopped);
    }
}

void AudioEngine::setTransportState(TransportState newState)
{
    if (transportState.load() != newState)
    {
        transportState = newState;
        
        // Notify listeners on message thread
        notifyListeners([newState](Listener* l) {
            l->transportStateChanged(newState);
        });
    }
}

//==============================================================================
// Test Tone
//==============================================================================

void AudioEngine::setTestToneEnabled(bool shouldBeEnabled)
{
    testToneEnabled = shouldBeEnabled;
    
    if (shouldBeEnabled)
    {
        testTonePhase = 0.0;
        DBG("AudioEngine: Test tone enabled (440 Hz)");
    }
    else
    {
        DBG("AudioEngine: Test tone disabled");
    }
}

void AudioEngine::setLooping(bool shouldLoop)
{
    looping = shouldLoop;
    DBG("AudioEngine: Looping " << (shouldLoop ? "enabled" : "disabled"));
}

void AudioEngine::setLoopRegion(double startSeconds, double endSeconds)
{
    if (startSeconds < 0 || endSeconds < 0 || endSeconds <= startSeconds)
    {
        // Clear loop region
        loopRegionStart = -1.0;
        loopRegionEnd = -1.0;
        DBG("AudioEngine: Loop region cleared");
    }
    else
    {
        loopRegionStart = startSeconds;
        loopRegionEnd = endSeconds;
        DBG("AudioEngine: Loop region set: " << startSeconds << "s - " << endSeconds << "s");
    }
}

//==============================================================================
// AudioSource Implementation
//==============================================================================

void AudioEngine::prepareToPlay(int samplesPerBlockExpected, double sampleRate)
{
    currentSampleRate = sampleRate;
    currentBufferSize = samplesPerBlockExpected;
    
    // Prepare MIDI player
    midiPlayer.prepareToPlay(sampleRate, samplesPerBlockExpected);
    
    // Prepare Mixer
    mixerGraph.prepareToPlay(sampleRate, samplesPerBlockExpected);
    
    // Prepare Tracks
    const juce::ScopedLock sl(tracksLock);
    for (auto& track : tracks)
        track->prepareToPlay(sampleRate, samplesPerBlockExpected);
    
    DBG("AudioEngine::prepareToPlay - SR: " << sampleRate << ", Block: " << samplesPerBlockExpected);
}

void AudioEngine::releaseResources()
{
    midiPlayer.releaseResources();
    mixerGraph.releaseResources();
    DBG("AudioEngine::releaseResources");
}

void AudioEngine::getNextAudioBlock(const juce::AudioSourceChannelInfo& bufferToFill)
{
    // Clear the buffer first
    bufferToFill.clearActiveBufferRegion();
    
    // Only produce audio if playing
    // if (transportState.load() != TransportState::Playing)
    //    return;
    // NOTE: We want to hear live notes even if transport is stopped!
    
    // MIDI playback (renders to buffer)
    if (transportState.load() == TransportState::Playing && midiPlayer.hasMidiLoaded() && !testToneEnabled.load())
    {
        // Render MIDI directly to the output buffer's active region
        auto* leftChannel = bufferToFill.buffer->getWritePointer(0, bufferToFill.startSample);
        auto* rightChannel = bufferToFill.buffer->getNumChannels() > 1
                           ? bufferToFill.buffer->getWritePointer(1, bufferToFill.startSample)
                           : nullptr;
        
        // Create temporary buffer for MIDI rendering
        juce::AudioBuffer<float> midiBuffer(bufferToFill.buffer->getNumChannels(), bufferToFill.numSamples);
        midiBuffer.clear();
        
        midiPlayer.setPlaying(true);
        midiPlayer.renderNextBlock(midiBuffer, bufferToFill.numSamples);
        
        // Copy MIDI output to the main buffer
        for (int ch = 0; ch < midiBuffer.getNumChannels(); ++ch)
        {
            auto* src = midiBuffer.getReadPointer(ch);
            auto* dst = bufferToFill.buffer->getWritePointer(ch, bufferToFill.startSample);
            for (int i = 0; i < bufferToFill.numSamples; ++i)
            {
                dst[i] = src[i];
            }
        }
        
        // Debug: track max sample in MIDI output
        static int midiDebugCounter = 0;
        if (++midiDebugCounter % 500 == 0)
        {
            float maxSample = 0.0f;
            for (int ch = 0; ch < midiBuffer.getNumChannels(); ++ch)
            {
                auto* data = midiBuffer.getReadPointer(ch);
                for (int i = 0; i < bufferToFill.numSamples; ++i)
                    maxSample = juce::jmax(maxSample, std::abs(data[i]));
            }
            DBG("AudioEngine: MIDI rendered, maxSample=" << maxSample);
        }
        
        // Check if playback finished
        if (!midiPlayer.isPlaying())
        {
            if (looping.load())
            {
                // Check for custom loop region
                double loopStart = loopRegionStart.load();
                double loopEnd = loopRegionEnd.load();
                
                if (loopStart >= 0 && loopEnd > loopStart)
                {
                    // Loop to region start
                    midiPlayer.setPosition(loopStart);
                }
                else
                {
                    // Loop to beginning
                    midiPlayer.setPosition(0.0);
                }
                midiPlayer.setPlaying(true);
            }
            else
            {
                // MIDI finished - stop transport
                juce::MessageManager::callAsync([this]() {
                    stop();
                });
            }
        }
        else if (looping.load())
        {
            // Check if we've reached the loop end point
            double loopStart = loopRegionStart.load();
            double loopEnd = loopRegionEnd.load();
            
            if (loopStart >= 0 && loopEnd > loopStart)
            {
                double currentPos = midiPlayer.getPosition();
                if (currentPos >= loopEnd)
                {
                    midiPlayer.setPosition(loopStart);
                }
            }
        }
    }
    
    // Process Tracks
    {
        const juce::ScopedLock sl(tracksLock);
        
        // Check for solo
        bool anySolo = false;
        for (auto& track : tracks)
            if (track->isSoloed()) { anySolo = true; break; }
            
        for (auto& track : tracks)
        {
            if (anySolo && !track->isSoloed())
                continue;
                
            track->renderNextBlock(*bufferToFill.buffer, bufferToFill.startSample, bufferToFill.numSamples);
        }
    }
    
    // Test tone generation (for verification) - only if no MIDI or test tone enabled
    if (testToneEnabled.load() && currentSampleRate > 0)
    {
        auto* leftChannel = bufferToFill.buffer->getWritePointer(0, bufferToFill.startSample);
        auto* rightChannel = bufferToFill.buffer->getNumChannels() > 1
                           ? bufferToFill.buffer->getWritePointer(1, bufferToFill.startSample)
                           : nullptr;
        
        const double phaseIncrement = juce::MathConstants<double>::twoPi 
                                    * testToneFrequency / currentSampleRate;
        
        for (int sample = 0; sample < bufferToFill.numSamples; ++sample)
        {
            const float sampleValue = static_cast<float>(std::sin(testTonePhase) * testToneAmplitude);
            
            leftChannel[sample] = sampleValue;
            if (rightChannel != nullptr)
                rightChannel[sample] = sampleValue;
            
            testTonePhase += phaseIncrement;
            
            // Keep phase in valid range to prevent precision loss
            if (testTonePhase >= juce::MathConstants<double>::twoPi)
                testTonePhase -= juce::MathConstants<double>::twoPi;
        }
    }
    
    // Compute master bus RMS and peak for metering
    {
        float rms = 0.0f;
        float peak = 0.0f;
        int numChannels = bufferToFill.buffer->getNumChannels();
        
        for (int ch = 0; ch < numChannels; ++ch)
        {
            rms += bufferToFill.buffer->getRMSLevel(ch, bufferToFill.startSample, bufferToFill.numSamples);
            peak = juce::jmax(peak, bufferToFill.buffer->getMagnitude(ch, bufferToFill.startSample, bufferToFill.numSamples));
        }
        
        if (numChannels > 0)
            rms /= (float)numChannels;
        
        masterRmsLevel.store(rms);
        masterPeakLevel.store(peak);
    }
    
    // Send audio samples to visualization listeners (lock-free)
    {
        auto* leftChannel = bufferToFill.buffer->getReadPointer(0, bufferToFill.startSample);
        auto* rightChannel = bufferToFill.buffer->getNumChannels() > 1
                           ? bufferToFill.buffer->getReadPointer(1, bufferToFill.startSample)
                           : leftChannel;
        
        for (auto& listenerPtr : visualizationListeners)
        {
            if (auto* listener = listenerPtr.load())
            {
                listener->audioSamplesReady(leftChannel, rightChannel, bufferToFill.numSamples);
            }
        }
    }
}

//==============================================================================
// ChangeListener Implementation
//==============================================================================

void AudioEngine::changeListenerCallback(juce::ChangeBroadcaster* source)
{
    if (source == &deviceManager)
    {
        // Audio device changed - update our cached values
        if (auto* device = deviceManager.getCurrentAudioDevice())
        {
            currentSampleRate = device->getCurrentSampleRate();
            currentBufferSize = device->getCurrentBufferSizeSamples();
            
            DBG("AudioEngine: Device changed");
            DBG("  Sample Rate: " << currentSampleRate);
            DBG("  Buffer Size: " << currentBufferSize);
            DBG("  Device: " << device->getName());
        }
        
        notifyListeners([](Listener* l) {
            l->audioDeviceChanged();
        });
    }
}

//==============================================================================
// MidiPlayerListener Implementation (for routing MIDI to Tracks)
//==============================================================================

void AudioEngine::midiNoteOn(int channel, int note, float velocity)
{
    // Route MIDI note-on to the appropriate Track
    // Channel/track index comes from MidiPlayer (0-based)
    if (auto* track = getTrack(channel))
    {
        track->noteOn(note, velocity);
    }
}

void AudioEngine::midiNoteOff(int channel, int note)
{
    // Route MIDI note-off to the appropriate Track
    if (auto* track = getTrack(channel))
    {
        track->noteOff(note);
    }
}

//==============================================================================
// Listener Management
//==============================================================================

void AudioEngine::addListener(Listener* listener)
{
    listeners.add(listener);
}

void AudioEngine::removeListener(Listener* listener)
{
    listeners.remove(listener);
}

void AudioEngine::addVisualizationListener(VisualizationListener* listener)
{
    // Find an empty slot (lock-free for audio thread safety)
    for (auto& slot : visualizationListeners)
    {
        VisualizationListener* expected = nullptr;
        if (slot.compare_exchange_strong(expected, listener))
            return;
    }
    DBG("AudioEngine: Warning - max visualization listeners reached!");
}

void AudioEngine::removeVisualizationListener(VisualizationListener* listener)
{
    // Find and clear the slot
    for (auto& slot : visualizationListeners)
    {
        VisualizationListener* expected = listener;
        slot.compare_exchange_strong(expected, nullptr);
    }
}

void AudioEngine::notifyListeners(std::function<void(Listener*)> callback)
{
    // Ensure we're on the message thread for listener callbacks
    if (juce::MessageManager::getInstance()->isThisTheMessageThread())
    {
        for (int i = listeners.size(); --i >= 0;)
            if (auto* l = listeners.getListeners()[i])
                callback(l);
    }
    else
    {
        juce::MessageManager::callAsync([this, callback]() {
            for (int i = listeners.size(); --i >= 0;)
                if (auto* l = listeners.getListeners()[i])
                    callback(l);
        });
    }
}

//==============================================================================
// MIDI Playback
//==============================================================================

bool AudioEngine::loadMidiFile(const juce::File& midiFile)
{
    DBG("AudioEngine::loadMidiFile - " << midiFile.getFullPathName());
    
    // Stop playback first
    stop();
    
    bool success = midiPlayer.loadMidiFile(midiFile);
    
    if (success)
    {
        DBG("AudioEngine: Loaded MIDI file - " << midiFile.getFileName());
        DBG("  Duration: " << midiPlayer.getTotalDuration() << "s");
        DBG("  BPM: " << midiPlayer.getBPM());
        DBG("  hasMidiLoaded now: " << (midiPlayer.hasMidiLoaded() ? "YES" : "NO"));
    }
    else
    {
        DBG("AudioEngine: FAILED to load MIDI file!");
    }
    
    return success;
}

bool AudioEngine::loadAudioFile(const juce::File& audioFile)
{
    // TODO: Phase 2 - Implement full audio file playback
    // For now, just log and return false until we have an audio file player
    DBG("AudioEngine: loadAudioFile requested (not yet implemented) - " << audioFile.getFileName());
    
    // Future implementation will:
    // 1. Load audio file using AudioFormatReader
    // 2. Create AudioTransportSource for playback
    // 3. Mix with MIDI output through MixerGraph
    
    return false;
}

void AudioEngine::loadMidiData(const juce::MidiFile& midi)
{
    stop();
    midiPlayer.setMidiData(midi);
    DBG("AudioEngine: Loaded MIDI data from memory");
}

void AudioEngine::clearMidiFile()
{
    stop();
    midiPlayer.clearMidiFile();
}

bool AudioEngine::hasMidiLoaded() const
{
    return midiPlayer.hasMidiLoaded();
}

juce::String AudioEngine::getPlaybackDebugStatus() const
{
    juce::String status;
    auto state = transportState.load();
    status += (state == TransportState::Playing) ? "PLAY " : "STOP ";
    status += testToneEnabled.load() ? "TT " : "";
    status += "E:" + juce::String(midiPlayer.getNumEvents()) + " ";
    status += "L:" + juce::String(midiPlayer.getLastMaxSample(), 3) + " ";
    status += juce::String(midiPlayer.getPosition(), 1) + "s";
    return status;
}

bool AudioEngine::renderToWavFile(const juce::File& outputFile, double sampleRate, int bitDepth)
{
    if (!midiPlayer.hasMidiLoaded())
    {
        DBG("AudioEngine::renderToWavFile - No MIDI loaded");
        return false;
    }
    
    // Create a temporary MidiPlayer for offline rendering
    MidiPlayer renderPlayer;
    renderPlayer.prepareToPlay(sampleRate, 512);
    
    // Copy MIDI data from current player
    auto loadedFile = midiPlayer.getLoadedFile();
    if (!loadedFile.existsAsFile())
    {
        DBG("AudioEngine::renderToWavFile - MIDI file not found");
        return false;
    }
    
    if (!renderPlayer.loadMidiFile(loadedFile))
    {
        DBG("AudioEngine::renderToWavFile - Failed to load MIDI for rendering");
        return false;
    }
    
    double totalDuration = renderPlayer.getTotalDuration();
    int totalSamples = static_cast<int>(totalDuration * sampleRate) + static_cast<int>(sampleRate); // Add 1 second for tail
    
    DBG("AudioEngine::renderToWavFile - Rendering " << totalDuration << "s to " << outputFile.getFullPathName());
    
    // Create output buffer
    juce::AudioBuffer<float> outputBuffer(2, totalSamples);
    outputBuffer.clear();
    
    // Render in blocks
    const int blockSize = 512;
    renderPlayer.setPlaying(true);
    renderPlayer.setPosition(0.0);
    
    for (int pos = 0; pos < totalSamples && renderPlayer.isPlaying(); pos += blockSize)
    {
        int numSamples = juce::jmin(blockSize, totalSamples - pos);
        
        // Create a sub-buffer for this block
        juce::AudioBuffer<float> blockBuffer(2, numSamples);
        blockBuffer.clear();
        
        renderPlayer.renderNextBlock(blockBuffer, numSamples);
        
        // Copy to output buffer
        for (int ch = 0; ch < 2; ++ch)
        {
            outputBuffer.copyFrom(ch, pos, blockBuffer, ch, 0, numSamples);
        }
    }
    
    // Write to WAV file
    outputFile.deleteFile();
    std::unique_ptr<juce::FileOutputStream> outStream(outputFile.createOutputStream());
    
    if (outStream == nullptr)
    {
        DBG("AudioEngine::renderToWavFile - Could not create output file");
        return false;
    }
    
    juce::WavAudioFormat wavFormat;
    std::unique_ptr<juce::AudioFormatWriter> writer(
        wavFormat.createWriterFor(outStream.get(), sampleRate, 2, bitDepth, {}, 0));
    
    if (writer == nullptr)
    {
        DBG("AudioEngine::renderToWavFile - Could not create WAV writer");
        return false;
    }
    
    outStream.release(); // Writer takes ownership
    
    if (!writer->writeFromAudioSampleBuffer(outputBuffer, 0, outputBuffer.getNumSamples()))
    {
        DBG("AudioEngine::renderToWavFile - Failed to write audio data");
        return false;
    }
    
    DBG("AudioEngine::renderToWavFile - Successfully rendered to " << outputFile.getFullPathName());
    return true;
}

double AudioEngine::getPlaybackPosition() const
{
    return midiPlayer.getPosition();
}

void AudioEngine::setPlaybackPosition(double positionSeconds)
{
    midiPlayer.setPosition(positionSeconds);
}

double AudioEngine::getTotalDuration() const
{
    return midiPlayer.getTotalDuration();
}

AudioEngine::Track* AudioEngine::addTrack(const juce::String& name)
{
    const juce::ScopedLock sl(tracksLock);
    int id = (int)tracks.size(); // Simple ID generation
    auto newTrack = std::make_unique<Track>(id, name, formatManager);
    if (currentSampleRate > 0)
        newTrack->prepareToPlay(currentSampleRate, currentBufferSize);
    
    auto* ptr = newTrack.get();
    tracks.push_back(std::move(newTrack));
    return ptr;
}

void AudioEngine::removeTrack(int index)
{
    const juce::ScopedLock sl(tracksLock);
    if (index >= 0 && index < tracks.size())
        tracks.erase(tracks.begin() + index);
}

AudioEngine::Track* AudioEngine::getTrack(int index)
{
    const juce::ScopedLock sl(tracksLock);
    if (index >= 0 && index < tracks.size())
        return tracks[index].get();
    return nullptr;
}

int AudioEngine::getNumTracks() const
{
    const juce::ScopedLock sl(tracksLock);
    return (int)tracks.size();
}

void AudioEngine::playNote(int trackIndex, int noteNumber, float velocity, float durationSeconds)
{
    if (auto* track = getTrack(trackIndex))
        track->noteOn(noteNumber, velocity);

    // Fire-and-forget preview notes must be turned off, otherwise they can sustain indefinitely.
    // If durationSeconds isn't provided, use a short default so clicks on keys/notes don't stick.
    const float effectiveDurationSeconds = (durationSeconds > 0.0f ? durationSeconds : 0.25f);
    const int delayMs = juce::jlimit(1, 60 * 1000, (int)std::round(effectiveDurationSeconds * 1000.0f));

    juce::Timer::callAfterDelay(delayMs, [this, trackIndex, noteNumber]() {
        if (!initialised.load())
            return;

        if (auto* track = getTrack(trackIndex))
            track->noteOff(noteNumber);
    });
}

void AudioEngine::loadInstrument(int trackIndex, const juce::File& sampleFile, const juce::String& instrumentName)
{
    if (auto* track = getTrack(trackIndex))
    {
        track->loadSample(sampleFile, formatManager);
        if (instrumentName.isNotEmpty())
            track->setName(instrumentName);
    }
}

//==============================================================================
// Expansion Instruments
//==============================================================================

int AudioEngine::scanExpansions(const juce::File& expansionsDir)
{
    DBG("AudioEngine: Scanning expansions at " << expansionsDir.getFullPathName());
    return expansionLoader.scanExpansionsDirectory(expansionsDir);
}

bool AudioEngine::loadTrackInstrument(int trackIndex, const juce::String& instrumentId)
{
    if (auto* track = getTrack(trackIndex))
    {
        return track->loadInstrumentById(instrumentId, expansionLoader, formatManager);
    }
    return false;
}

void AudioEngine::setTrackDefaultSynthWaveform(int trackIndex, DefaultSynthWaveform waveform)
{
    if (auto* track = getTrack(trackIndex))
        track->setDefaultSynthWaveform(waveform);
}

void AudioEngine::setTrackDefaultSynthParam(int trackIndex, DefaultSynthParam param, float value)
{
    if (auto* track = getTrack(trackIndex))
        track->setDefaultSynthParam(param, value);
}

const InstrumentDefinition* AudioEngine::getInstrumentDefinition(const juce::String& instrumentId) const
{
    return expansionLoader.getInstrument(instrumentId);
}

std::map<juce::String, std::vector<const InstrumentDefinition*>> AudioEngine::getInstrumentsByCategory() const
{
    return expansionLoader.getInstrumentsByCategory();
}

juce::StringArray AudioEngine::getInstrumentCategories() const
{
    return expansionLoader.getCategories();
}

} // namespace mmg
