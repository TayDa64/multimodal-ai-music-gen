/*
  ==============================================================================

    ExpansionInstrumentLoader.h
    
    Scans MPC expansion folders for instruments, parses XPM files,
    and builds a catalog of available instruments with sample mappings.
    
    Supports:
    - Chromatic instruments (bass, keys, synths, pads) with multi-sample zones
    - One-shot samples (drums, FX)
    - Drum kits with pad mappings

  ==============================================================================
*/

#pragma once

#include <juce_core/juce_core.h>
#include <juce_audio_formats/juce_audio_formats.h>
#include <map>
#include <vector>

namespace mmg
{

//==============================================================================
/**
    A single sample zone within an instrument.
    Maps a range of MIDI notes to a specific sample.
*/
struct SampleZone
{
    juce::String sampleName;    // Sample filename without extension
    juce::File sampleFile;      // Full path to WAV file
    int rootNote = 60;          // Original pitch of the sample (MIDI note)
    int lowNote = 0;            // Lowest MIDI note this zone responds to
    int highNote = 127;         // Highest MIDI note this zone responds to
    int lowVelocity = 0;        // Lowest velocity
    int highVelocity = 127;     // Highest velocity
    float volume = 1.0f;        // Zone volume
    float pan = 0.5f;           // Pan (0.0 = left, 0.5 = center, 1.0 = right)
    
    bool containsNote(int midiNote, int velocity = 64) const
    {
        return midiNote >= lowNote && midiNote <= highNote &&
               velocity >= lowVelocity && velocity <= highVelocity;
    }
};

//==============================================================================
/**
    Information about a single instrument (program) from an expansion.
*/
struct InstrumentDefinition
{
    juce::String id;              // Unique ID: "expansion_category_name"
    juce::String name;            // Display name: "Amphi Bass"
    juce::String category;        // bass, keys, synth, pad, drums, fx
    juce::String expansionId;     // Parent expansion ID
    juce::String expansionName;   // "Funk o Rama"
    juce::File xpmFile;           // Source XPM file
    juce::File expansionPath;     // Base path for resolving sample files
    
    std::vector<SampleZone> zones;  // Sample zones (multi-sample mapping)
    
    bool isChromatic = true;      // True for melodic instruments
    bool isMono = false;          // Mono playback mode
    int polyphony = 8;            // Max voices
    
    // Envelope defaults
    float attack = 0.0f;
    float decay = 0.05f;
    float sustain = 1.0f;
    float release = 0.1f;
};

//==============================================================================
/**
    Information about an expansion pack.
*/
struct ExpansionDefinition
{
    juce::String id;                // "funk_o_rama"
    juce::String name;              // "Funk o Rama"
    juce::String version;           // "1.0.5"
    juce::File path;                // Root folder path
    
    juce::StringArray categories;   // Available categories in this expansion
    std::map<juce::String, std::vector<InstrumentDefinition>> instruments; // By category
    
    int getTotalInstrumentCount() const
    {
        int total = 0;
        for (const auto& [cat, insts] : instruments)
            total += (int)insts.size();
        return total;
    }
};

//==============================================================================
/**
    Scans expansion folders and builds instrument catalog.
*/
class ExpansionInstrumentLoader
{
public:
    ExpansionInstrumentLoader();
    ~ExpansionInstrumentLoader() = default;
    
    //==========================================================================
    // Scanning
    //==========================================================================
    
    /** Scan a single expansion folder and add to catalog. */
    bool scanExpansion(const juce::File& expansionFolder);
    
    /** Scan all expansions in a parent directory. */
    int scanExpansionsDirectory(const juce::File& expansionsDir);
    
    /** Clear all loaded expansions. */
    void clear();
    
    //==========================================================================
    // Catalog Access
    //==========================================================================
    
    /** Get all loaded expansions. */
    const std::map<juce::String, ExpansionDefinition>& getExpansions() const { return expansions; }
    
    /** Get expansion by ID. */
    const ExpansionDefinition* getExpansion(const juce::String& id) const;
    
    /** Get all instruments across all expansions, organized by category. */
    std::map<juce::String, std::vector<const InstrumentDefinition*>> getInstrumentsByCategory() const;
    
    /** Get a specific instrument by ID. */
    const InstrumentDefinition* getInstrument(const juce::String& instrumentId) const;
    
    /** Get all instruments in a category (across all expansions). */
    std::vector<const InstrumentDefinition*> getInstrumentsInCategory(const juce::String& category) const;
    
    /** Get all available categories. */
    juce::StringArray getCategories() const;
    
    /** Get total instrument count. */
    int getTotalInstrumentCount() const;

private:
    //==========================================================================
    // XPM Parsing
    //==========================================================================
    
    bool parseXpmFile(const juce::File& xpmFile, InstrumentDefinition& outInstrument);
    juce::String categorizeInstrument(const juce::String& filename) const;
    juce::String sanitizeId(const juce::String& name) const;
    
    //==========================================================================
    // Members
    //==========================================================================
    
    std::map<juce::String, ExpansionDefinition> expansions;
    std::map<juce::String, InstrumentDefinition> instrumentLookup; // Quick lookup by ID
    
    // Category detection patterns
    struct CategoryPattern
    {
        juce::String prefix;
        juce::String category;
    };
    std::vector<CategoryPattern> categoryPatterns = {
        { "Inst-Bass-", "bass" },
        { "Inst-Keys-", "keys" },
        { "Inst-Synth-", "synth" },
        { "Inst-Pad-", "pad" },
        { "RnB-Kick", "drums" },
        { "RnB-Snare", "drums" },
        { "RnB-Clap", "drums" },
        { "RnB-Hat", "drums" },
        { "RnB-Cymbal", "drums" },
        { "RnB-Perc", "drums" },
        { "RnB-Drum", "drums" },
        { "RnB-Guitar", "guitar" },
        { "RnB-Keys", "keys" },
        { "RnB-Bass", "bass" },
        { "RnB-Synth", "synth" },
        { "RnB-Vocal", "vocals" },
        { "RnB-FX", "fx" },
        { "Kit-", "drumkits" }
    };
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(ExpansionInstrumentLoader)
};

} // namespace mmg
