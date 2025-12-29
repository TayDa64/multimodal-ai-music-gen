/*
  ==============================================================================

    OSCBridge.h
    
    OSC communication bridge for Python backend.

  ==============================================================================
*/

#pragma once

#include <juce_osc/juce_osc.h>
#include <juce_core/juce_core.h>
#include "Messages.h"

//==============================================================================
/**
    Connection state for the OSC bridge.
    Provides clear UI feedback about current status.
*/
enum class ConnectionState
{
    Disconnected,       // No connection established
    Connecting,         // Attempting to connect (waiting for pong)
    Connected,          // Server responded, ready for requests
    Generating,         // Generation in progress
    Canceling,          // Cancel requested, waiting for confirmation
    Error               // Connection error occurred
};

/**
    Convert ConnectionState to a user-friendly string for UI display.
*/
inline juce::String connectionStateToString(ConnectionState state)
{
    switch (state)
    {
        case ConnectionState::Disconnected: return "Disconnected";
        case ConnectionState::Connecting:   return "Connecting...";
        case ConnectionState::Connected:    return "Connected";
        case ConnectionState::Generating:   return "Generating...";
        case ConnectionState::Canceling:    return "Canceling...";
        case ConnectionState::Error:        return "Error";
        default:                            return "Unknown";
    }
}

//==============================================================================
/**
    OSC communication bridge for connecting to Python backend.
    
    Handles:
    - Sending generation requests
    - Receiving progress updates
    - Connection management with timeout/retry
    - Request/response correlation via request_id
*/
class OSCBridge : public juce::OSCReceiver::Listener<juce::OSCReceiver::MessageLoopCallback>,
                  private juce::Timer
{
public:
    //==============================================================================
    /**
        Listener interface for OSC events.
    */
    class Listener
    {
    public:
        virtual ~Listener() = default;
        
        virtual void onConnectionStateChanged(ConnectionState newState) {}
        virtual void onConnectionStatusChanged(bool connected) {}  // Legacy, calls onConnectionStateChanged
        virtual void onProgress(float percent, const juce::String& step, const juce::String& message) {}
        virtual void onGenerationComplete(const GenerationResult& result) {}
        virtual void onError(int code, const juce::String& message) {}
        virtual void onInstrumentsLoaded(int count, const juce::StringPairArray& categories) {}
        
        // Expansion callbacks
        virtual void onExpansionListReceived(const juce::String& json) {}
        virtual void onExpansionInstrumentsReceived(const juce::String& json) {}
        virtual void onExpansionResolveReceived(const juce::String& json) {}
    };
    
    //==============================================================================
    // Timeout and retry configuration
    static constexpr int PingTimeoutMs = 5000;          // 5 seconds to wait for pong
    static constexpr int PingIntervalMs = 3000;         // Ping every 3 seconds when connected
    static constexpr int MaxReconnectBackoffMs = 5000;  // Maximum backoff delay
    static constexpr int InitialReconnectDelayMs = 250; // Starting backoff delay
    
    //==============================================================================
    OSCBridge(int receivePort = 9001, int sendPort = 9000, 
              const juce::String& host = "127.0.0.1");
    ~OSCBridge() override;
    
    //==============================================================================
    // Connection management
    bool connect();
    void disconnect();
    bool isConnected() const { return connectionState == ConnectionState::Connected 
                                   || connectionState == ConnectionState::Generating; }
    
    ConnectionState getConnectionState() const { return connectionState; }
    juce::String getConnectionStateString() const { return connectionStateToString(connectionState); }
    
    /** Get the current request ID being processed (empty if none). */
    juce::String getCurrentRequestId() const { return currentRequestId; }
    
    //==============================================================================
    // Outgoing messages
    void sendGenerate(const GenerationRequest& request);
    void sendCancel(const juce::String& taskId = {});
    void sendPing();
    void sendShutdown();
    void sendGetInstruments(const juce::StringArray& paths, const juce::String& cacheDir = {});
    
    // Expansion management
    void sendExpansionList();
    void sendExpansionInstruments(const juce::String& expansionId);
    void sendExpansionResolve(const juce::String& instrument, const juce::String& genre);
    void sendExpansionImport(const juce::String& path);
    void sendExpansionScan(const juce::String& directory);
    void sendExpansionEnable(const juce::String& expansionId, bool enabled);
    
    //==============================================================================
    // Listeners
    void addListener(Listener* listener);
    void removeListener(Listener* listener);
    
private:
    //==============================================================================
    // Timer callback for ping/timeout handling
    void timerCallback() override;
    
    //==============================================================================
    // OSCReceiver::Listener
    void oscMessageReceived(const juce::OSCMessage& message) override;
    void oscBundleReceived(const juce::OSCBundle& bundle) override;
    
    //==============================================================================
    // Message handlers
    void handleProgress(const juce::OSCMessage& message);
    void handleComplete(const juce::OSCMessage& message);
    void handleError(const juce::OSCMessage& message);
    void handlePong(const juce::OSCMessage& message);
    void handleStatus(const juce::OSCMessage& message);
    void handleInstrumentsLoaded(const juce::OSCMessage& message);
    
    // Expansion handlers
    void handleExpansionList(const juce::OSCMessage& message);
    void handleExpansionInstruments(const juce::OSCMessage& message);
    void handleExpansionResolve(const juce::OSCMessage& message);
    
    //==============================================================================
    void sendMessage(const juce::String& address, const juce::String& jsonPayload = {});
    void setConnectionState(ConnectionState newState);
    void attemptReconnect();
    void resetReconnectBackoff();
    
    //==============================================================================
    juce::OSCReceiver receiver;
    juce::OSCSender sender;
    
    juce::String host;
    int sendPort;
    int receivePort;
    
    // Connection state machine
    ConnectionState connectionState = ConnectionState::Disconnected;
    bool connected = false;  // Legacy compatibility
    
    // Request tracking
    juce::String currentRequestId;
    
    // Timing
    std::atomic<int64_t> lastPongTime { 0 };
    std::atomic<int64_t> lastPingSentTime { 0 };
    int reconnectDelayMs = InitialReconnectDelayMs;
    bool reconnectScheduled = false;
    
    juce::ListenerList<Listener> listeners;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(OSCBridge)
};
