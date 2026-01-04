/*
  ==============================================================================

    PromptHistoryManager.h
    
    Manages prompt history and favorites for quick re-generation.
    Implements Milestone 0.9 from TODOtasks.md:
    - Recent prompts dropdown
    - Star/favorite prompts
    - Quick re-generate with previous prompt
    - Persist to disk

  ==============================================================================
*/

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include <juce_data_structures/juce_data_structures.h>
#include <vector>
#include <memory>

//==============================================================================
/**
    A single entry in the prompt history.
*/
struct PromptEntry
{
    juce::String prompt;              // The full prompt text
    juce::String genre;               // Genre used when generated
    int bpm = 120;                    // BPM when generated
    juce::String key;                 // Key when generated
    juce::Time timestamp;             // When it was used
    bool isFavorite = false;          // Whether user starred this
    int useCount = 1;                 // Number of times used
    juce::String outputFile;          // Optional: associated output file
    
    // Serialization
    juce::var toVar() const
    {
        auto* obj = new juce::DynamicObject();
        obj->setProperty("prompt", prompt);
        obj->setProperty("genre", genre);
        obj->setProperty("bpm", bpm);
        obj->setProperty("key", key);
        obj->setProperty("timestamp", timestamp.toMilliseconds());
        obj->setProperty("isFavorite", isFavorite);
        obj->setProperty("useCount", useCount);
        obj->setProperty("outputFile", outputFile);
        return juce::var(obj);
    }
    
    static PromptEntry fromVar(const juce::var& v)
    {
        PromptEntry entry;
        if (auto* obj = v.getDynamicObject())
        {
            entry.prompt = obj->getProperty("prompt").toString();
            entry.genre = obj->getProperty("genre").toString();
            entry.bpm = (int)obj->getProperty("bpm");
            entry.key = obj->getProperty("key").toString();
            entry.timestamp = juce::Time((juce::int64)obj->getProperty("timestamp"));
            entry.isFavorite = (bool)obj->getProperty("isFavorite");
            entry.useCount = (int)obj->getProperty("useCount");
            entry.outputFile = obj->getProperty("outputFile").toString();
        }
        return entry;
    }
    
    // For sorting - favorites first, then by timestamp (newest first)
    bool operator<(const PromptEntry& other) const
    {
        if (isFavorite != other.isFavorite)
            return isFavorite > other.isFavorite;  // Favorites first
        return timestamp > other.timestamp;         // Newest first
    }
};

//==============================================================================
/**
    Manages prompt history with persistence and favorites.
    
    Features:
    - Automatic saving/loading from disk
    - Duplicate detection (reusing prompt updates timestamp and count)
    - Favorites that persist across sessions
    - Maximum history size with automatic cleanup
*/
class PromptHistoryManager
{
public:
    //==========================================================================
    static constexpr int MaxHistorySize = 100;    // Maximum prompts to store
    static constexpr int MaxDisplaySize = 20;     // Max shown in dropdown
    
    //==========================================================================
    PromptHistoryManager();
    ~PromptHistoryManager();
    
    //==========================================================================
    /** Add a prompt to history (or update if exists) */
    void addPrompt(const juce::String& prompt, 
                   const juce::String& genre = "",
                   int bpm = 120,
                   const juce::String& key = "C",
                   const juce::String& outputFile = "");
    
    /** Toggle favorite status for a prompt */
    void toggleFavorite(const juce::String& prompt);
    
    /** Check if a prompt is favorited */
    bool isFavorite(const juce::String& prompt) const;
    
    /** Remove a specific prompt from history */
    void removePrompt(const juce::String& prompt);
    
    /** Clear all non-favorite history */
    void clearHistory();
    
    /** Clear everything including favorites */
    void clearAll();
    
    //==========================================================================
    /** Get all prompts (sorted: favorites first, then by recency) */
    std::vector<PromptEntry> getAllPrompts() const;
    
    /** Get recent prompts for dropdown (limited count) */
    std::vector<PromptEntry> getRecentPrompts(int maxCount = MaxDisplaySize) const;
    
    /** Get only favorited prompts */
    std::vector<PromptEntry> getFavorites() const;
    
    /** Get history size */
    int getHistorySize() const { return (int)history.size(); }
    
    /** Get favorites count */
    int getFavoritesCount() const;
    
    //==========================================================================
    /** Search history by partial match */
    std::vector<PromptEntry> searchPrompts(const juce::String& searchText) const;
    
    /** Find exact prompt entry (or nullptr if not found) */
    const PromptEntry* findPrompt(const juce::String& prompt) const;
    
    //==========================================================================
    /** Save history to file */
    void saveToFile(const juce::File& file);
    
    /** Load history from file */
    void loadFromFile(const juce::File& file);
    
    /** Get default history file location */
    static juce::File getDefaultHistoryFile();
    
    //==========================================================================
    /** Export favorites to JSON (for sharing) */
    juce::String exportFavoritesToJSON() const;
    
    /** Import favorites from JSON */
    void importFavoritesFromJSON(const juce::String& json);
    
private:
    //==========================================================================
    std::vector<PromptEntry> history;
    mutable juce::CriticalSection lock;
    
    // Auto-save
    juce::File historyFile;
    bool autoSaveEnabled = true;
    
    void autoSave();
    void enforceMaxSize();
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(PromptHistoryManager)
};

//==============================================================================
/**
    UI Component for prompt history dropdown/popup.
    
    Shows recent prompts with favorites at top, allows:
    - Click to select prompt
    - Star icon to toggle favorite
    - Delete button to remove
*/
class PromptHistoryComponent : public juce::Component,
                                public juce::ListBoxModel
{
public:
    //==========================================================================
    PromptHistoryComponent(PromptHistoryManager& manager);
    ~PromptHistoryComponent() override;
    
    //==========================================================================
    /** Listener for prompt selection */
    class Listener
    {
    public:
        virtual ~Listener() = default;
        virtual void promptSelected(const PromptEntry& entry) = 0;
    };
    
    void addListener(Listener* listener);
    void removeListener(Listener* listener);
    
    //==========================================================================
    void paint(juce::Graphics& g) override;
    void resized() override;
    
    /** Refresh the displayed list */
    void refresh();
    
    //==========================================================================
    // ListBoxModel
    int getNumRows() override;
    void paintListBoxItem(int rowNumber, juce::Graphics& g, int width, int height, bool rowIsSelected) override;
    void listBoxItemClicked(int row, const juce::MouseEvent& event) override;
    void listBoxItemDoubleClicked(int row, const juce::MouseEvent& event) override;
    juce::Component* refreshComponentForRow(int rowNumber, bool isRowSelected, juce::Component* existingComponentToUpdate) override;
    
private:
    //==========================================================================
    PromptHistoryManager& historyManager;
    juce::ListenerList<Listener> listeners;
    
    std::unique_ptr<juce::ListBox> listBox;
    std::vector<PromptEntry> displayedPrompts;
    
    void notifySelection(int row);
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(PromptHistoryComponent)
};

//==============================================================================
/**
    Row component for the history list with favorite toggle and delete buttons.
*/
class PromptHistoryRow : public juce::Component
{
public:
    PromptHistoryRow(PromptHistoryManager& manager);
    
    void setEntry(const PromptEntry& entry);
    void paint(juce::Graphics& g) override;
    void resized() override;
    
    std::function<void()> onSelected;
    std::function<void()> onFavoriteToggled;
    std::function<void()> onDeleteRequested;
    
private:
    PromptHistoryManager& historyManager;
    PromptEntry currentEntry;
    
    juce::TextButton favoriteButton;
    juce::TextButton deleteButton;
    
    void updateFavoriteButton();
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(PromptHistoryRow)
};
