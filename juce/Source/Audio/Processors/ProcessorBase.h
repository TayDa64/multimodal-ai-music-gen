#pragma once

#include <juce_audio_processors/juce_audio_processors.h>
#include <juce_core/juce_core.h>

namespace Audio
{
    /**
     * Base class for internal audio processors used in the mixer graph.
     * Simplifies the AudioProcessor boilerplate for internal FX.
     */
    class ProcessorBase : public juce::AudioProcessor
    {
    public:
        ProcessorBase(const BusesProperties& layouts)
            : AudioProcessor(layouts)
        {
        }

        ~ProcessorBase() override = default;

        //==============================================================================
        void prepareToPlay(double sampleRate, int samplesPerBlock) override {}
        void releaseResources() override {}

        //==============================================================================
        bool hasEditor() const override { return false; }
        juce::AudioProcessorEditor* createEditor() override { return nullptr; }

        //==============================================================================
        const juce::String getName() const override { return "ProcessorBase"; }

        bool acceptsMidi() const override { return false; }
        bool producesMidi() const override { return false; }
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

    private:
        JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(ProcessorBase)
    };
}
