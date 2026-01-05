/*
  ==============================================================================

    ExpansionInstrumentLoader.cpp
    
    Implementation of expansion/XPM parsing and instrument catalog building.

  ==============================================================================
*/

#include "ExpansionInstrumentLoader.h"

namespace mmg
{

//==============================================================================
ExpansionInstrumentLoader::ExpansionInstrumentLoader() {}

//==============================================================================
// Scanning
//==============================================================================

bool ExpansionInstrumentLoader::scanExpansion(const juce::File& expansionFolder)
{
    if (!expansionFolder.isDirectory())
        return false;
    
    DBG("ExpansionInstrumentLoader: Scanning " << expansionFolder.getFullPathName());
    
    // Look for the actual expansion content folder
    // MPC expansions often have nested structure: 
    // /Expansion Name/Expansion Name-Version/Expansion Name/ (with XPM files)
    juce::File contentFolder = expansionFolder;
    
    // Recursively search for folder containing .xpm files (up to 3 levels deep)
    std::function<juce::File(const juce::File&, int)> findXpmFolder = [&](const juce::File& folder, int depth) -> juce::File {
        if (depth > 3) return juce::File();
        
        // Check this folder for XPM files
        auto xpmFiles = folder.findChildFiles(juce::File::findFiles, false, "*.xpm");
        if (!xpmFiles.isEmpty())
            return folder;
        
        // Check subdirectories
        auto subDirs = folder.findChildFiles(juce::File::findDirectories, false);
        for (const auto& subDir : subDirs)
        {
            // Skip hidden folders and system folders
            if (subDir.getFileName().startsWithChar('.') || 
                subDir.getFileName().startsWithChar('_'))
                continue;
            
            auto result = findXpmFolder(subDir, depth + 1);
            if (result.exists())
                return result;
        }
        
        return juce::File();
    };
    
    contentFolder = findXpmFolder(expansionFolder, 0);
    
    if (!contentFolder.exists())
    {
        DBG("  No folder with XPM files found");
        return false;
    }
    
    DBG("  Found content folder: " << contentFolder.getFullPathName());
    
    // Find all XPM files (only Inst-* pattern for keygrouped instruments)
    auto xpmFiles = contentFolder.findChildFiles(juce::File::findFiles, false, "Inst-*.xpm");
    
    if (xpmFiles.isEmpty())
    {
        // Also try RnB-Kit-* pattern for drum kits
        xpmFiles = contentFolder.findChildFiles(juce::File::findFiles, false, "*.xpm");
    }
    
    if (xpmFiles.isEmpty())
    {
        DBG("  No XPM files found");
        return false;
    }
    
    DBG("  Found " << xpmFiles.size() << " XPM files");
    
    // Create expansion definition
    ExpansionDefinition expansion;
    expansion.path = contentFolder;
    expansion.name = contentFolder.getFileName();
    expansion.id = sanitizeId(expansion.name);
    
    // Try to extract version from parent folder name
    juce::String parentName = expansionFolder.getFileName();
    auto dashIndex = parentName.lastIndexOf("-");
    if (dashIndex > 0)
    {
        expansion.version = parentName.substring(dashIndex + 1);
        // Also use cleaner name if available
        if (expansion.name.isEmpty())
            expansion.name = parentName.substring(0, dashIndex);
    }
    
    // Parse each XPM file
    for (const auto& xpmFile : xpmFiles)
    {
        InstrumentDefinition instrument;
        
        if (parseXpmFile(xpmFile, instrument))
        {
            instrument.expansionId = expansion.id;
            instrument.expansionName = expansion.name;
            instrument.expansionPath = contentFolder;
            
            // Add to category
            expansion.instruments[instrument.category].push_back(instrument);
            if (!expansion.categories.contains(instrument.category))
                expansion.categories.add(instrument.category);
            
            // Add to lookup
            instrumentLookup[instrument.id] = instrument;
            
            DBG("  Loaded: " << instrument.name << " (" << instrument.category << ") with " 
                << instrument.zones.size() << " zones");
        }
    }
    
    if (expansion.getTotalInstrumentCount() > 0)
    {
        expansions[expansion.id] = std::move(expansion);
        DBG("  Expansion loaded: " << expansion.name << " with " 
            << expansion.getTotalInstrumentCount() << " instruments");
        return true;
    }
    
    return false;
}

int ExpansionInstrumentLoader::scanExpansionsDirectory(const juce::File& expansionsDir)
{
    if (!expansionsDir.isDirectory())
        return 0;
    
    int count = 0;
    auto subDirs = expansionsDir.findChildFiles(juce::File::findDirectories, false);
    
    for (const auto& dir : subDirs)
    {
        if (scanExpansion(dir))
            count++;
    }
    
    DBG("ExpansionInstrumentLoader: Loaded " << count << " expansions with " 
        << getTotalInstrumentCount() << " total instruments");
    
    return count;
}

void ExpansionInstrumentLoader::clear()
{
    expansions.clear();
    instrumentLookup.clear();
}

//==============================================================================
// Catalog Access
//==============================================================================

const ExpansionDefinition* ExpansionInstrumentLoader::getExpansion(const juce::String& id) const
{
    auto it = expansions.find(id);
    return it != expansions.end() ? &it->second : nullptr;
}

std::map<juce::String, std::vector<const InstrumentDefinition*>> 
ExpansionInstrumentLoader::getInstrumentsByCategory() const
{
    std::map<juce::String, std::vector<const InstrumentDefinition*>> result;
    
    for (const auto& [expId, expansion] : expansions)
    {
        for (const auto& [category, instruments] : expansion.instruments)
        {
            for (const auto& inst : instruments)
            {
                result[category].push_back(&instrumentLookup.at(inst.id));
            }
        }
    }
    
    return result;
}

const InstrumentDefinition* ExpansionInstrumentLoader::getInstrument(const juce::String& instrumentId) const
{
    auto it = instrumentLookup.find(instrumentId);
    return it != instrumentLookup.end() ? &it->second : nullptr;
}

std::vector<const InstrumentDefinition*> 
ExpansionInstrumentLoader::getInstrumentsInCategory(const juce::String& category) const
{
    std::vector<const InstrumentDefinition*> result;
    
    for (const auto& [expId, expansion] : expansions)
    {
        auto it = expansion.instruments.find(category);
        if (it != expansion.instruments.end())
        {
            for (const auto& inst : it->second)
            {
                result.push_back(&instrumentLookup.at(inst.id));
            }
        }
    }
    
    return result;
}

juce::StringArray ExpansionInstrumentLoader::getCategories() const
{
    juce::StringArray categories;
    
    for (const auto& [expId, expansion] : expansions)
    {
        for (const auto& cat : expansion.categories)
        {
            if (!categories.contains(cat))
                categories.add(cat);
        }
    }
    
    // Sort in preferred order
    juce::StringArray sortedCategories;
    juce::StringArray preferredOrder = { "bass", "keys", "synth", "pad", "drums", "drumkits", "guitar", "vocals", "fx" };
    
    for (const auto& preferred : preferredOrder)
    {
        if (categories.contains(preferred))
            sortedCategories.add(preferred);
    }
    
    // Add any remaining
    for (const auto& cat : categories)
    {
        if (!sortedCategories.contains(cat))
            sortedCategories.add(cat);
    }
    
    return sortedCategories;
}

int ExpansionInstrumentLoader::getTotalInstrumentCount() const
{
    int total = 0;
    for (const auto& [id, exp] : expansions)
        total += exp.getTotalInstrumentCount();
    return total;
}

//==============================================================================
// XPM Parsing
//==============================================================================

bool ExpansionInstrumentLoader::parseXpmFile(const juce::File& xpmFile, InstrumentDefinition& outInstrument)
{
    // Parse XML structure of XPM file
    auto xml = juce::XmlDocument::parse(xpmFile);
    
    if (!xml)
    {
        DBG("  Failed to parse: " << xpmFile.getFileName());
        return false;
    }
    
    DBG("  Parsing XPM: " << xpmFile.getFileName());
    DBG("    Root element: " << xml->getTagName());
    
    // Navigate to Program element
    // XPM files have structure: <MPCVObject><Program type="Keygroup">...
    auto* program = xml->getChildByName("Program");
    if (!program)
    {
        // Try MPCVObject wrapper
        auto* mpcvObj = xml->getChildByName("MPCVObject");
        if (mpcvObj)
            program = mpcvObj->getChildByName("Program");
        
        // Or the root might be MPCVObject itself
        if (!program && xml->getTagName() == "MPCVObject")
            program = xml->getChildByName("Program");
    }
    
    if (!program)
    {
        DBG("    No Program element found in: " << xpmFile.getFileName());
        return false;
    }
    
    DBG("    Found Program element");
    
    // Get program name
    auto* nameElement = program->getChildByName("ProgramName");
    juce::String programName = nameElement ? nameElement->getAllSubText() : xpmFile.getFileNameWithoutExtension();
    
    outInstrument.xpmFile = xpmFile;
    outInstrument.name = programName;
    outInstrument.category = categorizeInstrument(programName);
    outInstrument.id = sanitizeId(programName);
    
    // Parse instrument settings
    auto* monoElement = program->getChildByName("Mono");
    outInstrument.isMono = monoElement && monoElement->getAllSubText().equalsIgnoreCase("true");
    
    auto* polyElement = program->getChildByName("Program_Polyphony");
    outInstrument.polyphony = polyElement ? polyElement->getAllSubText().getIntValue() : 8;
    if (outInstrument.polyphony < 1) outInstrument.polyphony = 8;
    
    // Parse instruments (key zones)
    auto* instruments = program->getChildByName("Instruments");
    if (!instruments)
    {
        DBG("    No Instruments element in: " << xpmFile.getFileName());
        return false;
    }
    
    DBG("    Found Instruments element");
    
    // Each Instrument element defines a key zone
    int zoneCount = 0;
    for (auto* inst : instruments->getChildIterator())
    {
        if (inst->getTagName() != "Instrument")
            continue;
        
        int lowNote = 0, highNote = 127;
        
        // Get note range for this zone
        auto* lowNoteEl = inst->getChildByName("LowNote");
        auto* highNoteEl = inst->getChildByName("HighNote");
        
        if (lowNoteEl)
            lowNote = lowNoteEl->getAllSubText().getIntValue();
        if (highNoteEl)
            highNote = highNoteEl->getAllSubText().getIntValue();
        
        // Parse layers (samples) within this instrument
        auto* layers = inst->getChildByName("Layers");
        if (!layers)
            continue;
        
        for (auto* layer : layers->getChildIterator())
        {
            if (layer->getTagName() != "Layer")
                continue;
            
            auto* activeEl = layer->getChildByName("Active");
            if (activeEl && activeEl->getAllSubText().equalsIgnoreCase("false"))
                continue;
            
            auto* sampleNameEl = layer->getChildByName("SampleName");
            if (!sampleNameEl)
                continue;
            
            juce::String sampleName = sampleNameEl->getAllSubText();
            if (sampleName.isEmpty())
                continue;
            
            SampleZone zone;
            zone.sampleName = sampleName;
            zone.lowNote = lowNote;
            zone.highNote = highNote;
            
            // Get root note
            auto* rootNoteEl = layer->getChildByName("RootNote");
            if (rootNoteEl)
            {
                int xpmRootNote = rootNoteEl->getAllSubText().getIntValue();
                // XPM uses a different numbering - convert to standard MIDI
                // XPM: C0 = 25, standard MIDI: C0 = 24
                zone.rootNote = xpmRootNote - 1;  // Approximate conversion
            }
            
            // Get velocity range
            auto* velStartEl = layer->getChildByName("VelStart");
            auto* velEndEl = layer->getChildByName("VelEnd");
            if (velStartEl)
                zone.lowVelocity = velStartEl->getAllSubText().getIntValue();
            if (velEndEl)
                zone.highVelocity = velEndEl->getAllSubText().getIntValue();
            
            // Get volume and pan
            auto* volumeEl = layer->getChildByName("Volume");
            auto* panEl = layer->getChildByName("Pan");
            if (volumeEl)
                zone.volume = (float)volumeEl->getAllSubText().getDoubleValue();
            if (panEl)
                zone.pan = (float)panEl->getAllSubText().getDoubleValue();
            
            // Resolve sample file path
            juce::File sampleFile = xpmFile.getParentDirectory().getChildFile(sampleName + ".WAV");
            if (!sampleFile.existsAsFile())
            {
                // Try lowercase
                sampleFile = xpmFile.getParentDirectory().getChildFile(sampleName + ".wav");
            }
            
            if (sampleFile.existsAsFile())
            {
                zone.sampleFile = sampleFile;
                outInstrument.zones.push_back(zone);
                zoneCount++;
            }
            else
            {
                DBG("    Sample not found: " << sampleName << " at " << sampleFile.getFullPathName());
            }
        }
    }
    
    DBG("    Total zones loaded: " << zoneCount);
    
    // Determine if chromatic based on category
    outInstrument.isChromatic = (outInstrument.category == "bass" || 
                                  outInstrument.category == "keys" ||
                                  outInstrument.category == "synth" ||
                                  outInstrument.category == "pad");
    
    return !outInstrument.zones.empty();
}

juce::String ExpansionInstrumentLoader::categorizeInstrument(const juce::String& filename) const
{
    for (const auto& pattern : categoryPatterns)
    {
        if (filename.startsWithIgnoreCase(pattern.prefix))
            return pattern.category;
    }
    return "other";
}

juce::String ExpansionInstrumentLoader::sanitizeId(const juce::String& name) const
{
    juce::String id = name.toLowerCase()
                          .replace(" ", "_")
                          .replace("-", "_")
                          .retainCharacters("abcdefghijklmnopqrstuvwxyz0123456789_");
    return id;
}

} // namespace mmg
