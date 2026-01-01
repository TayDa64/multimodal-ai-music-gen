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
        static const juce::Identifier mute("mute");
        static const juce::Identifier solo("solo");
        
        static const juce::Identifier path("path");
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
        
        // Generation Data
        void setGenerationData(const juce::String& prompt, int bpm, const juce::String& key, const juce::String& genre);
        void setGeneratedFiles(const juce::String& midiPath, const juce::String& audioPath);
        
        // Mixer Data
        void setTrackVolume(int trackIndex, float volume);
        void setTrackPan(int trackIndex, float pan);
        void setTrackMute(int trackIndex, bool mute);
        void setTrackSolo(int trackIndex, bool solo);
        
        // Instrument Data
        void setInstrument(int trackIndex, const juce::String& name, const juce::String& path);

        //==============================================================================
        // Note Editing
        void clearNotes();
        void addNote(int noteNum, double startBeats, double lengthBeats, int velocity, int channel);
        void deleteNote(const juce::ValueTree& noteNode);
        void moveNote(juce::ValueTree& noteNode, double newStart, int newNoteNum);
        void resizeNote(juce::ValueTree& noteNode, double newLength);
        void setNoteVelocity(juce::ValueTree& noteNode, int newVelocity);
        
        // Import/Export
        void importMidiFile(const juce::File& midiFile);
        juce::MidiFile exportToMidiFile();

        juce::ValueTree getMixerNode();
        juce::ValueTree getTrackNode(int index);
        juce::ValueTree getInstrumentsNode();

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
        bool isDirty = false;

        void createDefaultProject();
        
        JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(ProjectState)
    };
}
