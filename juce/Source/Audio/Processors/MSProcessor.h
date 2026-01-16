#pragma once

#include "ProcessorBase.h"

namespace Audio
{
    /**
     * MSProcessor - Mid/Side Stereo Processing
     * 
     * Professional M/S encoding/decoding with stereo width control.
     * 
     * Signal flow:
     *   Input L/R -> Encode to M/S -> Process -> Decode to L/R -> Output
     * 
     * Parameters:
     *   - width: 0.0 (mono) to 2.0 (extra wide), default 1.0
     *   - midGain: -12dB to +12dB, default 0dB
     *   - sideGain: -12dB to +12dB, default 0dB
     */
    class MSProcessor : public ProcessorBase
    {
    public:
        MSProcessor();
        ~MSProcessor() override = default;

        void prepareToPlay(double sampleRate, int samplesPerBlock) override;
        void processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer& midiMessages) override;
        void reset() override;

        const juce::String getName() const override { return "M/S Processor"; }

        /**
         * Set stereo width.
         * @param newWidth 0.0 (mono) to 2.0 (extra wide)
         */
        void setWidth(float newWidth);
        float getWidth() const { return targetWidth; }

        /**
         * Set mid channel gain.
         * @param gainDb -12dB to +12dB
         */
        void setMidGain(float gainDb);
        float getMidGain() const { return midGainDb; }

        /**
         * Set side channel gain.
         * @param gainDb -12dB to +12dB
         */
        void setSideGain(float gainDb);
        float getSideGain() const { return sideGainDb; }

    private:
        // Target parameter values
        float targetWidth = 1.0f;
        float midGainDb = 0.0f;
        float sideGainDb = 0.0f;
        float midGainLinear = 1.0f;
        float sideGainLinear = 1.0f;

        // Smoothed values for click-free parameter changes
        juce::LinearSmoothedValue<float> smoothedWidth;
        juce::LinearSmoothedValue<float> smoothedMidGain;
        juce::LinearSmoothedValue<float> smoothedSideGain;

        // Smoothing time in seconds
        static constexpr double smoothingTimeSeconds = 0.02; // 20ms

        JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(MSProcessor)
    };
}
