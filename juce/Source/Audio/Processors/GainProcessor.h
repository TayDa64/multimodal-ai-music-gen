#pragma once

#include "ProcessorBase.h"
#include <juce_dsp/juce_dsp.h>

namespace Audio
{
    class GainProcessor : public ProcessorBase
    {
    public:
        GainProcessor();
        ~GainProcessor() override = default;

        void prepareToPlay(double sampleRate, int samplesPerBlock) override;
        void processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer& midiMessages) override;
        void reset() override;

        const juce::String getName() const override { return "Gain"; }

        // Parameter handling
        void setGainLinear(float newGain);
        void setGainDecibels(float newGainDb);
        float getGainLinear() const;

    private:
        juce::dsp::Gain<float> gain;
        juce::dsp::ProcessSpec spec;

        JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(GainProcessor)
    };
}
