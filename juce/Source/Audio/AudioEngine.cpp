/*
  ==============================================================================
    AudioEngine.cpp
    
    Implementation of the central audio engine.
    
    Task 0.3: JUCE Audio Architecture Prototype
    Task 0.4: MIDI Playback Integration
  ==============================================================================
*/

#include "AudioEngine.h"

namespace mmg
{

//==============================================================================
AudioEngine::AudioEngine()
{
    // Register as listener for device changes
    deviceManager.addChangeListener(this);
    
    // Initialize visualization listeners to nullptr
    for (auto& listener : visualizationListeners)
        listener.store(nullptr);
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
    if (!initialised.load())
        return;
        
    setTransportState(TransportState::Starting);
    setTransportState(TransportState::Playing);
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
        
        // Stop MIDI playback
        midiPlayer.setPlaying(false);
        midiPlayer.setPosition(0.0);
        
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

//==============================================================================
// AudioSource Implementation
//==============================================================================

void AudioEngine::prepareToPlay(int samplesPerBlockExpected, double sampleRate)
{
    currentSampleRate = sampleRate;
    currentBufferSize = samplesPerBlockExpected;
    
    // Prepare MIDI player
    midiPlayer.prepareToPlay(sampleRate, samplesPerBlockExpected);
    
    DBG("AudioEngine::prepareToPlay - SR: " << sampleRate << ", Block: " << samplesPerBlockExpected);
}

void AudioEngine::releaseResources()
{
    midiPlayer.releaseResources();
    DBG("AudioEngine::releaseResources");
}

void AudioEngine::getNextAudioBlock(const juce::AudioSourceChannelInfo& bufferToFill)
{
    // Clear the buffer first
    bufferToFill.clearActiveBufferRegion();
    
    // Only produce audio if playing
    if (transportState.load() != TransportState::Playing)
        return;
    
    // MIDI playback (renders to buffer)
    if (midiPlayer.hasMidiLoaded() && !testToneEnabled.load())
    {
        // Create a sub-buffer for the active region
        juce::AudioBuffer<float> subBuffer(bufferToFill.buffer->getArrayOfWritePointers(),
                                           bufferToFill.buffer->getNumChannels(),
                                           bufferToFill.startSample,
                                           bufferToFill.numSamples);
        
        midiPlayer.setPlaying(true);
        midiPlayer.renderNextBlock(subBuffer, bufferToFill.numSamples);
        
        // Check if playback finished
        if (!midiPlayer.isPlaying())
        {
            // MIDI finished - stop transport
            juce::MessageManager::callAsync([this]() {
                stop();
            });
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
    // Stop playback first
    stop();
    
    bool success = midiPlayer.loadMidiFile(midiFile);
    
    if (success)
    {
        DBG("AudioEngine: Loaded MIDI file - " << midiFile.getFileName());
        DBG("  Duration: " << midiPlayer.getTotalDuration() << "s");
        DBG("  BPM: " << midiPlayer.getBPM());
    }
    
    return success;
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

} // namespace mmg
