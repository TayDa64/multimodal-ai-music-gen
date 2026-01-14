/*
  ==============================================================================
    MidiPlayer.cpp
    
    Implementation of MIDI file playback.
    
    Task 0.4: JUCE MIDI Playback Research
  ==============================================================================
*/

#include "MidiPlayer.h"

namespace mmg
{

//==============================================================================
MidiPlayer::MidiPlayer()
{
    setupSynthesiser();
}

//==============================================================================
void MidiPlayer::setupSynthesiser()
{
    // Clear any existing voices/sounds
    synth.clearVoices();
    synth.clearSounds();
    
    // Add sine wave voices (polyphony)
    for (int i = 0; i < numVoices; ++i)
    {
        synth.addVoice(new SimpleSineVoice());
    }
    
    // Add the sound (all voices use this)
    synth.addSound(new SimpleSineSound());
    
    DBG("MidiPlayer: Synthesiser setup with " << numVoices << " voices");
}

//==============================================================================
void MidiPlayer::prepareToPlay(double newSampleRate, int newSamplesPerBlock)
{
    sampleRate = newSampleRate;
    samplesPerBlock = newSamplesPerBlock;
    
    synth.setCurrentPlaybackSampleRate(sampleRate);
    
    // Prepare each voice
    for (int i = 0; i < synth.getNumVoices(); ++i)
    {
        if (auto* voice = dynamic_cast<SimpleSineVoice*>(synth.getVoice(i)))
        {
            voice->prepareToPlay(sampleRate, samplesPerBlock);
        }
    }
    
    DBG("MidiPlayer: Prepared - SR: " << sampleRate << ", Block: " << samplesPerBlock);
}

void MidiPlayer::releaseResources()
{
    synth.allNotesOff(0, true);
}

//==============================================================================
bool MidiPlayer::loadMidiFile(const juce::File& file)
{
    if (!file.existsAsFile())
    {
        DBG("MidiPlayer: File not found: " << file.getFullPathName());
        return false;
    }
    
    // Read the file
    juce::FileInputStream fileStream(file);
    if (!fileStream.openedOk())
    {
        DBG("MidiPlayer: Could not open file: " << file.getFullPathName());
        return false;
    }
    
    // Parse MIDI
    if (!midiFile.readFrom(fileStream))
    {
        DBG("MidiPlayer: Failed to parse MIDI file: " << file.getFullPathName());
        return false;
    }
    
    // Convert timestamps to seconds
    midiFile.convertTimestampTicksToSeconds();
    
    // Merge all tracks into one sequence for easier playback
    combinedSequence.clear();
    for (int track = 0; track < midiFile.getNumTracks(); ++track)
    {
        const auto* trackSequence = midiFile.getTrack(track);
        if (trackSequence != nullptr)
        {
            combinedSequence.addSequence(*trackSequence, 0.0);
        }
    }
    
    // Sort by timestamp
    combinedSequence.sort();
    
    // Update state
    loadedFile = file;
    midiLoaded = true;
    currentEventIndex = 0;
    currentPositionSeconds = 0.0;
    
    // Extract metadata (tempo, time signature, etc.)
    extractMetadata();
    
    // Calculate total duration
    if (combinedSequence.getNumEvents() > 0)
    {
        double lastEventTime = combinedSequence.getEndTime();
        
        // Round up to the next bar for musical looping
        if (bpm > 0 && timeSignatureNumerator > 0)
        {
            double secondsPerBeat = 60.0 / bpm;
            // Assuming 4/4 or similar where beat is a quarter note. 
            // For more complex signatures, we might need to adjust, but this is a good baseline.
            double beatsPerBar = (double)timeSignatureNumerator; 
            double secondsPerBar = secondsPerBeat * beatsPerBar;
            
            if (secondsPerBar > 0)
            {
                double totalBars = lastEventTime / secondsPerBar;
                double roundedBars = std::ceil(totalBars);
                // Ensure we have at least 1 bar if there are notes
                if (roundedBars < 1.0) roundedBars = 1.0;
                
                // Add a small buffer if the last note ends exactly on the bar line? 
                // No, exact bar length is better for looping.
                totalDurationSeconds = roundedBars * secondsPerBar;
                
                // If the rounded duration is significantly longer than the last event (e.g. > 1 bar of silence),
                // maybe we shouldn't round up that much? 
                // But for a loop, we usually want full bars.
            }
            else
            {
                totalDurationSeconds = lastEventTime + 1.0; // Fallback buffer
            }
        }
        else
        {
            totalDurationSeconds = lastEventTime + 1.0; // Fallback buffer
        }
    }
    else
    {
        totalDurationSeconds = 0.0;
    }
    
    DBG("MidiPlayer: Loaded " << file.getFileName());
    DBG("  Tracks: " << midiFile.getNumTracks());
    DBG("  Events: " << combinedSequence.getNumEvents());
    DBG("  Duration: " << totalDurationSeconds << "s");
    DBG("  BPM: " << bpm);
    
    return true;
}

void MidiPlayer::setMidiData(const juce::MidiFile& midi)
{
    midiFile = midi;
    
    // Convert timestamps to seconds
    midiFile.convertTimestampTicksToSeconds();
    
    // Merge all tracks into one sequence for easier playback
    combinedSequence.clear();
    for (int track = 0; track < midiFile.getNumTracks(); ++track)
    {
        const auto* trackSequence = midiFile.getTrack(track);
        if (trackSequence != nullptr)
        {
            combinedSequence.addSequence(*trackSequence, 0.0);
        }
    }
    
    // Sort by timestamp
    combinedSequence.sort();
    
    // Update state
    loadedFile = juce::File(); // Clear file path as it's memory-based
    midiLoaded = true;
    currentEventIndex = 0;
    currentPositionSeconds = 0.0;
    
    // Extract metadata (tempo, time signature, etc.)
    extractMetadata();
    
    // Calculate total duration
    if (combinedSequence.getNumEvents() > 0)
    {
        double lastEventTime = combinedSequence.getEndTime();
        
        // Round up to the next bar for musical looping
        if (bpm > 0 && timeSignatureNumerator > 0)
        {
            double secondsPerBeat = 60.0 / bpm;
            double beatsPerBar = (double)timeSignatureNumerator;
            double secondsPerBar = secondsPerBeat * beatsPerBar;
            
            if (secondsPerBar > 0)
            {
                double totalBars = lastEventTime / secondsPerBar;
                double roundedBars = std::ceil(totalBars);
                if (roundedBars < 1.0) roundedBars = 1.0;
                totalDurationSeconds = roundedBars * secondsPerBar;
            }
            else
            {
                totalDurationSeconds = lastEventTime + 1.0;
            }
        }
        else
        {
            totalDurationSeconds = lastEventTime + 1.0;
        }
    }
    else
    {
        totalDurationSeconds = 0.0;
    }
    
    DBG("MidiPlayer: Loaded MIDI from memory");
    DBG("  Tracks: " << midiFile.getNumTracks());
    DBG("  Events: " << combinedSequence.getNumEvents());
    DBG("  Duration: " << totalDurationSeconds << "s");
    DBG("  BPM: " << bpm);
}

void MidiPlayer::clearMidiFile()
{
    playing = false;
    midiLoaded = false;
    combinedSequence.clear();
    midiFile.clear();
    loadedFile = juce::File();
    currentEventIndex = 0;
    currentPositionSeconds = 0.0;
    totalDurationSeconds = 0.0;
    
    // Turn off any playing notes
    synth.allNotesOff(0, true);
}

void MidiPlayer::extractMetadata()
{
    // Default values
    bpm = 120.0;
    timeSignatureNumerator = 4;
    timeSignatureDenominator = 4;
    
    // Look for tempo and time signature in track 0 (conductor track)
    const auto* track0 = midiFile.getTrack(0);
    if (track0 == nullptr)
        return;
    
    for (int i = 0; i < track0->getNumEvents(); ++i)
    {
        auto& midiEvent = track0->getEventPointer(i)->message;
        
        if (midiEvent.isTempoMetaEvent())
        {
            double secondsPerQuarterNote = midiEvent.getTempoSecondsPerQuarterNote();
            if (secondsPerQuarterNote > 0)
            {
                bpm = 60.0 / secondsPerQuarterNote;
            }
        }
        else if (midiEvent.isTimeSignatureMetaEvent())
        {
            int numerator, denominator;
            midiEvent.getTimeSignatureInfo(numerator, denominator);
            timeSignatureNumerator = numerator;
            timeSignatureDenominator = denominator;
        }
    }
}

//==============================================================================
void MidiPlayer::setPlaying(bool shouldPlay)
{
    if (shouldPlay && !midiLoaded)
    {
        DBG("MidiPlayer: Cannot play - no MIDI loaded");
        return;
    }
    
    if (!shouldPlay)
    {
        // Turn off all notes when stopping
        synth.allNotesOff(0, true);
    }
    
    playing = shouldPlay;
}

void MidiPlayer::setPosition(double positionInSeconds)
{
    // Clamp to valid range
    currentPositionSeconds = juce::jlimit(0.0, totalDurationSeconds, positionInSeconds);
    
    // Find the event index for this position
    currentEventIndex = 0;
    for (int i = 0; i < combinedSequence.getNumEvents(); ++i)
    {
        if (combinedSequence.getEventPointer(i)->message.getTimeStamp() >= currentPositionSeconds)
        {
            currentEventIndex = i;
            break;
        }
        currentEventIndex = i + 1;
    }
    
    // Turn off all notes when seeking
    synth.allNotesOff(0, true);
}

//==============================================================================
void MidiPlayer::renderNextBlock(juce::AudioBuffer<float>& buffer, int numSamples)
{
    if (!playing || !midiLoaded)
    {
        buffer.clear();
        return;
    }

    const bool shouldRenderSynth = renderInternalSynth.load();
    if (shouldRenderSynth)
        buffer.clear();
    
    // Calculate time advance for this block
    double blockDurationSeconds = numSamples / sampleRate;
    double endPositionSeconds = currentPositionSeconds + (blockDurationSeconds * tempoMultiplier);
    
    // Create MIDI buffer for events in this time range (only needed if we're rendering the internal synth)
    juce::MidiBuffer midiBuffer;
    int eventsAdded = 0;
    
    while (currentEventIndex < combinedSequence.getNumEvents())
    {
        auto* eventPtr = combinedSequence.getEventPointer(currentEventIndex);
        double eventTime = eventPtr->message.getTimeStamp();
        
        // Check if event is within this block's time range
        if (eventTime >= endPositionSeconds)
            break;
        
        // Calculate sample offset within this block
        double offsetSeconds = eventTime - currentPositionSeconds;
        int sampleOffset = juce::jmax(0, static_cast<int>(offsetSeconds * sampleRate / tempoMultiplier));
        sampleOffset = juce::jmin(sampleOffset, numSamples - 1);
        
        // Process MIDI message (skip meta events)
        if (!eventPtr->message.isMetaEvent())
        {
            const auto& msg = eventPtr->message;
            
            // Route note events to external instruments (Track SamplerInstruments)
            if (midiListener)
            {
                if (msg.isNoteOn())
                {
                    // Channel 1-16 maps to track index 0-15
                    int trackIndex = msg.getChannel() - 1;
                    float velocity = msg.getVelocity() / 127.0f;
                    midiListener->midiNoteOn(trackIndex, msg.getNoteNumber(), velocity);
                }
                else if (msg.isNoteOff())
                {
                    int trackIndex = msg.getChannel() - 1;
                    midiListener->midiNoteOff(trackIndex, msg.getNoteNumber());
                }
            }
            
            // Also feed to internal synth (fallback sine waves for unmapped instruments)
            if (shouldRenderSynth)
                midiBuffer.addEvent(msg, sampleOffset);
            eventsAdded++;
        }
        
        ++currentEventIndex;
    }
    
    // Render internal synth with MIDI events (sine wave fallback)
    // If disabled, AudioEngine tracks provide all audio.
    if (shouldRenderSynth)
        synth.renderNextBlock(buffer, midiBuffer, 0, numSamples);
    
    // Track max output level for debug status
    float maxSample = 0.0f;
    for (int ch = 0; ch < buffer.getNumChannels(); ++ch)
    {
        for (int i = 0; i < numSamples; ++i)
            maxSample = juce::jmax(maxSample, std::abs(buffer.getSample(ch, i)));
    }
    lastMaxSample.store(maxSample);
    lastEventsInBlock.store(eventsAdded);
    
    // Update position
    currentPositionSeconds = endPositionSeconds;
    
    // Check for end of file
    if (currentPositionSeconds >= totalDurationSeconds)
    {
        playing = false;
        currentPositionSeconds = 0.0;
        currentEventIndex = 0;
        synth.allNotesOff(0, true);
        DBG("MidiPlayer: Playback finished");
    }
}

} // namespace mmg
