/*
  ==============================================================================

    AppState.h
    
    Global application state management.
    Handles settings persistence, project state, and undo/redo.

  ==============================================================================
*/

#pragma once

#include <JuceHeader.h>

//==============================================================================
/**
    Application state manager.
    
    Manages:
    - User preferences (window position, last used paths)
    - Current project state
    - Undo/redo history
*/
class AppState
{
public:
    //==============================================================================
    AppState();
    ~AppState();
    
    //==============================================================================
    // Settings persistence
    void loadSettings();
    void saveSettings();
    
    //==============================================================================
    // Window bounds
    juce::Rectangle<int> getWindowBounds() const;
    void setWindowBounds(const juce::Rectangle<int>& bounds);
    
    //==============================================================================
    // Project management
    bool hasUnsavedChanges() const { return unsavedChanges; }
    void setUnsavedChanges(bool hasChanges) { unsavedChanges = hasChanges; }
    
    void newProject();
    bool loadProject(const juce::File& file);
    bool saveProject();
    bool saveProjectAs(const juce::File& file);
    
    juce::File getCurrentProjectFile() const { return currentProjectFile; }
    
    //==============================================================================
    // Recent files
    juce::StringArray getRecentFiles() const;
    void addRecentFile(const juce::File& file);
    void clearRecentFiles();
    
    //==============================================================================
    // User preferences
    juce::String getLastInstrumentPath() const;
    void setLastInstrumentPath(const juce::String& path);
    
    juce::String getLastOutputPath() const;
    void setLastOutputPath(const juce::String& path);
    
    int getServerPort() const;
    void setServerPort(int port);
    
    //==============================================================================
    // Current generation state
    struct GenerationState
    {
        juce::String prompt;
        int bpm = 0;
        juce::String key;
        juce::String genre;
        juce::StringArray instrumentPaths;
        
        juce::File midiFile;
        juce::File audioFile;
    };
    
    GenerationState& getCurrentGeneration() { return currentGeneration; }
    const GenerationState& getCurrentGeneration() const { return currentGeneration; }
    
private:
    //==============================================================================
    std::unique_ptr<juce::PropertiesFile> settings;
    juce::File currentProjectFile;
    bool unsavedChanges = false;
    
    GenerationState currentGeneration;
    
    //==============================================================================
    juce::File getSettingsFile() const;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(AppState)
};
