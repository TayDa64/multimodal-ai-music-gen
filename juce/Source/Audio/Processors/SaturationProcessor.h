#pragma once

#include "ProcessorBase.h"
#include <juce_dsp/juce_dsp.h>

namespace Audio
{
    /**
     * Saturation/Tape emulation processor using waveshaping.
     */
    class SaturationProcessor : public ProcessorBase
    {
    public:
        SaturationProcessor()
            : ProcessorBase(BusesProperties()
                .withInput("Input", juce::AudioChannelSet::stereo(), true)
                .withOutput("Output", juce::AudioChannelSet::stereo(), true))
        {
            // Initialize waveshaper with soft clipping function
            waveshaper.functionToUse = [](float x)
            {
                // Soft clipping using tanh
                return std::tanh(x);
            };
        }

        const juce::String getName() const override { return "Saturation"; }

        void prepareToPlay(double sampleRate, int samplesPerBlock) override
        {
            juce::dsp::ProcessSpec spec;
            spec.sampleRate = sampleRate;
            spec.maximumBlockSize = static_cast<juce::uint32>(samplesPerBlock);
            spec.numChannels = 2;
            
            waveshaper.prepare(spec);
        }

        void processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer&) override
        {
            if (!enabled || drive <= 0.01f)
                return;
                
            // Apply input gain (drive), then waveshaping, then output compensation
            for (int channel = 0; channel < buffer.getNumChannels(); ++channel)
            {
                auto* channelData = buffer.getWritePointer(channel);
                for (int sample = 0; sample < buffer.getNumSamples(); ++sample)
                {
                    float input = channelData[sample];
                    
                    // Apply drive (increase before saturation)
                    float driven = input * (1.0f + drive * 10.0f);
                    
                    // Apply saturation curve based on type
                    float saturated;
                    switch (type)
                    {
                        case SaturationType::Tape:
                            saturated = tapeStyle(driven);
                            break;
                        case SaturationType::Tube:
                            saturated = tubeStyle(driven);
                            break;
                        case SaturationType::Hard:
                            saturated = hardClip(driven);
                            break;
                        default:
                            saturated = softClip(driven);
                            break;
                    }
                    
                    // Compensate for drive gain
                    float compensated = saturated / (1.0f + drive * 3.0f);
                    
                    // Mix dry/wet
                    channelData[sample] = (input * (1.0f - mix)) + (compensated * mix);
                }
            }
        }

        enum class SaturationType
        {
            Soft,   // Tanh soft clipping
            Tape,   // Tape-style saturation
            Tube,   // Tube-style asymmetric
            Hard    // Hard clipping
        };

        // Parameters
        void setDrive(float d)
        {
            drive = juce::jlimit(0.0f, 1.0f, d);
        }
        
        void setMix(float m)
        {
            mix = juce::jlimit(0.0f, 1.0f, m);
        }
        
        void setType(SaturationType t)
        {
            type = t;
        }
        
        void setEnabled(bool e) { enabled = e; }
        bool isEnabled() const { return enabled; }

    private:
        // Soft clip using tanh
        static float softClip(float x)
        {
            return std::tanh(x);
        }
        
        // Tape-style saturation with hysteresis-like curve
        static float tapeStyle(float x)
        {
            // Approximation of tape saturation
            if (x > 0.0f)
                return 1.0f - std::exp(-x);
            else
                return -1.0f + std::exp(x);
        }
        
        // Tube-style asymmetric saturation
        static float tubeStyle(float x)
        {
            // Asymmetric - more compression on positive peaks
            if (x >= 0.0f)
                return std::tanh(x * 1.2f);
            else
                return std::tanh(x * 0.8f);
        }
        
        // Hard clipping
        static float hardClip(float x)
        {
            return juce::jlimit(-1.0f, 1.0f, x);
        }
        
        juce::dsp::WaveShaper<float> waveshaper;
        
        float drive = 0.3f;
        float mix = 0.5f;
        SaturationType type = SaturationType::Tape;
        bool enabled = true;
        
        JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(SaturationProcessor)
    };
}
