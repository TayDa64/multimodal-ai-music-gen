/*
  ==============================================================================

    SFZParser.cpp
    
    Implementation of SFZ file parser.

  ==============================================================================
*/

#include "SFZParser.h"

namespace mmg
{

// Helper function: find substring starting from a position
static int findFrom(const juce::String& str, int startPos, const juce::String& needle)
{
    if (startPos >= str.length())
        return -1;
    int result = str.substring(startPos).indexOf(needle);
    return (result >= 0) ? result + startPos : -1;
}

bool SFZParser::parse(const juce::File& sfzFile, SFZInstrumentData& outData)
{
    if (!sfzFile.existsAsFile())
    {
        lastError = "SFZ file not found: " + sfzFile.getFullPathName();
        return false;
    }
    
    juce::String content = sfzFile.loadFileAsString();
    if (content.isEmpty())
    {
        lastError = "SFZ file is empty or unreadable";
        return false;
    }
    
    outData.sfzFile = sfzFile;
    outData.baseDirectory = sfzFile.getParentDirectory();
    
    return parseString(content, outData.baseDirectory, outData);
}

bool SFZParser::parseString(const juce::String& content, const juce::File& baseDir,
                            SFZInstrumentData& outData)
{
    outData.baseDirectory = baseDir;
    outData.groups.clear();
    outData.defaultPath.clear();
    outData.globalVolume = 0.0f;
    outData.globalTune = 0;
    
    // Preprocessing - remove comments and normalize whitespace
    juce::String processed;
    bool inBlockComment = false;
    
    juce::StringArray lines;
    lines.addTokens(content, "\n", "");
    
    for (auto& line : lines)
    {
        // Remove line comments
        int commentPos = line.indexOf("//");
        if (commentPos >= 0)
            line = line.substring(0, commentPos);
        
        // Handle block comments /* */
        while (true)
        {
            if (inBlockComment)
            {
                int endPos = line.indexOf("*/");
                if (endPos >= 0)
                {
                    line = line.substring(endPos + 2);
                    inBlockComment = false;
                }
                else
                {
                    line = "";
                    break;
                }
            }
            else
            {
                int startPos = line.indexOf("/*");
                if (startPos >= 0)
                {
                    int endPos = findFrom(line, startPos + 2, "*/");
                    if (endPos >= 0)
                    {
                        line = line.substring(0, startPos) + line.substring(endPos + 2);
                    }
                    else
                    {
                        line = line.substring(0, startPos);
                        inBlockComment = true;
                    }
                }
                else
                {
                    break;
                }
            }
        }
        
        line = line.trim();
        if (line.isNotEmpty())
            processed += line + " ";
    }
    
    // Parse sections and opcodes
    SectionType currentSection = SectionType::None;
    SFZGroup currentGroup;
    SFZRegion currentRegion;
    bool hasRegion = false;
    bool hasGroup = false;
    
    int pos = 0;
    while (pos < processed.length())
    {
        // Skip whitespace
        while (pos < processed.length() && juce::CharacterFunctions::isWhitespace(processed[pos]))
            pos++;
        
        if (pos >= processed.length())
            break;
        
        // Check for header
        if (processed[pos] == '<')
        {
            int endPos = findFrom(processed, pos, ">");
            if (endPos < 0)
            {
                lastError = "Unterminated header at position " + juce::String(pos);
                return false;
            }
            
            juce::String header = processed.substring(pos + 1, endPos).toLowerCase().trim();
            pos = endPos + 1;
            
            // Save current region/group if any
            if (hasRegion)
            {
                // Resolve sample path
                currentRegion.sampleFile = resolveSamplePath(currentRegion.sample, 
                                                              baseDir, outData.defaultPath);
                currentGroup.regions.push_back(currentRegion);
                currentRegion = SFZRegion();
                hasRegion = false;
            }
            
            if (header == "global")
            {
                // Save current group if any
                if (hasGroup && !currentGroup.regions.empty())
                {
                    outData.groups.push_back(currentGroup);
                    currentGroup = SFZGroup();
                }
                currentSection = SectionType::Global;
                hasGroup = false;
            }
            else if (header == "control")
            {
                if (hasGroup && !currentGroup.regions.empty())
                {
                    outData.groups.push_back(currentGroup);
                    currentGroup = SFZGroup();
                }
                currentSection = SectionType::Control;
                hasGroup = false;
            }
            else if (header == "group")
            {
                if (hasGroup && !currentGroup.regions.empty())
                {
                    outData.groups.push_back(currentGroup);
                }
                currentGroup = SFZGroup();
                currentSection = SectionType::Group;
                hasGroup = true;
            }
            else if (header == "region")
            {
                if (!hasGroup)
                {
                    // Create implicit group
                    currentGroup = SFZGroup();
                    hasGroup = true;
                }
                
                // Initialize region with group defaults
                currentRegion = SFZRegion();
                currentRegion.lokey = currentGroup.lokey;
                currentRegion.hikey = currentGroup.hikey;
                currentRegion.lovel = currentGroup.lovel;
                currentRegion.hivel = currentGroup.hivel;
                currentRegion.pitch_keycenter = currentGroup.pitch_keycenter;
                currentRegion.volume = currentGroup.volume;
                currentRegion.pan = currentGroup.pan;
                currentRegion.ampeg_attack = currentGroup.ampeg_attack;
                currentRegion.ampeg_decay = currentGroup.ampeg_decay;
                currentRegion.ampeg_sustain = currentGroup.ampeg_sustain;
                currentRegion.ampeg_release = currentGroup.ampeg_release;
                currentRegion.group = currentGroup.group;
                currentRegion.off_by = currentGroup.off_by;
                currentRegion.trigger = currentGroup.trigger;
                
                currentSection = SectionType::Region;
                hasRegion = true;
            }
            else if (header == "curve" || header == "effect" || header == "master" || header == "midi")
            {
                // Unsupported headers - skip
                currentSection = SectionType::None;
            }
        }
        else
        {
            // Parse opcode=value
            int eqPos = findFrom(processed, pos, "=");
            if (eqPos < 0)
            {
                // Skip unknown token
                while (pos < processed.length() && !juce::CharacterFunctions::isWhitespace(processed[pos]))
                    pos++;
                continue;
            }
            
            juce::String opcode = processed.substring(pos, eqPos).trim().toLowerCase();
            pos = eqPos + 1;
            
            // Parse value (may contain spaces if quoted or for sample paths)
            juce::String value;
            bool needsPath = (opcode == "sample" || opcode == "default_path");
            
            if (needsPath)
            {
                // Value extends until next opcode or header
                int nextHeader = findFrom(processed, pos, "<");
                int nextEq = findFrom(processed, pos, "=");
                int endVal = processed.length();
                
                if (nextHeader >= 0 && (nextEq < 0 || nextHeader < nextEq))
                    endVal = nextHeader;
                else if (nextEq >= 0)
                {
                    // Find start of next opcode (word before =)
                    int wordStart = nextEq - 1;
                    while (wordStart > pos && !juce::CharacterFunctions::isWhitespace(processed[wordStart - 1]))
                        wordStart--;
                    if (wordStart > pos)
                        endVal = wordStart;
                }
                
                value = processed.substring(pos, endVal).trim();
                pos = endVal;
            }
            else
            {
                // Simple value - read until whitespace
                int startVal = pos;
                while (pos < processed.length() && 
                       !juce::CharacterFunctions::isWhitespace(processed[pos]) &&
                       processed[pos] != '<')
                    pos++;
                value = processed.substring(startVal, pos).trim();
            }
            
            // Apply opcode
            parseOpcode(opcode, value, outData, currentGroup, currentRegion, currentSection);
        }
    }
    
    // Save final region/group
    if (hasRegion)
    {
        currentRegion.sampleFile = resolveSamplePath(currentRegion.sample, 
                                                      baseDir, outData.defaultPath);
        currentGroup.regions.push_back(currentRegion);
    }
    
    if (hasGroup && !currentGroup.regions.empty())
    {
        outData.groups.push_back(currentGroup);
    }
    
    return true;
}

void SFZParser::parseOpcode(const juce::String& opcode, const juce::String& value,
                            SFZInstrumentData& data, SFZGroup& currentGroup,
                            SFZRegion& currentRegion, SectionType section)
{
    // Helper to parse note names (C4, D#5, etc.) or MIDI numbers
    auto parseNote = [](const juce::String& s) -> int {
        juce::String lower = s.toLowerCase().trim();
        
        // Try as integer first
        if (lower.containsOnly("0123456789-"))
            return lower.getIntValue();
        
        // Parse note name
        static const int noteOffsets[] = { 9, 11, 0, 2, 4, 5, 7 }; // a, b, c, d, e, f, g
        
        if (lower.isEmpty())
            return 60;
        
        int note = 0;
        int pos = 0;
        
        char firstChar = (char)lower[pos++];
        if (firstChar >= 'a' && firstChar <= 'g')
            note = noteOffsets[firstChar - 'a'];
        else if (firstChar >= 'c' && firstChar <= 'b')
            note = noteOffsets[firstChar - 'c' + 2];
        else
            return lower.getIntValue();
        
        // Check for sharp/flat
        if (pos < lower.length())
        {
            char second = (char)lower[pos];
            if (second == '#' || second == 's')
            {
                note++;
                pos++;
            }
            else if (second == 'b')
            {
                note--;
                pos++;
            }
        }
        
        // Parse octave
        int octave = lower.substring(pos).getIntValue();
        note += (octave + 1) * 12;
        
        return juce::jlimit(0, 127, note);
    };
    
    // Apply opcode based on section
    if (opcode == "sample")
    {
        if (section == SectionType::Region)
            currentRegion.sample = value;
    }
    else if (opcode == "default_path")
    {
        data.defaultPath = value.replace("\\", "/");
        if (!data.defaultPath.endsWithChar('/'))
            data.defaultPath += "/";
    }
    else if (opcode == "lokey")
    {
        int v = parseNote(value);
        if (section == SectionType::Region) currentRegion.lokey = v;
        else if (section == SectionType::Group) currentGroup.lokey = v;
    }
    else if (opcode == "hikey")
    {
        int v = parseNote(value);
        if (section == SectionType::Region) currentRegion.hikey = v;
        else if (section == SectionType::Group) currentGroup.hikey = v;
    }
    else if (opcode == "key")
    {
        int v = parseNote(value);
        if (section == SectionType::Region)
        {
            currentRegion.lokey = currentRegion.hikey = currentRegion.pitch_keycenter = v;
        }
        else if (section == SectionType::Group)
        {
            currentGroup.lokey = currentGroup.hikey = currentGroup.pitch_keycenter = v;
        }
    }
    else if (opcode == "pitch_keycenter")
    {
        int v = parseNote(value);
        if (section == SectionType::Region) currentRegion.pitch_keycenter = v;
        else if (section == SectionType::Group) currentGroup.pitch_keycenter = v;
    }
    else if (opcode == "lovel")
    {
        int v = value.getIntValue();
        if (section == SectionType::Region) currentRegion.lovel = v;
        else if (section == SectionType::Group) currentGroup.lovel = v;
    }
    else if (opcode == "hivel")
    {
        int v = value.getIntValue();
        if (section == SectionType::Region) currentRegion.hivel = v;
        else if (section == SectionType::Group) currentGroup.hivel = v;
    }
    else if (opcode == "volume")
    {
        float v = value.getFloatValue();
        if (section == SectionType::Region) currentRegion.volume = v;
        else if (section == SectionType::Group) currentGroup.volume = v;
        else if (section == SectionType::Global) data.globalVolume = v;
    }
    else if (opcode == "pan")
    {
        float v = value.getFloatValue();
        if (section == SectionType::Region) currentRegion.pan = v;
        else if (section == SectionType::Group) currentGroup.pan = v;
    }
    else if (opcode == "tune")
    {
        float v = value.getFloatValue();
        if (section == SectionType::Region) currentRegion.tune = v;
    }
    else if (opcode == "transpose")
    {
        int v = value.getIntValue();
        if (section == SectionType::Region) currentRegion.transpose = v;
    }
    else if (opcode == "pitch_keytrack")
    {
        int v = value.getIntValue();
        if (section == SectionType::Region) currentRegion.pitch_keytrack = v;
    }
    else if (opcode == "ampeg_attack")
    {
        float v = value.getFloatValue();
        if (section == SectionType::Region) currentRegion.ampeg_attack = v;
        else if (section == SectionType::Group) currentGroup.ampeg_attack = v;
    }
    else if (opcode == "ampeg_decay")
    {
        float v = value.getFloatValue();
        if (section == SectionType::Region) currentRegion.ampeg_decay = v;
        else if (section == SectionType::Group) currentGroup.ampeg_decay = v;
    }
    else if (opcode == "ampeg_sustain")
    {
        float v = value.getFloatValue();
        if (section == SectionType::Region) currentRegion.ampeg_sustain = v;
        else if (section == SectionType::Group) currentGroup.ampeg_sustain = v;
    }
    else if (opcode == "ampeg_release")
    {
        float v = value.getFloatValue();
        if (section == SectionType::Region) currentRegion.ampeg_release = v;
        else if (section == SectionType::Group) currentGroup.ampeg_release = v;
    }
    else if (opcode == "loop_mode")
    {
        if (section == SectionType::Region)
            currentRegion.loop_mode = value.toLowerCase();
    }
    else if (opcode == "loop_start")
    {
        if (section == SectionType::Region)
            currentRegion.loop_start = value.getIntValue();
    }
    else if (opcode == "loop_end")
    {
        if (section == SectionType::Region)
            currentRegion.loop_end = value.getIntValue();
    }
    else if (opcode == "offset")
    {
        if (section == SectionType::Region)
            currentRegion.offset = value.getIntValue();
    }
    else if (opcode == "end")
    {
        if (section == SectionType::Region)
            currentRegion.end = value.getIntValue();
    }
    else if (opcode == "group")
    {
        int v = value.getIntValue();
        if (section == SectionType::Region) currentRegion.group = v;
        else if (section == SectionType::Group) currentGroup.group = v;
    }
    else if (opcode == "off_by")
    {
        int v = value.getIntValue();
        if (section == SectionType::Region) currentRegion.off_by = v;
        else if (section == SectionType::Group) currentGroup.off_by = v;
    }
    else if (opcode == "trigger")
    {
        if (section == SectionType::Region) currentRegion.trigger = value.toLowerCase();
        else if (section == SectionType::Group) currentGroup.trigger = value.toLowerCase();
    }
    // Many more opcodes could be supported here...
}

juce::File SFZParser::resolveSamplePath(const juce::String& samplePath,
                                         const juce::File& baseDir,
                                         const juce::String& defaultPath)
{
    if (samplePath.isEmpty())
        return juce::File();
    
    // Normalize path separators
    juce::String path = samplePath.replace("\\", "/");
    
    // Apply default_path if set
    if (defaultPath.isNotEmpty() && !juce::File::isAbsolutePath(path))
    {
        path = defaultPath + path;
    }
    
    // Resolve relative to base directory
    if (juce::File::isAbsolutePath(path))
        return juce::File(path);
    else
        return baseDir.getChildFile(path);
}

} // namespace mmg
