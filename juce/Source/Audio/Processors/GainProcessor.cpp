#include "GainProcessor.h"

namespace Audio
{
    GainProcessor::GainProcessor()
        : ProcessorBase(BusesProperties().withInput("Input", juce::AudioChannelSet::stereo(), true)
                                         .withOutput("Output", juce::AudioChannelSet::stereo(), true))
    {
        gain.setGainLinear(1.0f);
    }

    void GainProcessor::prepareToPlay(double sampleRate, int samplesPerBlock)
    {
        spec.sampleRate = sampleRate;
        spec.maximumBlockSize = samplesPerBlock;
        spec.numChannels = getTotalNumOutputChannels();

        gain.prepare(spec);
        gain.setRampDurationSeconds(0.05); // Smooth parameter changes
    }

    void GainProcessor::processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer& midiMessages)
    {
        juce::dsp::AudioBlock<float> block(buffer);
        juce::dsp::ProcessContextReplacing<float> context(block);
        gain.process(context);
    }

    void GainProcessor::reset()
    {
        gain.reset();
    }

    void GainProcessor::setGainLinear(float newGain)
    {
        gain.setGainLinear(newGain);
    }

    void GainProcessor::setGainDecibels(float newGainDb)
    {
        gain.setGainDecibels(newGainDb);
    }

    float GainProcessor::getGainLinear() const
    {
        return gain.getGainLinear();
    }
}
