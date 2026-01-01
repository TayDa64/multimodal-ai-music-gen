#pragma once

#include "ProcessorBase.h"
#include <juce_dsp/juce_dsp.h>

namespace Audio
{
    /**
     * 3-band EQ processor (Low, Mid, High).
     */
    class EQProcessor : public ProcessorBase
    {
    public:
        EQProcessor()
            : ProcessorBase(BusesProperties()
                .withInput("Input", juce::AudioChannelSet::stereo(), true)
                .withOutput("Output", juce::AudioChannelSet::stereo(), true))
        {
        }

        const juce::String getName() const override { return "EQ"; }

        void prepareToPlay(double sampleRate, int samplesPerBlock) override
        {
            currentSampleRate = sampleRate;
            
            juce::dsp::ProcessSpec spec;
            spec.sampleRate = sampleRate;
            spec.maximumBlockSize = static_cast<juce::uint32>(samplesPerBlock);
            spec.numChannels = 2;
            
            lowShelf.prepare(spec);
            midPeak.prepare(spec);
            highShelf.prepare(spec);
            
            updateFilters();
        }

        void processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer&) override
        {
            if (!enabled)
                return;
                
            juce::dsp::AudioBlock<float> block(buffer);
            juce::dsp::ProcessContextReplacing<float> context(block);
            
            lowShelf.process(context);
            midPeak.process(context);
            highShelf.process(context);
        }

        // Parameters
        void setLowGain(float gainDb)
        {
            lowGainDb = juce::jlimit(-12.0f, 12.0f, gainDb);
            updateFilters();
        }
        
        void setMidGain(float gainDb)
        {
            midGainDb = juce::jlimit(-12.0f, 12.0f, gainDb);
            updateFilters();
        }
        
        void setHighGain(float gainDb)
        {
            highGainDb = juce::jlimit(-12.0f, 12.0f, gainDb);
            updateFilters();
        }
        
        void setEnabled(bool e) { enabled = e; }
        bool isEnabled() const { return enabled; }

    private:
        void updateFilters()
        {
            if (currentSampleRate <= 0.0)
                return;
                
            // Low shelf at 200 Hz
            *lowShelf.state = *juce::dsp::IIR::Coefficients<float>::makeLowShelf(
                currentSampleRate, 200.0f, 0.707f, juce::Decibels::decibelsToGain(lowGainDb));
            
            // Mid peak at 1 kHz
            *midPeak.state = *juce::dsp::IIR::Coefficients<float>::makePeakFilter(
                currentSampleRate, 1000.0f, 1.0f, juce::Decibels::decibelsToGain(midGainDb));
            
            // High shelf at 5 kHz
            *highShelf.state = *juce::dsp::IIR::Coefficients<float>::makeHighShelf(
                currentSampleRate, 5000.0f, 0.707f, juce::Decibels::decibelsToGain(highGainDb));
        }
        
        juce::dsp::ProcessorDuplicator<juce::dsp::IIR::Filter<float>, juce::dsp::IIR::Coefficients<float>> lowShelf;
        juce::dsp::ProcessorDuplicator<juce::dsp::IIR::Filter<float>, juce::dsp::IIR::Coefficients<float>> midPeak;
        juce::dsp::ProcessorDuplicator<juce::dsp::IIR::Filter<float>, juce::dsp::IIR::Coefficients<float>> highShelf;
        
        double currentSampleRate = 44100.0;
        float lowGainDb = 0.0f;
        float midGainDb = 0.0f;
        float highGainDb = 0.0f;
        bool enabled = true;
        
        JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(EQProcessor)
    };
}
