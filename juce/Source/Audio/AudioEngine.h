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
#include "MixerGraph.h"

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

    /** Load MIDI data directly from memory */
    void loadMidiData(const juce::MidiFile& midi);
    
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
    
    /** Get the MixerGraph for UI access */
    Audio::MixerGraph& getMixerGraph() { return mixerGraph; }
    
    //==========================================================================
    // Live Synthesis (Preview)
    //==========================================================================
    
    /** Trigger a note for preview (fire and forget, auto-release) */
    void playNote(int trackIndex, int noteNumber, float velocity, float durationSeconds = 0.2f);

    /** Set looping state */
    void setLooping(bool shouldLoop);
    bool isLooping() const { return looping.load(); }
    
    /** Set loop region (in seconds). Pass -1, -1 to clear loop region */
    void setLoopRegion(double startSeconds, double endSeconds);
    
    /** Get loop region start (returns -1 if not set) */
    double getLoopRegionStart() const { return loopRegionStart.load(); }
    
    /** Get loop region end (returns -1 if not set) */
    double getLoopRegionEnd() const { return loopRegionEnd.load(); }
    
    /** Check if we have a custom loop region set */
    bool hasLoopRegion() const { return loopRegionStart.load() >= 0 && loopRegionEnd.load() > loopRegionStart.load(); }

    //==========================================================================
    // Track Architecture
    //==========================================================================
    
    class Track
    {
    public:
        Track(int id, const juce::String& name);
        ~Track();
        
        void prepareToPlay(double sampleRate, int samplesPerBlock);
        void releaseResources();
        void renderNextBlock(juce::AudioBuffer<float>& outputBuffer, int startSample, int numSamples);
        
        void noteOn(int note, float velocity);
        void noteOff(int note);
        
        // Load a sample file (WAV, AIFF, etc.)
        void loadSample(const juce::File& file, juce::AudioFormatManager& formatManager);
        
        void setVolume(float newVolume);
        float getVolume() const { return volume.load(); }
        
        void setMute(bool shouldMute);
        bool isMuted() const { return muted.load(); }
        
        void setSolo(bool shouldSolo);
        bool isSoloed() const { return soloed.load(); }
        
        int getId() const { return id; }
        juce::String getName() const { return name; }
        void setName(const juce::String& newName) { name = newName; }
        
    private:
        int id;
        juce::String name;
        juce::Synthesiser synth;
        std::atomic<float> volume { 1.0f };
        std::atomic<bool> muted { false };
        std::atomic<bool> soloed { false };
        
        juce::MidiBuffer midiBuffer;
        juce::CriticalSection trackLock;
        
        JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(Track)
    };
    
    Track* addTrack(const juce::String& name);
    void removeTrack(int index);
    Track* getTrack(int index);
    int getNumTracks() const;
    
    /** Load an instrument sample into a track */
    void loadInstrument(int trackIndex, const juce::File& sampleFile, const juce::String& instrumentName);

    //==========================================================================
    // Audio Visualization Support
    //==========================================================================
    
    /** Listener interface for visualization - receives audio samples */
    class VisualizationListener
    {
    public:
        virtual ~VisualizationListener() = default;
        
        /** Called with audio samples for visualization (on audio thread!) */
        virtual void audioSamplesReady(const float* leftSamples, 
                                       const float* rightSamples, 
                                       int numSamples) = 0;
    };
    
    /** Add a visualization listener (lock-free, call from message thread) */
    void addVisualizationListener(VisualizationListener* listener);
    
    /** Remove a visualization listener (lock-free, call from message thread) */
    void removeVisualizationListener(VisualizationListener* listener);
    
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
    juce::AudioFormatManager formatManager; // Added for file loading
    juce::AudioSourcePlayer sourcePlayer;
    
    // State
    std::atomic<bool> initialised { false };
    std::atomic<TransportState> transportState { TransportState::Stopped };
    std::atomic<bool> looping { false };
    std::atomic<double> loopRegionStart { -1.0 };
    std::atomic<double> loopRegionEnd { -1.0 };
    
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
    
    // Mixer
    Audio::MixerGraph mixerGraph;
    
    // Tracks
    std::vector<std::unique_ptr<Track>> tracks;
    juce::CriticalSection tracksLock;

    // Visualization listeners (lock-free array for audio thread safety)
    static constexpr int maxVisualizationListeners = 8;
    std::array<std::atomic<VisualizationListener*>, maxVisualizationListeners> visualizationListeners;
    
    // Listeners
    juce::ListenerList<Listener> listeners;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(AudioEngine)
};

} // namespace mmg
