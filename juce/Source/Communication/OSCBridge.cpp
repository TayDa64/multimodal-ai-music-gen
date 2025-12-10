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
        setConnected(false);
        return false;
    }
    
    // Connect sender
    if (!sender.connect(host, sendPort))
    {
        DBG("OSCBridge: Failed to connect sender to " << host << ":" << sendPort);
        receiver.disconnect();
        setConnected(false);
        return false;
    }
    
    DBG("OSCBridge: Connected - listening on " << receivePort << ", sending to " << host << ":" << sendPort);
    
    // Send ping to verify server is running
    sendPing();
    
    return true;
}

void OSCBridge::disconnect()
{
    receiver.disconnect();
    sender.disconnect();
    setConnected(false);
}

//==============================================================================
void OSCBridge::sendGenerate(const GenerationRequest& request)
{
    sendMessage(OSCAddresses::generate, request.toJson());
}

void OSCBridge::sendCancel(const juce::String& taskId)
{
    if (taskId.isNotEmpty())
        sendMessage(OSCAddresses::cancel, taskId);
    else
        sendMessage(OSCAddresses::cancel);
}

void OSCBridge::sendPing()
{
    sendMessage(OSCAddresses::ping);
}

void OSCBridge::sendShutdown()
{
    sendMessage(OSCAddresses::shutdown);
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
    
    listeners.call([&](Listener& l)
    {
        l.onError(error.code, error.message);
    });
}

void OSCBridge::handlePong(const juce::OSCMessage& message)
{
    lastPongTime = juce::Time::currentTimeMillis();
    setConnected(true);
    
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

void OSCBridge::setConnected(bool isConnected)
{
    if (connected != isConnected)
    {
        connected = isConnected;
        
        listeners.call([isConnected](Listener& l)
        {
            l.onConnectionStatusChanged(isConnected);
        });
    }
}
