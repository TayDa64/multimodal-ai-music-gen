/*
  ==============================================================================

    OSCBridge.h
    
    OSC communication bridge for Python backend.

  ==============================================================================
*/

#pragma once

#include <JuceHeader.h>
#include "Messages.h"

//==============================================================================
/**
    OSC communication bridge for connecting to Python backend.
    
    Handles:
    - Sending generation requests
    - Receiving progress updates
    - Connection management
*/
class OSCBridge : public juce::OSCReceiver::Listener<juce::OSCReceiver::MessageLoopCallback>
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
        
        virtual void onConnectionStatusChanged(bool connected) {}
        virtual void onProgress(float percent, const juce::String& step, const juce::String& message) {}
        virtual void onGenerationComplete(const GenerationResult& result) {}
        virtual void onError(int code, const juce::String& message) {}
        virtual void onInstrumentsLoaded(int count, const juce::StringPairArray& categories) {}
    };
    
    //==============================================================================
    OSCBridge(int receivePort = 9001, int sendPort = 9000, 
              const juce::String& host = "127.0.0.1");
    ~OSCBridge() override;
    
    //==============================================================================
    // Connection management
    bool connect();
    void disconnect();
    bool isConnected() const { return connected; }
    
    //==============================================================================
    // Outgoing messages
    void sendGenerate(const GenerationRequest& request);
    void sendCancel(const juce::String& taskId = {});
    void sendPing();
    void sendShutdown();
    void sendGetInstruments(const juce::StringArray& paths, const juce::String& cacheDir = {});
    
    //==============================================================================
    // Listeners
    void addListener(Listener* listener);
    void removeListener(Listener* listener);
    
private:
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
    
    //==============================================================================
    void sendMessage(const juce::String& address, const juce::String& jsonPayload = {});
    void setConnected(bool isConnected);
    
    //==============================================================================
    juce::OSCReceiver receiver;
    juce::OSCSender sender;
    
    juce::String host;
    int sendPort;
    int receivePort;
    
    bool connected = false;
    std::atomic<int64_t> lastPongTime { 0 };
    
    juce::ListenerList<Listener> listeners;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(OSCBridge)
};
