/*
  ==============================================================================

    ProjectState.h
    
    Manages the project document state using juce::ValueTree and UndoManager.
    Handles persistence (.mmg files) and state modification.

  ==============================================================================
*/

#pragma once

#include <juce_core/juce_core.h>
#include <juce_data_structures/juce_data_structures.h>
#include <juce_audio_formats/juce_audio_formats.h>

namespace Project
{
    //==============================================================================
    // Data Model Constants
    namespace IDs
    {
        static const juce::Identifier PROJECT("PROJECT");
        static const juce::Identifier GENERATION("GENERATION");
        static const juce::Identifier MIXER("MIXER");
        static const juce::Identifier TRACK("TRACK");
        static const juce::Identifier INSTRUMENTS("INSTRUMENTS");
        static const juce::Identifier INSTRUMENT("INSTRUMENT");
        
        // FX Chain
        static const juce::Identifier FX_CHAINS("FX_CHAINS");
        static const juce::Identifier FX_BUS("FX_BUS");
        static const juce::Identifier FX_UNIT("FX_UNIT");
        static const juce::Identifier type("type");
        static const juce::Identifier displayName("displayName");
        static const juce::Identifier enabled("enabled");
        static const juce::Identifier parameters("parameters");
        
        // Note Data
        static const juce::Identifier NOTES("NOTES");
        static const juce::Identifier NOTE("NOTE");
        static const juce::Identifier noteNumber("n");
        static const juce::Identifier velocity("v");
        static const juce::Identifier start("s");
        static const juce::Identifier length("l");
        static const juce::Identifier channel("c");
        
        // Properties
        static const juce::Identifier version("version");
        static const juce::Identifier bpm("bpm");
        static const juce::Identifier key("key");
        static const juce::Identifier genre("genre");
        static const juce::Identifier prompt("prompt");
        static const juce::Identifier midiPath("midiPath");
        static const juce::Identifier audioPath("audioPath");
        
        static const juce::Identifier index("index");
        static const juce::Identifier name("name");
        static const juce::Identifier volume("volume");
        static const juce::Identifier pan("pan");
        static const juce::Identifier stereoWidth("stereoWidth");
        static const juce::Identifier mute("mute");
        static const juce::Identifier solo("solo");

        // Instrument selection (UI-level id, e.g. "default_sine")
        static const juce::Identifier instrumentId("instrumentId");

        // Default Synth (per-track)
        static const juce::Identifier defaultSynthWaveform("defaultSynthWaveform");
        static const juce::Identifier defaultSynthAttack("defaultSynthAttack");
        static const juce::Identifier defaultSynthRelease("defaultSynthRelease");
        static const juce::Identifier defaultSynthCutoff("defaultSynthCutoff");
        static const juce::Identifier defaultSynthLfoRate("defaultSynthLfoRate");
        static const juce::Identifier defaultSynthLfoDepth("defaultSynthLfoDepth");
        
        static const juce::Identifier path("path");
        static const juce::Identifier id("id");
        static const juce::Identifier bus("bus");
    }

    //==============================================================================
    class ProjectState : public juce::ValueTree::Listener
    {
    public:
        ProjectState();
        ~ProjectState() override;

        //==============================================================================
        // File Management
        void newProject();
        bool loadProject(const juce::File& file);
        bool saveProject(const juce::File& file);
        
        /**
         * Collect all referenced files (audio, MIDI, instruments) into a subfolder
         * next to the project file, and update paths to be relative.
         * Creates: <projectName>_files/{midi,audio,instruments,soundfonts}/
         * @param projectFile The .mmg project file
         * @returns Number of files successfully collected
         */
        int collectAndCopy(const juce::File& projectFile);
        
        juce::File getCurrentFile() const { return currentFile; }
        bool hasUnsavedChanges() const { return isDirty; }

        //==============================================================================
        // Undo/Redo
        juce::UndoManager& getUndoManager() { return undoManager; }
        void undo() { undoManager.undo(); }
        void redo() { undoManager.redo(); }
        
        //==============================================================================
        // Accessors
        juce::ValueTree& getState() { return projectTree; }

        //==============================================================================
        // Listener management
        // Use these instead of getState().addListener/removeListener so listeners survive
        // loadProject() swapping the underlying ValueTree.
        void addStateListener(juce::ValueTree::Listener* listener);
        void removeStateListener(juce::ValueTree::Listener* listener);
        
        // Generation Data
        void setGenerationData(const juce::String& prompt, int bpm, const juce::String& key, const juce::String& genre);
        void setGeneratedFiles(const juce::String& midiPath, const juce::String& audioPath);
        
        // Mixer Data
        void setTrackVolume(int trackIndex, float volume);
        void setTrackPan(int trackIndex, float pan);
        void setTrackMute(int trackIndex, bool mute);
        void setTrackSolo(int trackIndex, bool solo);
        void setTrackStereoWidth(int trackIndex, float width);
        
        // Instrument Data
        void setInstrument(int trackIndex, const juce::String& name, const juce::String& path);

        //==============================================================================
        // Note Editing
        void clearNotes();
        void addNote(int noteNum, double startBeats, double lengthBeats, int velocity, int channel);
        void deleteNote(const juce::ValueTree& noteNode);
        void deleteNotes(const juce::Array<juce::ValueTree>& noteNodes);  // Batch delete
        void moveNote(juce::ValueTree& noteNode, double newStart, int newNoteNum);
        void resizeNote(juce::ValueTree& noteNode, double newLength);
        void setNoteVelocity(juce::ValueTree& noteNode, int newVelocity);

        // Track-scoped Note Utilities (for take comping)
        juce::ValueTree copyNotesForTrack(int trackIndex) const;
        void restoreNotesForTrack(int trackIndex, const juce::ValueTree& snapshot);
        bool replaceNotesForTrackFromMidiFile(int trackIndex, const juce::File& midiFile);
        
        // Import/Export
        void importMidiFile(const juce::File& midiFile);
        juce::MidiFile exportToMidiFile();
        
        // Debug: last import stats
        juce::String getLastImportStats() const { return lastImportStats; }

        juce::ValueTree getMixerNode();
        juce::ValueTree getTrackNode(int index);
        juce::ValueTree getInstrumentsNode();
        juce::ValueTree getFXChainsNode();
        
        //==============================================================================
        // FX Chain Management
        /**
         * Set the FX chain for a specific bus.
         * @param busName "master", "drums", "bass", or "melodic"
         * @param chainJSON JSON array of FX units
         */
        void setFXChainForBus(const juce::String& busName, const juce::String& chainJSON);
        
        /**
         * Get the FX chain for a specific bus.
         * @param busName "master", "drums", "bass", or "melodic"
         * @return JSON string of the FX chain array
         */
        juce::String getFXChainForBus(const juce::String& busName) const;
        
        /**
         * Get all FX chains as a single JSON object.
         * @return JSON object with keys: master, drums, bass, melodic
         */
        juce::String getAllFXChainsJSON() const;

        //==============================================================================
        // ValueTree::Listener overrides
        void valueTreePropertyChanged(juce::ValueTree& treeWhosePropertyHasChanged, const juce::Identifier& property) override;
        void valueTreeChildAdded(juce::ValueTree& parentTree, juce::ValueTree& childWhichHasBeenAdded) override;
        void valueTreeChildRemoved(juce::ValueTree& parentTree, juce::ValueTree& childWhichHasBeenRemoved, int indexFromWhichChildWasRemoved) override;
        void valueTreeChildOrderChanged(juce::ValueTree& parentTreeWhichHasChanged, int oldIndex, int newIndex) override;
        void valueTreeParentChanged(juce::ValueTree& treeWhoseParentHasChanged) override;

    private:
        juce::ValueTree projectTree;
        juce::UndoManager undoManager;
        juce::File currentFile;
        juce::String lastImportStats;  // Debug: stores last import result
        bool isDirty = false;

        juce::Array<juce::ValueTree::Listener*> externalStateListeners;

        void createDefaultProject();
        void ensureTrackDefaults(juce::ValueTree& trackNode);
        
        JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(ProjectState)
    };
}
