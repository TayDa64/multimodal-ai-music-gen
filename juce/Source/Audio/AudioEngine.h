/*
  ==============================================================================
    AudioEngine.h
    
    Central audio engine for the AI Music Generator.
    Manages AudioDeviceManager, mixing, and playback.
    
    Task 0.3: JUCE Audio Architecture Prototype
    Task 0.4: MIDI Playback Integration
  ==============================================================================
*/

#pragma once

#include <juce_audio_devices/juce_audio_devices.h>
#include <juce_audio_basics/juce_audio_basics.h>
#include <juce_audio_formats/juce_audio_formats.h>
#include <juce_audio_utils/juce_audio_utils.h>
#include "MidiPlayer.h"

namespace mmg // Multimodal Music Generator
{

//==============================================================================
/**
    AudioEngine manages all audio I/O for the application.
    
    Responsibilities:
    - Initialize and manage AudioDeviceManager
    - Route audio from various sources (synthesizer, file playback)
    - Handle transport controls (play, pause, stop)
    - Provide audio device settings UI integration
    
    Thread Safety:
    - Audio callbacks run on audio thread
    - UI updates must be posted to message thread
    - Use atomics/locks for shared state
*/
class AudioEngine : public juce::AudioSource,
                    public juce::ChangeListener
{
public:
    //==========================================================================
    /** Transport state enumeration */
    enum class TransportState
    {
        Stopped,
        Starting,
        Playing,
        Pausing,
        Paused,
        Stopping
    };
    
    //==========================================================================
    /** Listener interface for engine state changes */
    class Listener
    {
    public:
        virtual ~Listener() = default;
        
        /** Called when transport state changes (on message thread) */
        virtual void transportStateChanged(TransportState newState) {}
        
        /** Called when audio device changes (on message thread) */
        virtual void audioDeviceChanged() {}
        
        /** Called with current playback position in seconds (on message thread) */
        virtual void playbackPositionChanged(double positionSeconds) {}
    };
    
    //==========================================================================
    AudioEngine();
    ~AudioEngine() override;
    
    //==========================================================================
    // Initialization
    //==========================================================================
    
    /** Initialize the audio device with default settings.
        @returns Error message if failed, empty string on success */
    juce::String initialise();
    
    /** Shutdown audio and release resources */
    void shutdown();
    
    /** Check if engine is initialized and ready */
    bool isInitialised() const { return initialised; }
    
    //==========================================================================
    // Device Management
    //==========================================================================
    
    /** Get the AudioDeviceManager for settings UI */
    juce::AudioDeviceManager& getDeviceManager() { return deviceManager; }
    
    /** Get current sample rate */
    double getSampleRate() const { return currentSampleRate; }
    
    /** Get current buffer size */
    int getBufferSize() const { return currentBufferSize; }
    
    //==========================================================================
    // Transport Controls
    //==========================================================================
    
    /** Start playback */
    void play();
    
    /** Pause playback (can resume) */
    void pause();
    
    /** Stop playback (resets position) */
    void stop();
    
    /** Get current transport state */
    TransportState getTransportState() const { return transportState.load(); }
    
    /** Check if currently playing */
    bool isPlaying() const 
    { 
        auto state = transportState.load();
        return state == TransportState::Playing || state == TransportState::Starting;
    }
    
    //==========================================================================
    // Test Tone (for verification)
    //==========================================================================
    
    /** Enable/disable test tone output (440 Hz sine wave)
        Used to verify audio output is working correctly */
    void setTestToneEnabled(bool shouldBeEnabled);
    
    /** Check if test tone is enabled */
    bool isTestToneEnabled() const { return testToneEnabled.load(); }
    
    //==========================================================================
    // MIDI Playback
    //==========================================================================
    
    /** Load a MIDI file for playback
        @returns true if loaded successfully */
    bool loadMidiFile(const juce::File& midiFile);
    
    /** Clear currently loaded MIDI */
    void clearMidiFile();
    
    /** Check if MIDI is loaded */
    bool hasMidiLoaded() const;
    
    /** Get current playback position in seconds */
    double getPlaybackPosition() const;
    
    /** Set playback position in seconds */
    void setPlaybackPosition(double positionSeconds);
    
    /** Get total duration of loaded MIDI in seconds */
    double getTotalDuration() const;
    
    /** Get the MidiPlayer for direct access (advanced usage) */
    MidiPlayer& getMidiPlayer() { return midiPlayer; }
    
    //==========================================================================
    // Listener Management
    //==========================================================================
    
    void addListener(Listener* listener);
    void removeListener(Listener* listener);
    
    //==========================================================================
    // AudioSource Implementation
    //==========================================================================
    
    void prepareToPlay(int samplesPerBlockExpected, double sampleRate) override;
    void releaseResources() override;
    void getNextAudioBlock(const juce::AudioSourceChannelInfo& bufferToFill) override;

private:
    //==========================================================================
    // ChangeListener Implementation (for device changes)
    //==========================================================================
    void changeListenerCallback(juce::ChangeBroadcaster* source) override;
    
    //==========================================================================
    // Internal Methods
    //==========================================================================
    
    void setTransportState(TransportState newState);
    void notifyListeners(std::function<void(Listener*)> callback);
    
    //==========================================================================
    // Members
    //==========================================================================
    
    // Device management
    juce::AudioDeviceManager deviceManager;
    juce::AudioSourcePlayer sourcePlayer;
    
    // State
    std::atomic<bool> initialised { false };
    std::atomic<TransportState> transportState { TransportState::Stopped };
    
    // Audio parameters
    double currentSampleRate { 0.0 };
    int currentBufferSize { 0 };
    
    // Test tone
    std::atomic<bool> testToneEnabled { false };
    double testTonePhase { 0.0 };
    static constexpr double testToneFrequency { 440.0 }; // A4
    static constexpr double testToneAmplitude { 0.25 };  // -12 dB
    
    // MIDI playback
    MidiPlayer midiPlayer;
    
    // Listeners
    juce::ListenerList<Listener> listeners;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(AudioEngine)
};

} // namespace mmg
