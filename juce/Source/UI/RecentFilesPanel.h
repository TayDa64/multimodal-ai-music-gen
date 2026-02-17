/*
  ==============================================================================

    RecentFilesPanel.h
    
    Displays recent MIDI/audio files from the output folder for easy access.
    Users can click to load and play files directly.
    
    Features:
    - File management: delete, export, reveal in explorer
    - Right-click context menu for file operations
    - Auto-refresh when new files appear

  ==============================================================================
*/

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include "../Application/AppState.h"
#include "../Audio/AudioEngine.h"

//==============================================================================
/**
    Panel showing recent generated files from the output folder.
    
    Features:
    - Scans output directory for .mid files
    - Shows file info (name, date, size)
    - Click to load into player
    - Right-click context menu for file operations
    - Auto-refreshes when new files appear
*/
class RecentFilesPanel : public juce::Component,
                         public juce::Timer,
                         public juce::FileBrowserListener
{
public:
    //==============================================================================
    struct FileInfo
    {
        juce::File file;
        juce::String displayName;    // Formatted name (genre, bpm, key)
        juce::String dateString;     // "Today 2:30 PM" or "Dec 9, 2025"
        juce::String sizeString;     // "12 KB"
        juce::Time lastModified;

        // Optional rich metadata (best-effort from project_metadata.json)
        juce::String promptSnippet;
        juce::String generatedAtIso;
        juce::int64 seed = 0;
        
        // Parsed from filename
        juce::String genre;
        int bpm = 0;
        juce::String key;
    };
    
    //==============================================================================
    class Listener
    {
    public:
        virtual ~Listener() = default;
        virtual void fileSelected(const juce::File& file) = 0;

        // Optional: request analysis of an audio file via OSC
        virtual void analyzeFileRequested(const juce::File& file) { juce::ignoreUnused(file); }
    };
    
    //==============================================================================
    RecentFilesPanel(AppState& state, mmg::AudioEngine& engine);
    ~RecentFilesPanel() override;
    
    //==============================================================================
    void paint(juce::Graphics& g) override;
    void resized() override;
    
    //==============================================================================
    /** Set the directory to scan for files */
    void setOutputDirectory(const juce::File& directory);
    
    /** Manually refresh the file list */
    void refresh();
    
    /** Get the number of files found */
    int getFileCount() const { return files.size(); }
    
    //==============================================================================
    void addListener(Listener* listener);
    void removeListener(Listener* listener);
    
    //==============================================================================
    // Timer callback for auto-refresh
    void timerCallback() override;
    
    // FileBrowserListener (not currently used but available)
    void selectionChanged() override {}
    void fileClicked(const juce::File&, const juce::MouseEvent&) override {}
    void fileDoubleClicked(const juce::File&) override {}
    void browserRootChanged(const juce::File&) override {}

private:
    //==============================================================================
    class FileListBox : public juce::ListBox,
                        public juce::ListBoxModel
    {
    public:
        FileListBox(RecentFilesPanel& owner);
        
        // ListBoxModel
        int getNumRows() override;
        void paintListBoxItem(int rowNumber, juce::Graphics& g, 
                             int width, int height, bool rowIsSelected) override;
        void listBoxItemClicked(int row, const juce::MouseEvent& e) override;
        void listBoxItemDoubleClicked(int row, const juce::MouseEvent& e) override;
        juce::String getTooltipForRow(int row) override;
        
    private:
        RecentFilesPanel& owner;
    };
    
    //==============================================================================
    AppState& appState;
    mmg::AudioEngine& audioEngine;
    juce::ListenerList<Listener> listeners;
    
    //==============================================================================
    // UI Components
    juce::Label titleLabel { {}, "Recent Files" };
    juce::TextButton refreshButton { juce::CharPointer_UTF8("\xe2\x9f\xb3") }; // ⟳ refresh icon
    juce::TextButton openFolderButton { juce::CharPointer_UTF8("\xf0\x9f\x93\x82") }; // 📂 folder icon
    juce::TextButton deleteButton { juce::CharPointer_UTF8("\xf0\x9f\x97\x91") }; // 🗑 delete icon
    std::unique_ptr<FileListBox> fileList;
    juce::Label emptyLabel { {}, "No files found.\nGenerate some music!" };
    
    //==============================================================================
    // State
    juce::File outputDirectory;
    juce::Array<FileInfo> files;
    juce::Time lastScanTime;
    int selectedRow = -1;
    int lastFileCount = 0;  // Track file count for change detection
    
    //==============================================================================
    void scanDirectory();
    FileInfo parseFileInfo(const juce::File& file);
    juce::String formatRelativeDate(const juce::Time& time);
    juce::String formatFileSize(juce::int64 bytes);
    void loadSelectedFile();
    
    // File management operations
    void showContextMenu(int row);
    void deleteSelectedFile();
    void exportSelectedFile();
    void exportToWav();
    void revealInExplorer();
    void renameSelectedFile();
    void deleteAllFiles();
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(RecentFilesPanel)
};
