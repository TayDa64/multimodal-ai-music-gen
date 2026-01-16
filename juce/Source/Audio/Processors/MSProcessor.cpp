#include "MSProcessor.h"

namespace Audio
{
    MSProcessor::MSProcessor()
        : ProcessorBase(BusesProperties().withInput("Input", juce::AudioChannelSet::stereo(), true)
                                         .withOutput("Output", juce::AudioChannelSet::stereo(), true))
    {
        // Initialize smoothed values with defaults
        smoothedWidth.reset(44100.0, smoothingTimeSeconds);
        smoothedWidth.setCurrentAndTargetValue(1.0f);

        smoothedMidGain.reset(44100.0, smoothingTimeSeconds);
        smoothedMidGain.setCurrentAndTargetValue(1.0f);

        smoothedSideGain.reset(44100.0, smoothingTimeSeconds);
        smoothedSideGain.setCurrentAndTargetValue(1.0f);
    }

    void MSProcessor::prepareToPlay(double sampleRate, int samplesPerBlock)
    {
        smoothedWidth.reset(sampleRate, smoothingTimeSeconds);
        smoothedMidGain.reset(sampleRate, smoothingTimeSeconds);
        smoothedSideGain.reset(sampleRate, smoothingTimeSeconds);
    }

    void MSProcessor::processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer& midiMessages)
    {
        // Need stereo for M/S processing
        if (buffer.getNumChannels() < 2)
            return;

        const int numSamples = buffer.getNumSamples();
        auto* leftChannel = buffer.getWritePointer(0);
        auto* rightChannel = buffer.getWritePointer(1);

        for (int i = 0; i < numSamples; ++i)
        {
            // Get smoothed parameter values
            const float width = smoothedWidth.getNextValue();
            const float midGain = smoothedMidGain.getNextValue();
            const float sideGain = smoothedSideGain.getNextValue();

            // Read input samples
            const float left = leftChannel[i];
            const float right = rightChannel[i];

            // Encode L/R to M/S
            const float mid = (left + right) * 0.5f;
            const float side = (left - right) * 0.5f;

            // Apply gains and width
            const float midProcessed = mid * midGain;
            const float sideProcessed = side * sideGain * width;

            // Decode M/S back to L/R
            leftChannel[i] = midProcessed + sideProcessed;
            rightChannel[i] = midProcessed - sideProcessed;
        }
    }

    void MSProcessor::reset()
    {
        smoothedWidth.setCurrentAndTargetValue(targetWidth);
        smoothedMidGain.setCurrentAndTargetValue(midGainLinear);
        smoothedSideGain.setCurrentAndTargetValue(sideGainLinear);
    }

    void MSProcessor::setWidth(float newWidth)
    {
        targetWidth = juce::jlimit(0.0f, 2.0f, newWidth);
        smoothedWidth.setTargetValue(targetWidth);
    }

    void MSProcessor::setMidGain(float gainDb)
    {
        midGainDb = juce::jlimit(-12.0f, 12.0f, gainDb);
        midGainLinear = juce::Decibels::decibelsToGain(midGainDb);
        smoothedMidGain.setTargetValue(midGainLinear);
    }

    void MSProcessor::setSideGain(float gainDb)
    {
        sideGainDb = juce::jlimit(-12.0f, 12.0f, gainDb);
        sideGainLinear = juce::Decibels::decibelsToGain(sideGainDb);
        smoothedSideGain.setTargetValue(sideGainLinear);
    }
}
