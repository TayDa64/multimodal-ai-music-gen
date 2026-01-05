/*
  ==============================================================================

    SFZParser.h
    
    Simple SFZ file parser for loading sample-based instruments.
    Supports common opcodes used in most SFZ instruments.

  ==============================================================================
*/

#pragma once

#include <juce_core/juce_core.h>
#include <juce_audio_formats/juce_audio_formats.h>
#include <vector>
#include <map>

namespace mmg
{

//==============================================================================
/**
    A region within an SFZ file - maps samples to key/velocity ranges.
*/
struct SFZRegion
{
    // Sample
    juce::String sample;           // Sample filename (relative to SFZ file)
    juce::File sampleFile;         // Resolved absolute path
    
    // Key mapping
    int lokey = 0;
    int hikey = 127;
    int pitch_keycenter = 60;      // Root note
    int pitch_keytrack = 100;      // Cents per semitone
    
    // Velocity mapping  
    int lovel = 0;
    int hivel = 127;
    
    // Playback
    float volume = 0.0f;           // dB
    float pan = 0.0f;              // -100 to +100
    float tune = 0.0f;             // Cents
    int transpose = 0;             // Semitones
    
    // Envelope
    float ampeg_attack = 0.001f;
    float ampeg_decay = 0.0f;
    float ampeg_sustain = 100.0f;  // Percent
    float ampeg_release = 0.001f;
    
    // Loop
    juce::String loop_mode = "no_loop";  // no_loop, loop_continuous, loop_sustain
    int loop_start = 0;
    int loop_end = 0;
    
    // Sample playback
    int offset = 0;                // Sample start offset
    int end = 0;                   // Sample end (0 = use full sample)
    
    // Group/exclusion
    int group = 0;
    int off_by = 0;
    
    // Trigger
    juce::String trigger = "attack";  // attack, release, first, legato
    
    /** Check if this region responds to a given note and velocity. */
    bool matches(int note, int velocity) const
    {
        return note >= lokey && note <= hikey &&
               velocity >= lovel && velocity <= hivel;
    }
};

//==============================================================================
/**
    Group within an SFZ file - groups share common settings.
*/
struct SFZGroup
{
    // Default values for regions in this group
    int lokey = 0;
    int hikey = 127;
    int lovel = 0;
    int hivel = 127;
    int pitch_keycenter = 60;
    float volume = 0.0f;
    float pan = 0.0f;
    float ampeg_attack = 0.001f;
    float ampeg_decay = 0.0f;
    float ampeg_sustain = 100.0f;
    float ampeg_release = 0.001f;
    int group = 0;
    int off_by = 0;
    juce::String trigger = "attack";
    
    std::vector<SFZRegion> regions;
};

//==============================================================================
/**
    Parsed SFZ instrument.
*/
struct SFZInstrumentData
{
    juce::File sfzFile;
    juce::File baseDirectory;      // Directory containing the SFZ
    juce::String defaultPath;      // default_path opcode value
    
    // Global defaults
    float globalVolume = 0.0f;
    int globalTune = 0;
    
    std::vector<SFZGroup> groups;
    
    /** Get all regions across all groups. */
    std::vector<const SFZRegion*> getAllRegions() const
    {
        std::vector<const SFZRegion*> allRegions;
        for (const auto& group : groups)
        {
            for (const auto& region : group.regions)
            {
                allRegions.push_back(&region);
            }
        }
        return allRegions;
    }
    
    /** Find regions matching a note and velocity. */
    std::vector<const SFZRegion*> findRegions(int note, int velocity) const
    {
        std::vector<const SFZRegion*> matches;
        for (const auto& group : groups)
        {
            for (const auto& region : group.regions)
            {
                if (region.matches(note, velocity))
                    matches.push_back(&region);
            }
        }
        return matches;
    }
};

//==============================================================================
/**
    Parser for SFZ files.
*/
class SFZParser
{
public:
    SFZParser() = default;
    ~SFZParser() = default;
    
    /** Parse an SFZ file.
        @param sfzFile The SFZ file to parse
        @param outData Output data structure
        @returns true if parsing succeeded */
    bool parse(const juce::File& sfzFile, SFZInstrumentData& outData);
    
    /** Parse SFZ content from a string.
        @param content SFZ file content
        @param baseDir Base directory for resolving sample paths
        @param outData Output data structure
        @returns true if parsing succeeded */
    bool parseString(const juce::String& content, const juce::File& baseDir, 
                     SFZInstrumentData& outData);
    
    /** Get last error message. */
    juce::String getLastError() const { return lastError; }

private:
    juce::String lastError;
    
    // Parsing state
    enum class SectionType { None, Global, Group, Region, Control };
    
    void parseOpcode(const juce::String& opcode, const juce::String& value,
                     SFZInstrumentData& data, SFZGroup& currentGroup, 
                     SFZRegion& currentRegion, SectionType section);
    
    juce::File resolveSamplePath(const juce::String& samplePath,
                                  const juce::File& baseDir,
                                  const juce::String& defaultPath);
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(SFZParser)
};

} // namespace mmg
