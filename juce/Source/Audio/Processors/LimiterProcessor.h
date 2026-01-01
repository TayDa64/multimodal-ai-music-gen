#pragma once

#include "ProcessorBase.h"
#include <juce_dsp/juce_dsp.h>

namespace Audio
{
    /**
     * Brick-wall limiter for master bus.
     */
    class LimiterProcessor : public ProcessorBase
    {
    public:
        LimiterProcessor()
            : ProcessorBase(BusesProperties()
                .withInput("Input", juce::AudioChannelSet::stereo(), true)
                .withOutput("Output", juce::AudioChannelSet::stereo(), true))
        {
        }

        const juce::String getName() const override { return "Limiter"; }

        void prepareToPlay(double sampleRate, int samplesPerBlock) override
        {
            juce::dsp::ProcessSpec spec;
            spec.sampleRate = sampleRate;
            spec.maximumBlockSize = static_cast<juce::uint32>(samplesPerBlock);
            spec.numChannels = 2;
            
            limiter.prepare(spec);
            updateLimiter();
        }

        void processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer&) override
        {
            if (!enabled)
                return;
                
            juce::dsp::AudioBlock<float> block(buffer);
            juce::dsp::ProcessContextReplacing<float> context(block);
            limiter.process(context);
        }

        // Parameters
        void setThreshold(float thresholdDb)
        {
            threshold = juce::jlimit(-20.0f, 0.0f, thresholdDb);
            updateLimiter();
        }
        
        void setRelease(float releaseMs)
        {
            release = juce::jlimit(1.0f, 500.0f, releaseMs);
            updateLimiter();
        }
        
        void setEnabled(bool e) { enabled = e; }
        bool isEnabled() const { return enabled; }

    private:
        void updateLimiter()
        {
            limiter.setThreshold(threshold);
            limiter.setRelease(release);
        }
        
        juce::dsp::Limiter<float> limiter;
        
        float threshold = -1.0f;
        float release = 100.0f;
        bool enabled = true;
        
        JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(LimiterProcessor)
    };
}
