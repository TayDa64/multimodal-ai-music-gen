#pragma once

#include "ProcessorBase.h"
#include <juce_dsp/juce_dsp.h>

namespace Audio
{
    /**
     * Stereo delay processor with feedback.
     */
    class DelayProcessor : public ProcessorBase
    {
    public:
        DelayProcessor()
            : ProcessorBase(BusesProperties()
                .withInput("Input", juce::AudioChannelSet::stereo(), true)
                .withOutput("Output", juce::AudioChannelSet::stereo(), true))
        {
        }

        const juce::String getName() const override { return "Delay"; }

        void prepareToPlay(double sampleRate, int samplesPerBlock) override
        {
            currentSampleRate = sampleRate;
            
            juce::dsp::ProcessSpec spec;
            spec.sampleRate = sampleRate;
            spec.maximumBlockSize = static_cast<juce::uint32>(samplesPerBlock);
            spec.numChannels = 2;
            
            // Max 2 seconds of delay
            delayLine.setMaximumDelayInSamples(static_cast<int>(sampleRate * 2.0));
            delayLine.prepare(spec);
            
            updateDelay();
        }

        void processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer&) override
        {
            if (!enabled)
                return;
                
            auto numSamples = buffer.getNumSamples();
            auto numChannels = buffer.getNumChannels();
            
            for (int sample = 0; sample < numSamples; ++sample)
            {
                for (int channel = 0; channel < numChannels; ++channel)
                {
                    float inputSample = buffer.getSample(channel, sample);
                    float delayedSample = delayLine.popSample(channel);
                    
                    // Push input + feedback to delay line
                    delayLine.pushSample(channel, inputSample + (delayedSample * feedback));
                    
                    // Mix dry and wet
                    float outputSample = (inputSample * dryLevel) + (delayedSample * wetLevel);
                    buffer.setSample(channel, sample, outputSample);
                }
            }
        }

        // Parameters
        void setDelayTime(float timeMs)
        {
            delayTimeMs = juce::jlimit(1.0f, 2000.0f, timeMs);
            updateDelay();
        }
        
        void setFeedback(float fb)
        {
            feedback = juce::jlimit(0.0f, 0.95f, fb);
        }
        
        void setWetLevel(float wet)
        {
            wetLevel = juce::jlimit(0.0f, 1.0f, wet);
        }
        
        void setDryLevel(float dry)
        {
            dryLevel = juce::jlimit(0.0f, 1.0f, dry);
        }
        
        void setEnabled(bool e) { enabled = e; }
        bool isEnabled() const { return enabled; }

    private:
        void updateDelay()
        {
            if (currentSampleRate > 0.0)
            {
                int delaySamples = static_cast<int>((delayTimeMs / 1000.0) * currentSampleRate);
                delayLine.setDelay(static_cast<float>(delaySamples));
            }
        }
        
        juce::dsp::DelayLine<float, juce::dsp::DelayLineInterpolationTypes::Linear> delayLine { 88200 };
        
        double currentSampleRate = 44100.0;
        float delayTimeMs = 250.0f;
        float feedback = 0.3f;
        float wetLevel = 0.3f;
        float dryLevel = 1.0f;
        bool enabled = true;
        
        JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(DelayProcessor)
    };
}
