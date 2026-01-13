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
    isRequestAcknowledged = false;
    generationStartTime = juce::Time::currentTimeMillis();
    lastMessageReceivedTime = generationStartTime.load();
    
    DBG("OSCBridge: Sending generate with request_id: " << mutableRequest.requestId);
    
    // Update state to generating
    setConnectionState(ConnectionState::Generating);
    
    sendMessage(OSCAddresses::generate, mutableRequest.toJson());
}

void OSCBridge::sendRegenerate(const RegenerationRequest& request)
{
    // Ensure request has a unique ID for correlation
    RegenerationRequest mutableRequest = request;
    if (mutableRequest.requestId.isEmpty())
        mutableRequest.generateRequestId();
    
    // Track current request (uses same field as generate)
    currentRequestId = mutableRequest.requestId;
    isRequestAcknowledged = false;
    generationStartTime = juce::Time::currentTimeMillis();
    lastMessageReceivedTime = generationStartTime.load();
    
    DBG("OSCBridge: Sending regenerate with request_id: " << mutableRequest.requestId
        << ", bars " << mutableRequest.startBar << "-" << mutableRequest.endBar);
    
    // Update state to generating
    setConnectionState(ConnectionState::Generating);
    
    sendMessage(OSCAddresses::regenerate, mutableRequest.toJson());
}

void OSCBridge::sendControlsSet(const juce::var& overrides)
{
    juce::DynamicObject::Ptr obj = new juce::DynamicObject();
    obj->setProperty("request_id", juce::Uuid().toString());
    obj->setProperty("schema_version", SCHEMA_VERSION);
    obj->setProperty("overrides", overrides);

    DBG("OSCBridge: Sending controls/set");
    sendMessage(OSCAddresses::controlsSet, juce::JSON::toString(juce::var(obj.get()), true));
}

void OSCBridge::sendControlsClear(const juce::StringArray& keys)
{
    juce::DynamicObject::Ptr obj = new juce::DynamicObject();
    obj->setProperty("request_id", juce::Uuid().toString());
    obj->setProperty("schema_version", SCHEMA_VERSION);

    if (!keys.isEmpty())
    {
        juce::Array<juce::var> keysArray;
        for (const auto& key : keys)
            keysArray.add(key);
        obj->setProperty("keys", keysArray);
    }

    DBG("OSCBridge: Sending controls/clear");
    sendMessage(OSCAddresses::controlsClear, juce::JSON::toString(juce::var(obj.get()), true));
}

void OSCBridge::sendAnalyzeFile(const juce::File& file, bool verbose)
{
    if (!file.existsAsFile())
    {
        DBG("OSCBridge: Analyze file does not exist: " << file.getFullPathName());
        return;
    }

    AnalyzeRequest request;
    request.generateRequestId();
    request.path = file.getFullPathName();
    request.verbose = verbose;

    currentAnalyzeRequestId = request.requestId;

    DBG("OSCBridge: Sending analyze (file) with request_id: " << request.requestId);
    sendMessage(OSCAddresses::analyze, request.toJson());
}

void OSCBridge::sendAnalyzeUrl(const juce::String& url, bool verbose)
{
    if (url.isEmpty())
        return;

    AnalyzeRequest request;
    request.generateRequestId();
    request.url = url;
    request.verbose = verbose;

    currentAnalyzeRequestId = request.requestId;

    DBG("OSCBridge: Sending analyze (url) with request_id: " << request.requestId);
    sendMessage(OSCAddresses::analyze, request.toJson());
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

void OSCBridge::sendFXChain(const juce::String& fxChainJson)
{
    // Send FX chain configuration to Python backend for offline render parity
    // The server will store this and apply it during the next generation
    juce::DynamicObject::Ptr obj = new juce::DynamicObject();
    obj->setProperty("schema_version", SCHEMA_VERSION);
    obj->setProperty("fx_chain", juce::JSON::parse(fxChainJson));
    
    DBG("OSCBridge: Sending FX chain configuration");
    sendMessage(OSCAddresses::fxChain, juce::JSON::toString(juce::var(obj.get())));
}

//==============================================================================
// Expansion management
//==============================================================================

void OSCBridge::sendExpansionList()
{
    sendMessage(OSCAddresses::expansionList);
}

void OSCBridge::sendExpansionInstruments(const juce::String& expansionId)
{
    juce::DynamicObject::Ptr obj = new juce::DynamicObject();
    obj->setProperty("expansion_id", expansionId);
    sendMessage(OSCAddresses::expansionInstruments, juce::JSON::toString(juce::var(obj.get())));
}

void OSCBridge::sendExpansionResolve(const juce::String& instrument, const juce::String& genre)
{
    juce::DynamicObject::Ptr obj = new juce::DynamicObject();
    obj->setProperty("instrument", instrument);
    obj->setProperty("genre", genre);
    sendMessage(OSCAddresses::expansionResolve, juce::JSON::toString(juce::var(obj.get())));
}

void OSCBridge::sendExpansionImport(const juce::String& path)
{
    juce::DynamicObject::Ptr obj = new juce::DynamicObject();
    obj->setProperty("path", path);
    sendMessage(OSCAddresses::expansionImport, juce::JSON::toString(juce::var(obj.get())));
}

void OSCBridge::sendExpansionScan(const juce::String& directory)
{
    juce::DynamicObject::Ptr obj = new juce::DynamicObject();
    obj->setProperty("directory", directory);
    sendMessage(OSCAddresses::expansionScan, juce::JSON::toString(juce::var(obj.get())));
}

void OSCBridge::sendExpansionEnable(const juce::String& expansionId, bool enabled)
{
    juce::DynamicObject::Ptr obj = new juce::DynamicObject();
    obj->setProperty("expansion_id", expansionId);
    obj->setProperty("enabled", enabled);
    sendMessage(OSCAddresses::expansionEnable, juce::JSON::toString(juce::var(obj.get())));
}

//==============================================================================
// Take management
//==============================================================================

void OSCBridge::sendSelectTake(const juce::String& track, const juce::String& takeId)
{
    TakeSelectRequest request;
    request.generateRequestId();
    request.track = track;
    request.takeId = takeId;
    
    DBG("OSCBridge: Sending select take - track: " << track << ", take: " << takeId);
    sendMessage(OSCAddresses::selectTake, request.toJson());
}

void OSCBridge::sendCompTakes(const TakeCompRequest& request)
{
    TakeCompRequest mutableRequest = request;
    if (mutableRequest.requestId.isEmpty())
        mutableRequest.generateRequestId();
    
    DBG("OSCBridge: Sending comp takes - track: " << request.track 
        << ", regions: " << request.regions.size());
    sendMessage(OSCAddresses::compTakes, mutableRequest.toJson());
}

void OSCBridge::sendRenderTake(const TakeRenderRequest& request)
{
    TakeRenderRequest mutableRequest = request;
    if (mutableRequest.requestId.isEmpty())
        mutableRequest.generateRequestId();
    
    DBG("OSCBridge: Sending render take - track: " << request.track 
        << ", take: " << (request.useComp ? "comp" : request.takeId));
    sendMessage(OSCAddresses::renderTake, mutableRequest.toJson());
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
    lastMessageReceivedTime = juce::Time::currentTimeMillis();
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
    else if (address == OSCAddresses::analyzeResult)
        handleAnalyzeResult(message);
    // Expansion responses
    else if (address == OSCAddresses::expansionListResponse)
        handleExpansionList(message);
    else if (address == OSCAddresses::expansionInstrumentsResponse)
        handleExpansionInstruments(message);
    else if (address == OSCAddresses::expansionResolveResponse)
        handleExpansionResolve(message);
    // Take responses
    else if (address == OSCAddresses::takesAvailable)
        handleTakesAvailable(message);
    else if (address == OSCAddresses::takeSelected)
        handleTakeSelected(message);
    else if (address == OSCAddresses::takeRendered)
        handleTakeRendered(message);
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
    
    // Validate request ID if we are tracking one
    if (currentRequestId.isNotEmpty() && update.requestId.isNotEmpty() && update.requestId != currentRequestId)
    {
        DBG("OSCBridge: Ignoring progress for unknown request ID: " << update.requestId);
        return;
    }
    
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
    
    // Protocol hardening: Validate request_id correlation
    if (currentRequestId.isNotEmpty() && result.requestId.isNotEmpty() && result.requestId != currentRequestId)
    {
        DBG("OSCBridge: Ignoring /complete for mismatched request ID: " << result.requestId << " (expected: " << currentRequestId << ")");
        return;
    }
    
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

    // If error is related to analyze request, just clear that request id
    if (error.requestId == currentAnalyzeRequestId)
    {
        currentAnalyzeRequestId.clear();

        listeners.call([&](Listener& l)
        {
            l.onAnalyzeError(error.code, error.message);
        });
        return;
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
    
    auto json = juce::JSON::parse(jsonStr);
    if (auto* obj = json.getDynamicObject())
    {
        juce::String status = obj->getProperty("status");
        juce::String reqId = obj->getProperty("request_id");
        
        if (status == "generation_started")
        {
            if (reqId == currentRequestId)
            {
                isRequestAcknowledged = true;
                DBG("OSCBridge: Generation request acknowledged");
            }
        }
        else if (status == "cancelled")
        {
            // Handle cancel acknowledgment
            if (reqId == currentRequestId || currentRequestId.isEmpty())
            {
                currentRequestId.clear();
                setConnectionState(ConnectionState::Connected);
                DBG("OSCBridge: Cancellation confirmed");
            }
        }
        else if (status == "schema_version_warning")
        {
            // Surface schema version mismatch to UI
            int clientVersion = obj->getProperty("client_version");
            int serverVersion = obj->getProperty("server_version");
            juce::String warningMsg = obj->getProperty("message");
            
            DBG("OSCBridge: Schema version warning - " << warningMsg);
            
            // Notify listeners about the schema mismatch (non-blocking warning)
            listeners.call([clientVersion, serverVersion, warningMsg](Listener& l)
            {
                l.onSchemaVersionWarning(clientVersion, serverVersion, warningMsg);
            });
        }
    }
}

void OSCBridge::handleInstrumentsLoaded(const juce::OSCMessage& message)
{
    if (message.isEmpty())
        return;
    
    auto jsonStr = message[0].getString();
    
    listeners.call([&](Listener& l)
    {
        l.onInstrumentsLoaded(jsonStr);
    });
}

//==============================================================================
// Analyze handlers
//==============================================================================

void OSCBridge::handleAnalyzeResult(const juce::OSCMessage& message)
{
    if (message.isEmpty())
        return;

    auto jsonStr = message[0].getString();
    auto result = AnalyzeResult::fromJson(jsonStr);

    if (result.requestId == currentAnalyzeRequestId)
        currentAnalyzeRequestId.clear();

    listeners.call([&](Listener& l)
    {
        l.onAnalyzeResultReceived(result);
    });
}

//==============================================================================
// Expansion handlers
//==============================================================================

void OSCBridge::handleExpansionList(const juce::OSCMessage& message)
{
    if (message.isEmpty())
        return;
    
    auto jsonStr = message[0].getString();
    DBG("OSCBridge: Received expansion list response");
    
    listeners.call([&](Listener& l)
    {
        l.onExpansionListReceived(jsonStr);
    });
}

void OSCBridge::handleExpansionInstruments(const juce::OSCMessage& message)
{
    if (message.isEmpty())
        return;
    
    auto jsonStr = message[0].getString();
    DBG("OSCBridge: Received expansion instruments response");
    
    listeners.call([&](Listener& l)
    {
        l.onExpansionInstrumentsReceived(jsonStr);
    });
}

void OSCBridge::handleExpansionResolve(const juce::OSCMessage& message)
{
    if (message.isEmpty())
        return;
    
    auto jsonStr = message[0].getString();
    DBG("OSCBridge: Received expansion resolve response");
    
    listeners.call([&](Listener& l)
    {
        l.onExpansionResolveReceived(jsonStr);
    });
}

//==============================================================================
// Take handlers
//==============================================================================

void OSCBridge::handleTakesAvailable(const juce::OSCMessage& message)
{
    if (message.isEmpty())
        return;
    
    auto jsonStr = message[0].getString();
    DBG("OSCBridge: Received takes available response");
    
    listeners.call([&](Listener& l)
    {
        l.onTakesAvailable(jsonStr);
    });
}

void OSCBridge::handleTakeSelected(const juce::OSCMessage& message)
{
    if (message.isEmpty())
        return;
    
    auto jsonStr = message[0].getString();
    DBG("OSCBridge: Received take selected response");
    
    auto json = juce::JSON::parse(jsonStr);
    if (auto* obj = json.getDynamicObject())
    {
        juce::String track = obj->getProperty("track");
        juce::String takeId = obj->getProperty("take_id");
        
        listeners.call([track, takeId](Listener& l)
        {
            l.onTakeSelected(track, takeId);
        });
    }
}

void OSCBridge::handleTakeRendered(const juce::OSCMessage& message)
{
    if (message.isEmpty())
        return;
    
    auto jsonStr = message[0].getString();
    DBG("OSCBridge: Received take rendered response");
    
    auto json = juce::JSON::parse(jsonStr);
    if (auto* obj = json.getDynamicObject())
    {
        juce::String track = obj->getProperty("track");
        juce::String outputPath = obj->getProperty("output_path");
        
        listeners.call([track, outputPath](Listener& l)
        {
            l.onTakeRendered(track, outputPath);
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
    else if (connectionState == ConnectionState::Generating)
    {
        // Check for generation timeouts
        
        // 1. Acknowledgment timeout (server didn't say "started")
        if (!isRequestAcknowledged && (now - generationStartTime > RequestAckTimeoutMs))
        {
            DBG("OSCBridge: Generation request timed out (no ack)");
            
            // Notify error
            listeners.call([&](Listener& l)
            {
                l.onError(201, "Server failed to acknowledge generation request");
            });
            
            currentRequestId.clear();
            setConnectionState(ConnectionState::Connected); // Revert to connected
            return;
        }
        
        // 2. Activity timeout (no progress/status updates for too long)
        if (now - lastMessageReceivedTime > ActivityTimeoutMs)
        {
            DBG("OSCBridge: Generation timed out (no activity)");
            
            listeners.call([&](Listener& l)
            {
                l.onError(201, "Generation timed out (server stopped responding)");
            });
            
            currentRequestId.clear();
            setConnectionState(ConnectionState::Connected);
            return;
        }
        
        // Send periodic ping to keep connection alive
        if (now - lastPing > PingIntervalMs)
        {
            lastPingSentTime = now;
            sendPing();
        }
    }
    else if (connectionState == ConnectionState::Connected)
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
