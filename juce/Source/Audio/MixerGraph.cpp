#include "MixerGraph.h"

namespace Audio
{
    MixerGraph::MixerGraph()
        : AudioProcessor(BusesProperties().withInput("Input", juce::AudioChannelSet::stereo(), true)
                                          .withOutput("Output", juce::AudioChannelSet::stereo(), true))
    {
        mainGraph = std::make_unique<juce::AudioProcessorGraph>();
        initializeGraph();
    }

    MixerGraph::~MixerGraph()
    {
        mainGraph = nullptr;
    }

    void MixerGraph::initializeGraph()
    {
        mainGraph->clear();
        fxChains.clear();

        // Create IO nodes
        audioInputNodeID = mainGraph->addNode(std::make_unique<juce::AudioProcessorGraph::AudioGraphIOProcessor>(juce::AudioProcessorGraph::AudioGraphIOProcessor::audioInputNode))->nodeID;
        audioOutputNodeID = mainGraph->addNode(std::make_unique<juce::AudioProcessorGraph::AudioGraphIOProcessor>(juce::AudioProcessorGraph::AudioGraphIOProcessor::audioOutputNode))->nodeID;
        midiInputNodeID = mainGraph->addNode(std::make_unique<juce::AudioProcessorGraph::AudioGraphIOProcessor>(juce::AudioProcessorGraph::AudioGraphIOProcessor::midiInputNode))->nodeID;
        midiOutputNodeID = mainGraph->addNode(std::make_unique<juce::AudioProcessorGraph::AudioGraphIOProcessor>(juce::AudioProcessorGraph::AudioGraphIOProcessor::midiOutputNode))->nodeID;

        // Create Master Bus
        auto masterGain = std::make_unique<GainProcessor>();
        masterGainNodeID = mainGraph->addNode(std::move(masterGain))->nodeID;
        
        // Apply default master volume boost (+9dB) to compensate for quiet samples
        if (auto* node = mainGraph->getNodeForId(masterGainNodeID))
        {
            if (auto* gainProc = dynamic_cast<GainProcessor*>(node->getProcessor()))
            {
                gainProc->setGainDecibels(9.0f);
                DBG("MixerGraph: Master gain set to +9dB");
            }
        }

        // Connect Input -> Master Gain -> Output (direct passthrough by default)
        for (int channel = 0; channel < 2; ++channel)
        {
            // Input to Master Gain (THIS WAS MISSING!)
            mainGraph->addConnection({ { audioInputNodeID, channel }, { masterGainNodeID, channel } });
            // Master Gain to Output
            mainGraph->addConnection({ { masterGainNodeID, channel }, { audioOutputNodeID, channel } });
        }
        
        DBG("MixerGraph: Initialized with Input -> MasterGain -> Output routing (+9dB boost)");
    }

    void MixerGraph::prepareToPlay(double sampleRate, int samplesPerBlock)
    {
        mainGraph->setPlayConfigDetails(getTotalNumInputChannels(),
                                        getTotalNumOutputChannels(),
                                        sampleRate, samplesPerBlock);
        mainGraph->prepareToPlay(sampleRate, samplesPerBlock);
    }

    void MixerGraph::releaseResources()
    {
        mainGraph->releaseResources();
    }

    void MixerGraph::processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer& midiMessages)
    {
        mainGraph->processBlock(buffer, midiMessages);
    }

    juce::AudioProcessorGraph::NodeID MixerGraph::addTrack(const juce::String& trackName)
    {
        // Create processors for the track strip
        auto gain = std::make_unique<GainProcessor>();
        auto pan = std::make_unique<PanProcessor>();

        auto gainNode = mainGraph->addNode(std::move(gain));
        auto panNode = mainGraph->addNode(std::move(pan));

        // Connect Gain -> Pan
        for (int channel = 0; channel < 2; ++channel)
        {
            mainGraph->addConnection({ { gainNode->nodeID, channel }, { panNode->nodeID, channel } });
        }

        // Connect Pan -> Master
        for (int channel = 0; channel < 2; ++channel)
        {
            mainGraph->addConnection({ { panNode->nodeID, channel }, { masterGainNodeID, channel } });
        }

        // Return the input node ID (Gain) so sources can connect to it
        return gainNode->nodeID;
    }

    void MixerGraph::clearTracks()
    {
        // Remove all nodes except IO and Master
        // Note: Iterating and removing is tricky, so we'll just re-initialize
        initializeGraph();
    }
    
    //==============================================================================
    // FX Chain Management
    
    std::unique_ptr<juce::AudioProcessor> MixerGraph::createProcessor(const juce::String& type)
    {
        auto lowerType = type.toLowerCase();
        
        if (lowerType == "eq" || lowerType == "equalizer")
            return std::make_unique<EQProcessor>();
        if (lowerType == "compressor" || lowerType == "comp")
            return std::make_unique<CompressorProcessor>();
        if (lowerType == "reverb" || lowerType == "rev")
            return std::make_unique<ReverbProcessor>();
        if (lowerType == "delay")
            return std::make_unique<DelayProcessor>();
        if (lowerType == "saturation" || lowerType == "sat" || lowerType == "tape")
            return std::make_unique<SaturationProcessor>();
        if (lowerType == "limiter" || lowerType == "lim")
            return std::make_unique<LimiterProcessor>();
        if (lowerType == "gain")
            return std::make_unique<GainProcessor>();
        if (lowerType == "pan")
            return std::make_unique<PanProcessor>();
            
        DBG("MixerGraph: Unknown processor type: " << type);
        return nullptr;
    }
    
    void MixerGraph::setFXChainForBus(const juce::String& bus, const juce::var& chainJson)
    {
        // Clear existing FX for this bus
        clearFXForBus(bus);
        
        auto* chainArray = chainJson.getArray();
        if (chainArray == nullptr)
            return;
            
        std::vector<FXNodeInfo> newChain;
        
        for (const auto& fxVar : *chainArray)
        {
            juce::String fxId = fxVar.getProperty("id", "").toString();
            juce::String fxType = fxVar.getProperty("type", "").toString();
            bool enabled = fxVar.getProperty("enabled", true);
            
            if (fxType.isEmpty())
                continue;
                
            auto processor = createProcessor(fxType);
            if (processor == nullptr)
                continue;
                
            // Apply parameters
            if (auto* paramsObj = fxVar.getProperty("parameters", juce::var()).getDynamicObject())
            {
                for (const auto& prop : paramsObj->getProperties())
                {
                    juce::String paramName = prop.name.toString();
                    float value = static_cast<float>(prop.value);
                    
                    // Apply parameter based on processor type
                    if (auto* eq = dynamic_cast<EQProcessor*>(processor.get()))
                    {
                        if (paramName == "low_gain") eq->setLowGain(value);
                        else if (paramName == "mid_gain") eq->setMidGain(value);
                        else if (paramName == "high_gain") eq->setHighGain(value);
                    }
                    else if (auto* comp = dynamic_cast<CompressorProcessor*>(processor.get()))
                    {
                        if (paramName == "threshold") comp->setThreshold(value);
                        else if (paramName == "ratio") comp->setRatio(value);
                        else if (paramName == "attack") comp->setAttack(value);
                        else if (paramName == "release") comp->setRelease(value);
                    }
                    else if (auto* reverb = dynamic_cast<ReverbProcessor*>(processor.get()))
                    {
                        if (paramName == "room_size") reverb->setRoomSize(value);
                        else if (paramName == "damping") reverb->setDamping(value);
                        else if (paramName == "wet") reverb->setWetLevel(value);
                        else if (paramName == "dry") reverb->setDryLevel(value);
                        else if (paramName == "width") reverb->setWidth(value);
                    }
                    else if (auto* delay = dynamic_cast<DelayProcessor*>(processor.get()))
                    {
                        if (paramName == "time" || paramName == "delay_time") delay->setDelayTime(value);
                        else if (paramName == "feedback") delay->setFeedback(value);
                        else if (paramName == "wet") delay->setWetLevel(value);
                        else if (paramName == "dry") delay->setDryLevel(value);
                    }
                    else if (auto* sat = dynamic_cast<SaturationProcessor*>(processor.get()))
                    {
                        if (paramName == "drive") sat->setDrive(value);
                        else if (paramName == "mix") sat->setMix(value);
                    }
                    else if (auto* lim = dynamic_cast<LimiterProcessor*>(processor.get()))
                    {
                        if (paramName == "threshold") lim->setThreshold(value);
                        else if (paramName == "release") lim->setRelease(value);
                    }
                    else if (auto* gain = dynamic_cast<GainProcessor*>(processor.get()))
                    {
                        if (paramName == "gain") gain->setGainDecibels(value);
                    }
                }
            }
            
            // Add node to graph
            auto node = mainGraph->addNode(std::move(processor));
            
            FXNodeInfo info;
            info.id = fxId.isEmpty() ? juce::Uuid().toString() : fxId;
            info.type = fxType;
            info.nodeId = node->nodeID;
            info.enabled = enabled;
            
            newChain.push_back(info);
        }
        
        fxChains[bus] = std::move(newChain);
        reconnectFXChain(bus);
        
        DBG("MixerGraph: Set FX chain for bus '" << bus << "' with " << fxChains[bus].size() << " effects");
    }
    
    void MixerGraph::clearFXForBus(const juce::String& bus)
    {
        auto it = fxChains.find(bus);
        if (it == fxChains.end())
            return;
            
        // Remove all FX nodes for this bus
        for (const auto& fxInfo : it->second)
        {
            mainGraph->removeNode(fxInfo.nodeId);
        }
        
        fxChains.erase(it);
    }
    
    void MixerGraph::reconnectFXChain(const juce::String& bus)
    {
        auto it = fxChains.find(bus);
        if (it == fxChains.end() || it->second.empty())
            return;
            
        const auto& chain = it->second;
        
        // For master bus, connect: Input -> FX chain -> MasterGain -> Output
        if (bus == "master")
        {
            // Remove existing connections to masterGainNodeID input
            for (auto& connection : mainGraph->getConnections())
            {
                if (connection.destination.nodeID == masterGainNodeID)
                {
                    mainGraph->removeConnection(connection);
                }
            }
            
            // Connect FX chain in series
            for (size_t i = 0; i < chain.size() - 1; ++i)
            {
                for (int channel = 0; channel < 2; ++channel)
                {
                    mainGraph->addConnection({ 
                        { chain[i].nodeId, channel }, 
                        { chain[i + 1].nodeId, channel } 
                    });
                }
            }
            
            // Connect last FX to master gain
            for (int channel = 0; channel < 2; ++channel)
            {
                mainGraph->addConnection({ 
                    { chain.back().nodeId, channel }, 
                    { masterGainNodeID, channel } 
                });
            }
            
            // Note: Input connection to first FX should come from track outputs
        }
    }
    
    void MixerGraph::setFXParameter(const juce::String& fxId, const juce::String& paramName, float value)
    {
        // Find the FX node
        for (auto& [bus, chain] : fxChains)
        {
            for (const auto& fxInfo : chain)
            {
                if (fxInfo.id == fxId)
                {
                    auto* node = mainGraph->getNodeForId(fxInfo.nodeId);
                    if (node == nullptr)
                        return;
                        
                    auto* processor = node->getProcessor();
                    
                    if (auto* eq = dynamic_cast<EQProcessor*>(processor))
                    {
                        if (paramName == "low_gain") eq->setLowGain(value);
                        else if (paramName == "mid_gain") eq->setMidGain(value);
                        else if (paramName == "high_gain") eq->setHighGain(value);
                    }
                    else if (auto* comp = dynamic_cast<CompressorProcessor*>(processor))
                    {
                        if (paramName == "threshold") comp->setThreshold(value);
                        else if (paramName == "ratio") comp->setRatio(value);
                        else if (paramName == "attack") comp->setAttack(value);
                        else if (paramName == "release") comp->setRelease(value);
                    }
                    else if (auto* reverb = dynamic_cast<ReverbProcessor*>(processor))
                    {
                        if (paramName == "room_size") reverb->setRoomSize(value);
                        else if (paramName == "damping") reverb->setDamping(value);
                        else if (paramName == "wet") reverb->setWetLevel(value);
                        else if (paramName == "dry") reverb->setDryLevel(value);
                    }
                    else if (auto* delay = dynamic_cast<DelayProcessor*>(processor))
                    {
                        if (paramName == "time") delay->setDelayTime(value);
                        else if (paramName == "feedback") delay->setFeedback(value);
                        else if (paramName == "wet") delay->setWetLevel(value);
                        else if (paramName == "dry") delay->setDryLevel(value);
                    }
                    else if (auto* sat = dynamic_cast<SaturationProcessor*>(processor))
                    {
                        if (paramName == "drive") sat->setDrive(value);
                        else if (paramName == "mix") sat->setMix(value);
                    }
                    else if (auto* lim = dynamic_cast<LimiterProcessor*>(processor))
                    {
                        if (paramName == "threshold") lim->setThreshold(value);
                        else if (paramName == "release") lim->setRelease(value);
                    }
                    
                    return;
                }
            }
        }
    }
    
    void MixerGraph::setFXEnabled(const juce::String& fxId, bool enabled)
    {
        for (auto& [bus, chain] : fxChains)
        {
            for (auto& fxInfo : chain)
            {
                if (fxInfo.id == fxId)
                {
                    fxInfo.enabled = enabled;
                    
                    auto* node = mainGraph->getNodeForId(fxInfo.nodeId);
                    if (node != nullptr)
                    {
                        auto* processor = node->getProcessor();
                        
                        // Set enabled state on processor if it supports it
                        if (auto* eq = dynamic_cast<EQProcessor*>(processor))
                            eq->setEnabled(enabled);
                        else if (auto* comp = dynamic_cast<CompressorProcessor*>(processor))
                            comp->setEnabled(enabled);
                        else if (auto* reverb = dynamic_cast<ReverbProcessor*>(processor))
                            reverb->setEnabled(enabled);
                        else if (auto* delay = dynamic_cast<DelayProcessor*>(processor))
                            delay->setEnabled(enabled);
                        else if (auto* sat = dynamic_cast<SaturationProcessor*>(processor))
                            sat->setEnabled(enabled);
                        else if (auto* lim = dynamic_cast<LimiterProcessor*>(processor))
                            lim->setEnabled(enabled);
                    }
                    return;
                }
            }
        }
    }
}
