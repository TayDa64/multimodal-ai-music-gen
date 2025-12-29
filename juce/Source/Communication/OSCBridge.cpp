/*
  ==============================================================================

    OSCBridge.cpp
    
    Implementation of OSC communication bridge.

  ==============================================================================
*/

#include "OSCBridge.h"

//==============================================================================
OSCBridge::OSCBridge(int receivePort_, int sendPort_, const juce::String& host_)
    : host(host_)
    , sendPort(sendPort_)
    , receivePort(receivePort_)
{
    receiver.addListener(this);
}

OSCBridge::~OSCBridge()
{
    stopTimer();
    disconnect();
    receiver.removeListener(this);
}

//==============================================================================
bool OSCBridge::connect()
{
    // Start listening for responses
    if (!receiver.connect(receivePort))
    {
        DBG("OSCBridge: Failed to listen on port " << receivePort);
        setConnectionState(ConnectionState::Error);
        return false;
    }
    
    // Connect sender
    if (!sender.connect(host, sendPort))
    {
        DBG("OSCBridge: Failed to connect sender to " << host << ":" << sendPort);
        receiver.disconnect();
        setConnectionState(ConnectionState::Error);
        return false;
    }
    
    DBG("OSCBridge: Connected - listening on " << receivePort << ", sending to " << host << ":" << sendPort);
    
    // Set state to connecting (waiting for pong)
    setConnectionState(ConnectionState::Connecting);
    
    // Send initial ping and start timer for heartbeat/timeout
    lastPingSentTime = juce::Time::currentTimeMillis();
    sendPing();
    
    // Start timer for ping/timeout monitoring
    startTimer(1000);  // Check every second
    
    return true;
}

void OSCBridge::disconnect()
{
    stopTimer();
    receiver.disconnect();
    sender.disconnect();
    currentRequestId.clear();
    resetReconnectBackoff();
    setConnectionState(ConnectionState::Disconnected);
}

//==============================================================================
void OSCBridge::sendGenerate(const GenerationRequest& request)
{
    // Ensure request has a unique ID for correlation
    GenerationRequest mutableRequest = request;
    if (mutableRequest.requestId.isEmpty())
        mutableRequest.generateRequestId();
    
    // Track current request
    currentRequestId = mutableRequest.requestId;
    
    DBG("OSCBridge: Sending generate with request_id: " << mutableRequest.requestId);
    
    // Update state to generating
    setConnectionState(ConnectionState::Generating);
    
    sendMessage(OSCAddresses::generate, mutableRequest.toJson());
}

void OSCBridge::sendCancel(const juce::String& taskId)
{
    setConnectionState(ConnectionState::Canceling);
    
    if (taskId.isNotEmpty())
        sendMessage(OSCAddresses::cancel, taskId);
    else
        sendMessage(OSCAddresses::cancel);
}

void OSCBridge::sendPing()
{
    lastPingSentTime = juce::Time::currentTimeMillis();
    sendMessage(OSCAddresses::ping);
}

void OSCBridge::sendShutdown()
{
    // Create shutdown request with request_id for acknowledgment
    juce::DynamicObject::Ptr obj = new juce::DynamicObject();
    juce::String shutdownRequestId = juce::Uuid().toString();
    obj->setProperty("request_id", shutdownRequestId);
    
    DBG("OSCBridge: Sending shutdown with request_id: " << shutdownRequestId);
    sendMessage(OSCAddresses::shutdown, juce::JSON::toString(juce::var(obj.get())));
}

void OSCBridge::sendGetInstruments(const juce::StringArray& paths, const juce::String& cacheDir)
{
    juce::DynamicObject::Ptr obj = new juce::DynamicObject();
    
    juce::Array<juce::var> pathsArray;
    for (const auto& path : paths)
        pathsArray.add(path);
    
    obj->setProperty("paths", pathsArray);
    
    if (cacheDir.isNotEmpty())
        obj->setProperty("cache_dir", cacheDir);
    
    sendMessage(OSCAddresses::getInstruments, juce::JSON::toString(juce::var(obj.get())));
}

//==============================================================================
void OSCBridge::addListener(Listener* listener)
{
    listeners.add(listener);
}

void OSCBridge::removeListener(Listener* listener)
{
    listeners.remove(listener);
}

//==============================================================================
void OSCBridge::oscMessageReceived(const juce::OSCMessage& message)
{
    auto address = message.getAddressPattern().toString();
    
    DBG("OSCBridge: Received " << address);
    
    if (address == OSCAddresses::progress)
        handleProgress(message);
    else if (address == OSCAddresses::complete)
        handleComplete(message);
    else if (address == OSCAddresses::error)
        handleError(message);
    else if (address == OSCAddresses::pong)
        handlePong(message);
    else if (address == OSCAddresses::status)
        handleStatus(message);
    else if (address == OSCAddresses::instrumentsLoaded)
        handleInstrumentsLoaded(message);
    else
        DBG("OSCBridge: Unknown address: " << address);
}

void OSCBridge::oscBundleReceived(const juce::OSCBundle& bundle)
{
    for (const auto& element : bundle)
    {
        if (element.isMessage())
            oscMessageReceived(element.getMessage());
        else if (element.isBundle())
            oscBundleReceived(element.getBundle());
    }
}

//==============================================================================
void OSCBridge::handleProgress(const juce::OSCMessage& message)
{
    if (message.isEmpty())
        return;
    
    auto jsonStr = message[0].getString();
    auto update = ProgressUpdate::fromJson(jsonStr);
    
    listeners.call([&](Listener& l)
    {
        l.onProgress(update.percent, update.step, update.message);
    });
}

void OSCBridge::handleComplete(const juce::OSCMessage& message)
{
    if (message.isEmpty())
        return;
    
    auto jsonStr = message[0].getString();
    auto result = GenerationResult::fromJson(jsonStr);
    
    // Clear current request and return to connected state
    currentRequestId.clear();
    setConnectionState(ConnectionState::Connected);
    
    listeners.call([&](Listener& l)
    {
        l.onGenerationComplete(result);
    });
}

void OSCBridge::handleError(const juce::OSCMessage& message)
{
    if (message.isEmpty())
        return;
    
    auto jsonStr = message[0].getString();
    auto error = ErrorResponse::fromJson(jsonStr);
    
    // If error is related to current generation, clear request and return to connected
    if (error.requestId == currentRequestId || currentRequestId.isEmpty())
    {
        currentRequestId.clear();
        setConnectionState(ConnectionState::Connected);
    }
    
    listeners.call([&](Listener& l)
    {
        l.onError(error.code, error.message);
    });
}

void OSCBridge::handlePong(const juce::OSCMessage& message)
{
    lastPongTime = juce::Time::currentTimeMillis();
    
    // Reset reconnect backoff on successful pong
    resetReconnectBackoff();
    
    // If we were connecting or disconnected, we're now connected
    if (connectionState == ConnectionState::Connecting ||
        connectionState == ConnectionState::Disconnected ||
        connectionState == ConnectionState::Error)
    {
        setConnectionState(ConnectionState::Connected);
    }
    
    DBG("OSCBridge: Received pong - server is alive");
}

void OSCBridge::handleStatus(const juce::OSCMessage& message)
{
    if (message.isEmpty())
        return;
    
    auto jsonStr = message[0].getString();
    DBG("OSCBridge: Status update: " << jsonStr);
}

void OSCBridge::handleInstrumentsLoaded(const juce::OSCMessage& message)
{
    if (message.isEmpty())
        return;
    
    auto jsonStr = message[0].getString();
    auto json = juce::JSON::parse(jsonStr);
    
    if (auto* obj = json.getDynamicObject())
    {
        int count = obj->getProperty("count");
        juce::StringPairArray categories;
        
        if (auto cats = obj->getProperty("categories"); cats.isObject())
        {
            if (auto* catsObj = cats.getDynamicObject())
            {
                for (const auto& prop : catsObj->getProperties())
                    categories.set(prop.name.toString(), juce::String((int)prop.value));
            }
        }
        
        listeners.call([&](Listener& l)
        {
            l.onInstrumentsLoaded(count, categories);
        });
    }
}

//==============================================================================
void OSCBridge::sendMessage(const juce::String& address, const juce::String& jsonPayload)
{
    if (!sender.send(address, jsonPayload))
    {
        DBG("OSCBridge: Failed to send message to " << address);
    }
    else
    {
        DBG("OSCBridge: Sent " << address);
    }
}

void OSCBridge::setConnectionState(ConnectionState newState)
{
    if (connectionState != newState)
    {
        auto oldState = connectionState;
        connectionState = newState;
        
        // Update legacy connected flag
        bool nowConnected = (newState == ConnectionState::Connected ||
                            newState == ConnectionState::Generating);
        bool wasConnected = (oldState == ConnectionState::Connected ||
                            oldState == ConnectionState::Generating);
        
        if (connected != nowConnected)
        {
            connected = nowConnected;
        }
        
        DBG("OSCBridge: State changed from " << connectionStateToString(oldState)
            << " to " << connectionStateToString(newState));
        
        // Notify listeners
        listeners.call([newState](Listener& l)
        {
            l.onConnectionStateChanged(newState);
        });
        
        // Also call legacy callback for backward compatibility
        if (wasConnected != nowConnected)
        {
            listeners.call([nowConnected](Listener& l)
            {
                l.onConnectionStatusChanged(nowConnected);
            });
        }
    }
}

void OSCBridge::timerCallback()
{
    auto now = juce::Time::currentTimeMillis();
    auto lastPong = lastPongTime.load();
    auto lastPing = lastPingSentTime.load();
    
    // Check for ping timeout
    if (connectionState == ConnectionState::Connecting)
    {
        // If we've been waiting too long for initial pong, connection failed
        if (now - lastPing > PingTimeoutMs)
        {
            DBG("OSCBridge: Ping timeout - server not responding");
            setConnectionState(ConnectionState::Disconnected);
            attemptReconnect();
            return;
        }
    }
    else if (connectionState == ConnectionState::Connected ||
             connectionState == ConnectionState::Generating)
    {
        // Check if we haven't received a pong recently
        if (lastPong > 0 && now - lastPong > PingTimeoutMs)
        {
            DBG("OSCBridge: Lost connection - no pong received for " << PingTimeoutMs << "ms");
            setConnectionState(ConnectionState::Disconnected);
            attemptReconnect();
            return;
        }
        
        // Send periodic ping to keep connection alive
        if (now - lastPing > PingIntervalMs)
        {
            lastPingSentTime = now;
            sendPing();
        }
    }
    else if (connectionState == ConnectionState::Disconnected && reconnectScheduled)
    {
        // Attempt reconnect after backoff delay
        reconnectScheduled = false;
        
        DBG("OSCBridge: Attempting reconnect after " << reconnectDelayMs << "ms backoff");
        
        // Increase backoff for next time (exponential backoff)
        reconnectDelayMs = juce::jmin(reconnectDelayMs * 2, MaxReconnectBackoffMs);
        
        // Try to reconnect
        receiver.disconnect();
        sender.disconnect();
        
        if (receiver.connect(receivePort) && sender.connect(host, sendPort))
        {
            setConnectionState(ConnectionState::Connecting);
            lastPingSentTime = juce::Time::currentTimeMillis();
            sendPing();
        }
        else
        {
            // Schedule another reconnect attempt
            attemptReconnect();
        }
    }
}

void OSCBridge::attemptReconnect()
{
    if (!reconnectScheduled)
    {
        reconnectScheduled = true;
        DBG("OSCBridge: Scheduling reconnect in " << reconnectDelayMs << "ms");
    }
}

void OSCBridge::resetReconnectBackoff()
{
    reconnectDelayMs = InitialReconnectDelayMs;
    reconnectScheduled = false;
}
