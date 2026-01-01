#pragma once

#include "ProcessorBase.h"
#include <juce_dsp/juce_dsp.h>

namespace Audio
{
    /**
     * Compressor processor with standard controls.
     */
    class CompressorProcessor : public ProcessorBase
    {
    public:
        CompressorProcessor()
            : ProcessorBase(BusesProperties()
                .withInput("Input", juce::AudioChannelSet::stereo(), true)
                .withOutput("Output", juce::AudioChannelSet::stereo(), true))
        {
        }

        const juce::String getName() const override { return "Compressor"; }

        void prepareToPlay(double sampleRate, int samplesPerBlock) override
        {
            juce::dsp::ProcessSpec spec;
            spec.sampleRate = sampleRate;
            spec.maximumBlockSize = static_cast<juce::uint32>(samplesPerBlock);
            spec.numChannels = 2;
            
            compressor.prepare(spec);
            updateCompressor();
        }

        void processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer&) override
        {
            if (!enabled)
                return;
                
            juce::dsp::AudioBlock<float> block(buffer);
            juce::dsp::ProcessContextReplacing<float> context(block);
            compressor.process(context);
        }

        // Parameters
        void setThreshold(float thresholdDb)
        {
            threshold = juce::jlimit(-60.0f, 0.0f, thresholdDb);
            updateCompressor();
        }
        
        void setRatio(float r)
        {
            ratio = juce::jlimit(1.0f, 20.0f, r);
            updateCompressor();
        }
        
        void setAttack(float attackMs)
        {
            attack = juce::jlimit(0.1f, 100.0f, attackMs);
            updateCompressor();
        }
        
        void setRelease(float releaseMs)
        {
            release = juce::jlimit(10.0f, 1000.0f, releaseMs);
            updateCompressor();
        }
        
        void setEnabled(bool e) { enabled = e; }
        bool isEnabled() const { return enabled; }

    private:
        void updateCompressor()
        {
            compressor.setThreshold(threshold);
            compressor.setRatio(ratio);
            compressor.setAttack(attack);
            compressor.setRelease(release);
        }
        
        juce::dsp::Compressor<float> compressor;
        
        float threshold = -20.0f;
        float ratio = 4.0f;
        float attack = 10.0f;
        float release = 100.0f;
        bool enabled = true;
        
        JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(CompressorProcessor)
    };
}
