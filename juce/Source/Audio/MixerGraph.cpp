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

        // Create IO nodes
        audioInputNodeID = mainGraph->addNode(std::make_unique<juce::AudioProcessorGraph::AudioGraphIOProcessor>(juce::AudioProcessorGraph::AudioGraphIOProcessor::audioInputNode))->nodeID;
        audioOutputNodeID = mainGraph->addNode(std::make_unique<juce::AudioProcessorGraph::AudioGraphIOProcessor>(juce::AudioProcessorGraph::AudioGraphIOProcessor::audioOutputNode))->nodeID;
        midiInputNodeID = mainGraph->addNode(std::make_unique<juce::AudioProcessorGraph::AudioGraphIOProcessor>(juce::AudioProcessorGraph::AudioGraphIOProcessor::midiInputNode))->nodeID;
        midiOutputNodeID = mainGraph->addNode(std::make_unique<juce::AudioProcessorGraph::AudioGraphIOProcessor>(juce::AudioProcessorGraph::AudioGraphIOProcessor::midiOutputNode))->nodeID;

        // Create Master Bus
        auto masterGain = std::make_unique<GainProcessor>();
        masterGainNodeID = mainGraph->addNode(std::move(masterGain))->nodeID;

        // Connect Master to Output
        for (int channel = 0; channel < 2; ++channel)
        {
            mainGraph->addConnection({ { masterGainNodeID, channel }, { audioOutputNodeID, channel } });
        }
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
}
