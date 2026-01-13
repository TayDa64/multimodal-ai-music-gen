/*
  ==============================================================================

    AppState.h
    
    Global application state management with listener pattern.

  ==============================================================================
*/

#pragma once

#include <juce_core/juce_core.h>
#include <juce_graphics/juce_graphics.h>
#include <juce_data_structures/juce_data_structures.h>
#include "../Project/ProjectState.h"

//==============================================================================
// Progress update structure
struct GenerationProgress
{
    juce::String stepName;
    float progress = 0.0f;
    juce::String message;
};

//==============================================================================
// Current generation state
struct GenerationState
{
    juce::String prompt;
    int bpm = 90;
    juce::String key;
    juce::String genre;
    juce::File midiFile;
    juce::File audioFile;
};

//==============================================================================
/**
    Application state manager with listener pattern for UI updates.
*/
class AppState
{
public:
    //==============================================================================
    AppState();
    ~AppState();
    
    //==============================================================================
    /** Listener interface for state change notifications */
    class Listener
    {
    public:
        virtual ~Listener() = default;
        virtual void onGenerationStarted() {}
        virtual void onGenerationFinished() {}
        virtual void onProgressChanged(const GenerationProgress& progress) { juce::ignoreUnused(progress); }
        virtual void onGenerationProgress(const GenerationProgress& progress) { juce::ignoreUnused(progress); }
        virtual void onGenerationCompleted(const juce::File& outputFile) { juce::ignoreUnused(outputFile); }
        virtual void onGenerationError(const juce::String& error) { juce::ignoreUnused(error); }
        virtual void onConnectionStatusChanged(bool connected) { juce::ignoreUnused(connected); }
    };
    
    void addListener(Listener* listener);
    void removeListener(Listener* listener);
    
    //==============================================================================
    // Notify listeners
    void notifyGenerationStarted() { listeners.call(&Listener::onGenerationStarted); }
    void notifyGenerationProgress(const GenerationProgress& p) { listeners.call(&Listener::onGenerationProgress, p); }
    void notifyGenerationCompleted(const juce::File& f) { listeners.call(&Listener::onGenerationCompleted, f); }
    void notifyGenerationError(const juce::String& e) { listeners.call(&Listener::onGenerationError, e); }
    void notifyConnectionStatusChanged(bool c) { listeners.call(&Listener::onConnectionStatusChanged, c); }
    
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
    void newProject();
    bool loadProject(const juce::File& file);
    bool saveProject();
    bool saveProjectAs(const juce::File& file);
    
    bool hasUnsavedChanges() const { return unsavedChanges; }
    juce::File getCurrentProjectFile() const { return currentProjectFile; }
    
    //==============================================================================
    // Recent files
    juce::StringArray getRecentFiles() const;
    void addRecentFile(const juce::File& file);
    void clearRecentFiles();
    
    //==============================================================================
    // Generation parameters
    juce::String getPrompt() const;
    void setPrompt(const juce::String& p);
    
    int getBPM() const;
    void setBPM(int b);
    
    juce::String getKey() const;
    void setKey(const juce::String& k);
    
    int getDurationBars() const;
    void setDurationBars(int bars);

    int getNumTakes() const;
    void setNumTakes(int takes);
    
    bool isGenerating() const;
    void setGenerating(bool g);
    
    juce::File getOutputFile() const;
    void setOutputFile(const juce::File& f);
    
    //==============================================================================
    // Progress management
    void setProgress(const GenerationProgress& progress);
    GenerationProgress getProgress() const;
    
    //==============================================================================
    // Path settings
    juce::String getLastInstrumentPath() const;
    void setLastInstrumentPath(const juce::String& path);
    
    juce::String getLastOutputPath() const;
    void setLastOutputPath(const juce::String& path);
    
    //==============================================================================
    // Server settings
    int getServerPort() const;
    void setServerPort(int port);

    //==============================================================================
    // Project State Access
    Project::ProjectState& getProjectState() { return projectState; }
    
private:
    //==============================================================================
    juce::ListenerList<Listener> listeners;
    std::unique_ptr<juce::PropertiesFile> settings;
    
    // Project state
    Project::ProjectState projectState;
    juce::File currentProjectFile;
    bool unsavedChanges = false;
    
    // Current generation
    GenerationState currentGeneration;
    int durationBars = 8;
    int numTakes = 1;
    bool generating = false;
    GenerationProgress currentProgress;
    
    //==============================================================================
    juce::File getSettingsFile() const;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(AppState)
};
