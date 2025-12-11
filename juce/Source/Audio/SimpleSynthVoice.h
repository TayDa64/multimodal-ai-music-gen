/*
  ==============================================================================
    SimpleSynthVoice.h
    
    Simple sine wave synthesizer voice for testing MIDI playback.
    
    Task 0.4: JUCE MIDI Playback Research
  ==============================================================================
*/

#pragma once

#include <juce_audio_basics/juce_audio_basics.h>

namespace mmg
{

//==============================================================================
/**
    A simple sine wave sound that responds to all MIDI notes.
*/
class SimpleSineSound : public juce::SynthesiserSound
{
public:
    SimpleSineSound() = default;
    
    bool appliesToNote(int /*midiNoteNumber*/) override { return true; }
    bool appliesToChannel(int /*midiChannel*/) override { return true; }
};

//==============================================================================
/**
    A simple sine wave voice for basic MIDI playback testing.
    
    Features:
    - Sine wave oscillator
    - Simple ADSR envelope
    - Velocity sensitivity
*/
class SimpleSineVoice : public juce::SynthesiserVoice
{
public:
    SimpleSineVoice() = default;
    
    //==========================================================================
    bool canPlaySound(juce::SynthesiserSound* sound) override
    {
        return dynamic_cast<SimpleSineSound*>(sound) != nullptr;
    }
    
    //==========================================================================
    void startNote(int midiNoteNumber, float velocity,
                   juce::SynthesiserSound* /*sound*/,
                   int /*currentPitchWheelPosition*/) override
    {
        // Calculate frequency from MIDI note number
        // A4 (MIDI 69) = 440 Hz
        frequency = 440.0 * std::pow(2.0, (midiNoteNumber - 69) / 12.0);
        
        // Velocity affects amplitude (0.0 - 1.0 range)
        level = velocity * 0.3; // Scale down to prevent clipping
        
        // Reset phase
        phase = 0.0;
        
        // Start envelope
        envelope.noteOn();
    }
    
    //==========================================================================
    void stopNote(float /*velocity*/, bool allowTailOff) override
    {
        if (allowTailOff)
        {
            envelope.noteOff();
        }
        else
        {
            // Immediate stop
            clearCurrentNote();
            envelope.reset();
        }
    }
    
    //==========================================================================
    void pitchWheelMoved(int /*newPitchWheelValue*/) override
    {
        // Not implemented for simple voice
    }
    
    void controllerMoved(int /*controllerNumber*/, int /*newControllerValue*/) override
    {
        // Not implemented for simple voice
    }
    
    //==========================================================================
    void prepareToPlay(double sampleRate, int /*samplesPerBlock*/)
    {
        // Setup envelope
        juce::ADSR::Parameters envParams;
        envParams.attack = 0.01f;   // 10ms attack
        envParams.decay = 0.1f;     // 100ms decay
        envParams.sustain = 0.7f;   // 70% sustain level
        envParams.release = 0.3f;   // 300ms release
        
        envelope.setSampleRate(sampleRate);
        envelope.setParameters(envParams);
    }
    
    //==========================================================================
    void renderNextBlock(juce::AudioBuffer<float>& outputBuffer,
                        int startSample, int numSamples) override
    {
        if (!isVoiceActive())
            return;
            
        auto sampleRate = getSampleRate();
        if (sampleRate <= 0)
            return;
            
        const double phaseIncrement = juce::MathConstants<double>::twoPi * frequency / sampleRate;
        
        for (int sample = 0; sample < numSamples; ++sample)
        {
            // Generate sine wave
            auto sineValue = std::sin(phase);
            
            // Apply envelope
            auto envValue = envelope.getNextSample();
            
            // Calculate final sample value
            auto currentSample = static_cast<float>(sineValue * level * envValue);
            
            // Add to all output channels
            for (int channel = 0; channel < outputBuffer.getNumChannels(); ++channel)
            {
                outputBuffer.addSample(channel, startSample + sample, currentSample);
            }
            
            // Advance phase
            phase += phaseIncrement;
            if (phase >= juce::MathConstants<double>::twoPi)
                phase -= juce::MathConstants<double>::twoPi;
        }
        
        // Check if envelope has finished
        if (!envelope.isActive())
        {
            clearCurrentNote();
        }
    }

private:
    double frequency { 440.0 };
    double phase { 0.0 };
    double level { 0.0 };
    juce::ADSR envelope;
};

} // namespace mmg
