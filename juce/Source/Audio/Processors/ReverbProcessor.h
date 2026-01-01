#pragma once

#include "ProcessorBase.h"
#include <juce_dsp/juce_dsp.h>

namespace Audio
{
    /**
     * Simple reverb processor using JUCE's built-in reverb.
     */
    class ReverbProcessor : public ProcessorBase
    {
    public:
        ReverbProcessor()
            : ProcessorBase(BusesProperties()
                .withInput("Input", juce::AudioChannelSet::stereo(), true)
                .withOutput("Output", juce::AudioChannelSet::stereo(), true))
        {
            updateReverb();
        }

        const juce::String getName() const override { return "Reverb"; }

        void prepareToPlay(double sampleRate, int samplesPerBlock) override
        {
            juce::dsp::ProcessSpec spec;
            spec.sampleRate = sampleRate;
            spec.maximumBlockSize = static_cast<juce::uint32>(samplesPerBlock);
            spec.numChannels = 2;
            
            reverb.prepare(spec);
        }

        void processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer&) override
        {
            if (!enabled)
                return;
                
            juce::dsp::AudioBlock<float> block(buffer);
            juce::dsp::ProcessContextReplacing<float> context(block);
            reverb.process(context);
        }

        // Parameters
        void setRoomSize(float size)
        {
            roomSize = juce::jlimit(0.0f, 1.0f, size);
            updateReverb();
        }
        
        void setDamping(float d)
        {
            damping = juce::jlimit(0.0f, 1.0f, d);
            updateReverb();
        }
        
        void setWetLevel(float wet)
        {
            wetLevel = juce::jlimit(0.0f, 1.0f, wet);
            updateReverb();
        }
        
        void setDryLevel(float dry)
        {
            dryLevel = juce::jlimit(0.0f, 1.0f, dry);
            updateReverb();
        }
        
        void setWidth(float w)
        {
            width = juce::jlimit(0.0f, 1.0f, w);
            updateReverb();
        }
        
        void setEnabled(bool e) { enabled = e; }
        bool isEnabled() const { return enabled; }

    private:
        void updateReverb()
        {
            juce::Reverb::Parameters params;
            params.roomSize = roomSize;
            params.damping = damping;
            params.wetLevel = wetLevel;
            params.dryLevel = dryLevel;
            params.width = width;
            params.freezeMode = 0.0f;
            reverb.setParameters(params);
        }
        
        juce::dsp::Reverb reverb;
        
        float roomSize = 0.5f;
        float damping = 0.5f;
        float wetLevel = 0.3f;
        float dryLevel = 0.7f;
        float width = 1.0f;
        bool enabled = true;
        
        JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(ReverbProcessor)
    };
}
