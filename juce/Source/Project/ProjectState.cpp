/*
  ==============================================================================

    ProjectState.cpp
    
    Manages the project document state using juce::ValueTree and UndoManager.

  ==============================================================================
*/

#include "ProjectState.h"

namespace Project
{
    ProjectState::ProjectState()
        : projectTree(IDs::PROJECT), isDirty(false)
    {
        createDefaultProject();
        projectTree.addListener(this);
    }

    ProjectState::~ProjectState()
    {
        projectTree.removeListener(this);
    }

    void ProjectState::createDefaultProject()
    {
        projectTree.removeAllChildren(&undoManager);
        projectTree.removeAllProperties(&undoManager);
        
        projectTree.setProperty(IDs::version, "1.0.0", &undoManager);
        
        // Create Generation Node
        juce::ValueTree genNode(IDs::GENERATION);
        projectTree.addChild(genNode, -1, &undoManager);
        
        // Create Mixer Node
        juce::ValueTree mixerNode(IDs::MIXER);
        projectTree.addChild(mixerNode, -1, &undoManager);
        
        // Create 4 default tracks
        for (int i = 0; i < 4; ++i)
        {
            juce::ValueTree trackNode(IDs::TRACK);
            trackNode.setProperty(IDs::index, i, nullptr);
            trackNode.setProperty(IDs::name, "Track " + juce::String(i + 1), nullptr);
            trackNode.setProperty(IDs::volume, 1.0f, nullptr);
            trackNode.setProperty(IDs::pan, 0.0f, nullptr);
            trackNode.setProperty(IDs::mute, false, nullptr);
            trackNode.setProperty(IDs::solo, false, nullptr);
            mixerNode.addChild(trackNode, -1, &undoManager);
        }
        
        // Create Instruments Node
        juce::ValueTree instNode(IDs::INSTRUMENTS);
        projectTree.addChild(instNode, -1, &undoManager);
        
        // Create Notes Node (under Generation for now, or root?)
        // Let's put it at root for easier access, representing the "Arrangement"
        juce::ValueTree notesNode(IDs::NOTES);
        projectTree.addChild(notesNode, -1, &undoManager);
        
        // Create FX Chains Node
        juce::ValueTree fxChainsNode(IDs::FX_CHAINS);
        projectTree.addChild(fxChainsNode, -1, &undoManager);
        
        undoManager.clearUndoHistory();
        currentFile = juce::File();
    }

    void ProjectState::newProject()
    {
        createDefaultProject();
        isDirty = false;
    }

    bool ProjectState::loadProject(const juce::File& file)
    {
        auto xml = juce::parseXML(file);
        if (xml != nullptr && xml->hasTagName(IDs::PROJECT))
        {
            auto newTree = juce::ValueTree::fromXml(*xml);
            if (newTree.isValid())
            {
                projectTree.removeListener(this);
                projectTree = newTree;
                projectTree.addListener(this);
                undoManager.clearUndoHistory();
                currentFile = file;
                isDirty = false;
                return true;
            }
        }
        return false;
    }

    bool ProjectState::saveProject(const juce::File& file)
    {
        if (auto xml = projectTree.createXml())
        {
            if (xml->writeTo(file))
            {
                currentFile = file;
                isDirty = false;
                return true;
            }
        }
        return false;
    }

    //==============================================================================
    // Accessors & Modifiers

    void ProjectState::setGenerationData(const juce::String& prompt, int bpm, const juce::String& key, const juce::String& genre)
    {
        auto genNode = projectTree.getChildWithName(IDs::GENERATION);
        if (genNode.isValid())
        {
            undoManager.beginNewTransaction("Update Generation Data");
            genNode.setProperty(IDs::prompt, prompt, &undoManager);
            genNode.setProperty(IDs::bpm, bpm, &undoManager);
            genNode.setProperty(IDs::key, key, &undoManager);
            genNode.setProperty(IDs::genre, genre, &undoManager);
        }
    }

    void ProjectState::setGeneratedFiles(const juce::String& midiPath, const juce::String& audioPath)
    {
        auto genNode = projectTree.getChildWithName(IDs::GENERATION);
        if (genNode.isValid())
        {
            undoManager.beginNewTransaction("Update Generated Files");
            genNode.setProperty(IDs::midiPath, midiPath, &undoManager);
            genNode.setProperty(IDs::audioPath, audioPath, &undoManager);
        }
    }

    juce::ValueTree ProjectState::getMixerNode()
    {
        return projectTree.getChildWithName(IDs::MIXER);
    }

    juce::ValueTree ProjectState::getTrackNode(int index)
    {
        auto mixerNode = getMixerNode();
        if (!mixerNode.isValid()) return {};

        // Find track with index
        for (auto child : mixerNode)
        {
            if (child.hasType(IDs::TRACK) && (int)child.getProperty(IDs::index) == index)
                return child;
        }

        // Create if not exists
        juce::ValueTree trackNode(IDs::TRACK);
        trackNode.setProperty(IDs::index, index, nullptr);
        mixerNode.addChild(trackNode, -1, &undoManager);
        return trackNode;
    }
    
    juce::ValueTree ProjectState::getInstrumentsNode()
    {
        auto node = projectTree.getChildWithName(IDs::INSTRUMENTS);
        if (!node.isValid())
        {
            node = juce::ValueTree(IDs::INSTRUMENTS);
            projectTree.addChild(node, -1, &undoManager);
        }
        return node;
    }
    
    juce::ValueTree ProjectState::getFXChainsNode()
    {
        auto node = projectTree.getChildWithName(IDs::FX_CHAINS);
        if (!node.isValid())
        {
            node = juce::ValueTree(IDs::FX_CHAINS);
            projectTree.addChild(node, -1, &undoManager);
        }
        return node;
    }

    void ProjectState::setTrackVolume(int trackIndex, float volume)
    {
        auto track = getTrackNode(trackIndex);
        if (track.isValid())
        {
            // Don't start a new transaction for continuous updates like sliders, 
            // usually handled by the UI calling beginNewTransaction on mouse down.
            // For now, we'll just set it.
            track.setProperty(IDs::volume, volume, &undoManager);
        }
    }

    void ProjectState::setTrackPan(int trackIndex, float pan)
    {
        auto track = getTrackNode(trackIndex);
        if (track.isValid())
            track.setProperty(IDs::pan, pan, &undoManager);
    }

    void ProjectState::setTrackMute(int trackIndex, bool mute)
    {
        auto track = getTrackNode(trackIndex);
        if (track.isValid())
        {
            undoManager.beginNewTransaction("Toggle Mute");
            track.setProperty(IDs::mute, mute, &undoManager);
        }
    }

    void ProjectState::setTrackSolo(int trackIndex, bool solo)
    {
        auto track = getTrackNode(trackIndex);
        if (track.isValid())
        {
            undoManager.beginNewTransaction("Toggle Solo");
            track.setProperty(IDs::solo, solo, &undoManager);
        }
    }
    
    void ProjectState::setInstrument(int trackIndex, const juce::String& name, const juce::String& path)
    {
        auto instsNode = projectTree.getChildWithName(IDs::INSTRUMENTS);
        if (!instsNode.isValid()) return;
        
        // Find or create instrument node for this track
        juce::ValueTree instNode;
        for (auto child : instsNode)
        {
            if (child.hasType(IDs::INSTRUMENT) && (int)child.getProperty(IDs::index) == trackIndex)
            {
                instNode = child;
                break;
            }
        }
        
        if (!instNode.isValid())
        {
            instNode = juce::ValueTree(IDs::INSTRUMENT);
            instNode.setProperty(IDs::index, trackIndex, nullptr);
            instsNode.addChild(instNode, -1, &undoManager);
        }
        
        undoManager.beginNewTransaction("Change Instrument");
        instNode.setProperty(IDs::name, name, &undoManager);
        instNode.setProperty(IDs::path, path, &undoManager);
    }

    //==============================================================================
    // Note Editing
    void ProjectState::clearNotes()
    {
        auto notesNode = projectTree.getChildWithName(IDs::NOTES);
        if (notesNode.isValid())
        {
            undoManager.beginNewTransaction("Clear Notes");
            notesNode.removeAllChildren(&undoManager);
        }
    }

    void ProjectState::addNote(int noteNum, double startBeats, double lengthBeats, int velocity, int channel)
    {
        auto notesNode = projectTree.getChildWithName(IDs::NOTES);
        if (notesNode.isValid())
        {
            juce::ValueTree note(IDs::NOTE);
            note.setProperty(IDs::noteNumber, noteNum, nullptr);
            note.setProperty(IDs::start, startBeats, nullptr);
            note.setProperty(IDs::length, lengthBeats, nullptr);
            note.setProperty(IDs::velocity, velocity, nullptr);
            note.setProperty(IDs::channel, channel, nullptr);
            
            // Don't start a transaction here, usually called in batch or by UI that started one
            notesNode.addChild(note, -1, &undoManager);
        }
    }

    void ProjectState::deleteNote(const juce::ValueTree& noteNode)
    {
        auto notesNode = projectTree.getChildWithName(IDs::NOTES);
        if (notesNode.isValid() && noteNode.isAChildOf(notesNode))
        {
            notesNode.removeChild(noteNode, &undoManager);
        }
    }

    void ProjectState::moveNote(juce::ValueTree& noteNode, double newStart, int newNoteNum)
    {
        if (noteNode.isValid())
        {
            noteNode.setProperty(IDs::start, newStart, &undoManager);
            noteNode.setProperty(IDs::noteNumber, newNoteNum, &undoManager);
        }
    }

    void ProjectState::resizeNote(juce::ValueTree& noteNode, double newLength)
    {
        if (noteNode.isValid())
        {
            noteNode.setProperty(IDs::length, newLength, &undoManager);
        }
    }

    void ProjectState::setNoteVelocity(juce::ValueTree& noteNode, int newVelocity)
    {
        if (noteNode.isValid())
        {
            noteNode.setProperty(IDs::velocity, newVelocity, &undoManager);
        }
    }

    void ProjectState::importMidiFile(const juce::File& midiFile)
    {
        juce::MidiFile midi;
        juce::FileInputStream stream(midiFile);
        
        if (stream.openedOk() && midi.readFrom(stream))
        {
            int timeFormat = midi.getTimeFormat();
            double ticksPerBeat = (timeFormat > 0) ? (double)timeFormat : 960.0;

            undoManager.beginNewTransaction("Import MIDI");
            clearNotes();
            
            auto notesNode = projectTree.getChildWithName(IDs::NOTES);
            
            // Use MidiMessageSequence to pair notes
            for (int t = 0; t < midi.getNumTracks(); ++t)
            {
                const auto* track = midi.getTrack(t);
                juce::MidiMessageSequence seq;
                seq.addSequence(*track, 0.0, 0.0, 0.0);
                seq.updateMatchedPairs();
                
                // Extract track name
                juce::String trackName = "Track " + juce::String(t + 1);
                for (int i = 0; i < track->getNumEvents(); ++i)
                {
                    const auto& msg = track->getEventPointer(i)->message;
                    if (msg.isTrackNameEvent())
                    {
                        trackName = msg.getTextFromTextMetaEvent();
                        if (trackName.isNotEmpty()) break;
                    }
                }
                
                // Create Track Node (optional, but good for metadata)
                // For now, we just ensure notes have the correct track index
                // We could store track names in a separate structure or property
                
                // Let's store track names in the MIXER node for persistence
                auto mixerNode = getMixerNode();
                if (mixerNode.isValid())
                {
                    // Find or create track node
                    juce::ValueTree trackNode;
                    for (auto child : mixerNode)
                    {
                        if (child.hasType(IDs::TRACK) && (int)child.getProperty(IDs::index) == t)
                        {
                            trackNode = child;
                            break;
                        }
                    }
                    
                    if (!trackNode.isValid())
                    {
                        trackNode = juce::ValueTree(IDs::TRACK);
                        trackNode.setProperty(IDs::index, t, nullptr);
                        mixerNode.addChild(trackNode, -1, &undoManager);
                    }
                    
                    trackNode.setProperty(IDs::name, trackName, &undoManager);
                }

                for (int i = 0; i < seq.getNumEvents(); ++i)
                {
                    auto* ev = seq.getEventPointer(i);
                    if (ev->message.isNoteOn())
                    {
                        double start = ev->message.getTimeStamp() / ticksPerBeat;
                        double length = 0.25; // Default
                        
                        if (auto* noteOff = ev->noteOffObject)
                            length = (noteOff->message.getTimeStamp() - ev->message.getTimeStamp()) / ticksPerBeat;
                            
                        addNote(ev->message.getNoteNumber(), 
                                start, 
                                length, 
                                ev->message.getVelocity(), 
                                t); // Use track index 't' as channel/track ID
                    }
                }
            }
        }
    }

    juce::MidiFile ProjectState::exportToMidiFile()
    {
        juce::MidiFile midi;
        midi.setTicksPerQuarterNote(960);
        
        juce::MidiMessageSequence seq;
        
        auto notesNode = projectTree.getChildWithName(IDs::NOTES);
        if (notesNode.isValid())
        {
            for (const auto& note : notesNode)
            {
                if (note.hasType(IDs::NOTE))
                {
                    int noteNum = note.getProperty(IDs::noteNumber);
                    double start = note.getProperty(IDs::start);
                    double length = note.getProperty(IDs::length);
                    int vel = note.getProperty(IDs::velocity);
                    int ch = note.getProperty(IDs::channel);
                    
                    // Convert beats to ticks
                    // juce::MidiFile expects ticks if we don't use setTicksPerQuarterNote?
                    // Actually, if we use addEvent with timestamp, we need to know the unit.
                    // If we setTicksPerQuarterNote(960), then timestamp 960 = 1 beat.
                    
                    int startTicks = (int)(start * 960.0);
                    int endTicks = (int)((start + length) * 960.0);
                    
                    seq.addEvent(juce::MidiMessage::noteOn(ch, noteNum, (juce::uint8)vel), startTicks);
                    seq.addEvent(juce::MidiMessage::noteOff(ch, noteNum), endTicks);
                }
            }
        }
        
        seq.sort();
        midi.addTrack(seq);
        
        return midi;
    }

    //==============================================================================
    // FX Chain Management
    void ProjectState::setFXChainForBus(const juce::String& busName, const juce::String& chainJSON)
    {
        auto fxChainsNode = getFXChainsNode();
        if (!fxChainsNode.isValid()) return;
        
        // Find or create bus node
        juce::ValueTree busNode;
        for (auto child : fxChainsNode)
        {
            if (child.hasType(IDs::FX_BUS) && child.getProperty(IDs::bus).toString() == busName)
            {
                busNode = child;
                break;
            }
        }
        
        if (!busNode.isValid())
        {
            busNode = juce::ValueTree(IDs::FX_BUS);
            busNode.setProperty(IDs::bus, busName, nullptr);
            fxChainsNode.addChild(busNode, -1, &undoManager);
        }
        
        undoManager.beginNewTransaction("Update FX Chain");
        
        // Clear existing FX units
        busNode.removeAllChildren(&undoManager);
        
        // Parse JSON and add FX units
        auto parsed = juce::JSON::parse(chainJSON);
        if (auto* chainArray = parsed.getArray())
        {
            for (const auto& fxVar : *chainArray)
            {
                juce::ValueTree fxNode(IDs::FX_UNIT);
                fxNode.setProperty(IDs::id, fxVar.getProperty("id", juce::Uuid().toString()), nullptr);
                fxNode.setProperty(IDs::type, fxVar.getProperty("type", ""), nullptr);
                fxNode.setProperty(IDs::displayName, fxVar.getProperty("display_name", ""), nullptr);
                fxNode.setProperty(IDs::enabled, (bool)fxVar.getProperty("enabled", true), nullptr);
                
                // Store parameters as JSON string
                if (auto* paramsObj = fxVar.getProperty("parameters", juce::var()).getDynamicObject())
                {
                    fxNode.setProperty(IDs::parameters, juce::JSON::toString(juce::var(paramsObj)), nullptr);
                }
                
                busNode.addChild(fxNode, -1, &undoManager);
            }
        }
    }
    
    juce::String ProjectState::getFXChainForBus(const juce::String& busName) const
    {
        auto fxChainsNode = projectTree.getChildWithName(IDs::FX_CHAINS);
        if (!fxChainsNode.isValid()) return "[]";
        
        // Find bus node
        for (const auto& child : fxChainsNode)
        {
            if (child.hasType(IDs::FX_BUS) && child.getProperty(IDs::bus).toString() == busName)
            {
                juce::Array<juce::var> chainArray;
                
                for (const auto& fxNode : child)
                {
                    if (fxNode.hasType(IDs::FX_UNIT))
                    {
                        auto* fxObj = new juce::DynamicObject();
                        fxObj->setProperty("id", fxNode.getProperty(IDs::id));
                        fxObj->setProperty("type", fxNode.getProperty(IDs::type));
                        fxObj->setProperty("display_name", fxNode.getProperty(IDs::displayName));
                        fxObj->setProperty("enabled", fxNode.getProperty(IDs::enabled));
                        
                        // Parse parameters back from JSON string
                        juce::String paramsStr = fxNode.getProperty(IDs::parameters).toString();
                        if (paramsStr.isNotEmpty())
                        {
                            fxObj->setProperty("parameters", juce::JSON::parse(paramsStr));
                        }
                        
                        chainArray.add(juce::var(fxObj));
                    }
                }
                
                return juce::JSON::toString(juce::var(chainArray));
            }
        }
        
        return "[]";
    }
    
    juce::String ProjectState::getAllFXChainsJSON() const
    {
        auto* root = new juce::DynamicObject();
        
        root->setProperty("master", juce::JSON::parse(getFXChainForBus("master")));
        root->setProperty("drums", juce::JSON::parse(getFXChainForBus("drums")));
        root->setProperty("bass", juce::JSON::parse(getFXChainForBus("bass")));
        root->setProperty("melodic", juce::JSON::parse(getFXChainForBus("melodic")));
        
        return juce::JSON::toString(juce::var(root));
    }

    //==============================================================================
    // ValueTree::Listener overrides
    void ProjectState::valueTreePropertyChanged(juce::ValueTree& treeWhosePropertyHasChanged, const juce::Identifier& property)
    {
        // Broadcast changes if needed, or rely on ValueTree listeners elsewhere
        isDirty = true;
        // Broadcast changes if needed, or rely on ValueTree listeners elsewhere
        DBG("Property changed: " << property.toString());
    }

    void ProjectState::valueTreeChildAdded(juce::ValueTree& parentTree, juce::ValueTree& childWhichHasBeenAdded) { isDirty = true; }
    void ProjectState::valueTreeChildRemoved(juce::ValueTree& parentTree, juce::ValueTree& childWhichHasBeenRemoved, int indexFromWhichChildWasRemoved) { isDirty = true; }
    void ProjectState::valueTreeChildOrderChanged(juce::ValueTree& parentTreeWhichHasChanged, int oldIndex, int newIndex) { isDirty = true; }
    void ProjectState::valueTreeParentChanged(juce::ValueTree& treeWhoseParentHasChanged) { isDirty = true; }
}
