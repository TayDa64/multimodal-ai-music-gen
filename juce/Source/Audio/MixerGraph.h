#pragma once

#include <juce_core/juce_core.h>
#include <juce_audio_basics/juce_audio_basics.h>
#include <juce_audio_processors/juce_audio_processors.h>
#include "Processors/GainProcessor.h"
#include "Processors/PanProcessor.h"
#include "Processors/EQProcessor.h"
#include "Processors/CompressorProcessor.h"
#include "Processors/ReverbProcessor.h"
#include "Processors/DelayProcessor.h"
#include "Processors/SaturationProcessor.h"
#include "Processors/LimiterProcessor.h"

namespace Audio
{
    /**
     * FX unit info for chain management.
     */
    struct FXNodeInfo
    {
        juce::String id;
        juce::String type;
        juce::AudioProcessorGraph::NodeID nodeId;
        bool enabled = true;
    };

    /**
     * Manages the AudioProcessorGraph for the project.
     * Handles routing, track creation, and master bus processing.
     */
    class MixerGraph : public juce::AudioProcessor
    {
    public:
        MixerGraph();
        ~MixerGraph() override;

        //==============================================================================
        void prepareToPlay(double sampleRate, int samplesPerBlock) override;
        void releaseResources() override;
        void processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer& midiMessages) override;

        //==============================================================================
        bool hasEditor() const override { return false; }
        juce::AudioProcessorEditor* createEditor() override { return nullptr; }
        const juce::String getName() const override { return "MixerGraph"; }

        bool acceptsMidi() const override { return true; }
        bool producesMidi() const override { return true; }
        bool isMidiEffect() const override { return false; }
        double getTailLengthSeconds() const override { return 0.0; }

        //==============================================================================
        int getNumPrograms() override { return 1; }
        int getCurrentProgram() override { return 0; }
        void setCurrentProgram(int index) override {}
        const juce::String getProgramName(int index) override { return {}; }
        void changeProgramName(int index, const juce::String& newName) override {}

        //==============================================================================
        void getStateInformation(juce::MemoryBlock& destData) override {}
        void setStateInformation(const void* data, int sizeInBytes) override {}

        //==============================================================================
        // Graph Management
        
        /**
         * Adds a new track to the mixer.
         * Creates a chain of Gain -> Pan -> Master.
         * Returns the NodeID of the input node for this track (where audio should be fed).
         */
        juce::AudioProcessorGraph::NodeID addTrack(const juce::String& trackName);

        /**
         * Clears all tracks and resets to default state (Master bus only).
         */
        void clearTracks();

        /**
         * Get the underlying graph for visualization or advanced manipulation.
         */
        juce::AudioProcessorGraph& getGraph() { return *mainGraph; }

        //==============================================================================
        // FX Chain Management
        
        /**
         * Set the FX chain for a specific bus from JSON.
         * Rebuilds the processor chain to match the JSON configuration.
         * @param bus "master", "drums", "bass", or "melodic"
         * @param chainJson Array of FX unit objects
         */
        void setFXChainForBus(const juce::String& bus, const juce::var& chainJson);
        
        /**
         * Clear all FX from a bus, leaving only the gain stage.
         */
        void clearFXForBus(const juce::String& bus);
        
        /**
         * Update a single FX parameter.
         */
        void setFXParameter(const juce::String& fxId, const juce::String& paramName, float value);
        
        /**
         * Enable/disable an FX unit.
         */
        void setFXEnabled(const juce::String& fxId, bool enabled);

    private:
        std::unique_ptr<juce::AudioProcessorGraph> mainGraph;
        
        // Node IDs for fixed routing
        juce::AudioProcessorGraph::NodeID audioInputNodeID;
        juce::AudioProcessorGraph::NodeID audioOutputNodeID;
        juce::AudioProcessorGraph::NodeID midiInputNodeID;
        juce::AudioProcessorGraph::NodeID midiOutputNodeID;

        // Master Bus
        juce::AudioProcessorGraph::NodeID masterGainNodeID;
        
        // FX chains per bus
        std::map<juce::String, std::vector<FXNodeInfo>> fxChains;
        
        // Helper to create processor from type name
        std::unique_ptr<juce::AudioProcessor> createProcessor(const juce::String& type);
        
        // Reconnect FX chain for a bus after modifications
        void reconnectFXChain(const juce::String& bus);

        void initializeGraph();

        JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(MixerGraph)
    };
}
