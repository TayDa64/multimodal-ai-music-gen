#include "PanProcessor.h"

namespace Audio
{
    PanProcessor::PanProcessor()
        : ProcessorBase(BusesProperties().withInput("Input", juce::AudioChannelSet::stereo(), true)
                                         .withOutput("Output", juce::AudioChannelSet::stereo(), true))
    {
        smoothedPan.reset(44100.0, 0.05); // Default, updated in prepareToPlay
        smoothedPan.setCurrentAndTargetValue(0.0f);
    }

    void PanProcessor::prepareToPlay(double sampleRate, int samplesPerBlock)
    {
        smoothedPan.reset(sampleRate, 0.05); // 50ms smoothing
    }

    void PanProcessor::processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer& midiMessages)
    {
        // Ensure stereo
        if (buffer.getNumChannels() != 2)
            return;

        const int numSamples = buffer.getNumSamples();
        auto* left = buffer.getWritePointer(0);
        auto* right = buffer.getWritePointer(1);

        for (int i = 0; i < numSamples; ++i)
        {
            float pan = smoothedPan.getNextValue();
            
            // Constant power panning
            // pan is -1 to 1
            // normalized to 0 to 1
            float normPan = (pan + 1.0f) * 0.5f;
            
            float gainL = std::cos(normPan * juce::MathConstants<float>::halfPi);
            float gainR = std::sin(normPan * juce::MathConstants<float>::halfPi);

            left[i] *= gainL;
            right[i] *= gainR;
        }
    }

    void PanProcessor::reset()
    {
        smoothedPan.setCurrentAndTargetValue(currentPan);
    }

    void PanProcessor::setPan(float newPan)
    {
        currentPan = juce::jlimit(-1.0f, 1.0f, newPan);
        smoothedPan.setTargetValue(currentPan);
    }
}
