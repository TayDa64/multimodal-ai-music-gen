#pragma once

#include "ProcessorBase.h"

namespace Audio
{
    class PanProcessor : public ProcessorBase
    {
    public:
        PanProcessor();
        ~PanProcessor() override = default;

        void prepareToPlay(double sampleRate, int samplesPerBlock) override;
        void processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer& midiMessages) override;
        void reset() override;

        const juce::String getName() const override { return "Pan"; }

        /**
         * Set pan position.
         * @param newPan -1.0 (left) to 1.0 (right)
         */
        void setPan(float newPan);
        float getPan() const { return currentPan; }

    private:
        float currentPan = 0.0f;
        juce::LinearSmoothedValue<float> smoothedPan;

        JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(PanProcessor)
    };
}
