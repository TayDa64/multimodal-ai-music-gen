/*
  ==============================================================================

    InstrumentBrowserPanel.h
    
    Instrument browser with category-based navigation and preview.
    Part of NB Phase 2: JUCE Framework & UI Standardization.

  ==============================================================================
*/

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include <juce_audio_formats/juce_audio_formats.h>
#include <juce_audio_devices/juce_audio_devices.h>
#include <juce_audio_utils/juce_audio_utils.h>
#include "../Application/AppState.h"

//==============================================================================
/**
    Instrument metadata from the Python backend.
*/
struct InstrumentInfo
{
    juce::String id;              // Unique identifier
    juce::String name;            // Display name
    juce::String filename;        // Original filename
    juce::String path;            // Relative path
    juce::String absolutePath;    // Full system path
    
    juce::String category;        // Primary category (drums, bass, keys, etc.)
    juce::String subcategory;     // Subcategory (kicks, snares, piano, etc.)
    
    juce::String key;             // Musical key (e.g., "Aminor")
    float bpm = 0.0f;             // BPM for loops
    float durationSec = 0.0f;     // Duration in seconds
    
    juce::StringArray tags;       // Descriptive tags
    juce::StringArray genreHints; // Genre affinity
    
    int fileSizeBytes = 0;
    
    bool favorite = false;
    int playCount = 0;
    
    /** Parse from JSON object */
    static InstrumentInfo fromJSON(const juce::var& json)
    {
        InstrumentInfo info;
        info.id = json.getProperty("id", "").toString();
        info.name = json.getProperty("name", "").toString();
        info.filename = json.getProperty("filename", "").toString();
        info.path = json.getProperty("path", "").toString();
        info.absolutePath = json.getProperty("absolute_path", "").toString();
        info.category = json.getProperty("category", "").toString();
        info.subcategory = json.getProperty("subcategory", "").toString();
        info.key = json.getProperty("key", "").toString();
        info.bpm = static_cast<float>(json.getProperty("bpm", 0.0));
        info.durationSec = static_cast<float>(json.getProperty("duration_ms", 0.0)) / 1000.0f;
        info.fileSizeBytes = static_cast<int>(json.getProperty("file_size_bytes", 0));
        info.favorite = static_cast<bool>(json.getProperty("favorite", false));
        info.playCount = static_cast<int>(json.getProperty("play_count", 0));
        
        if (auto* tagsArray = json.getProperty("tags", juce::var()).getArray())
        {
            for (const auto& tag : *tagsArray)
                info.tags.add(tag.toString());
        }
        
        if (auto* genresArray = json.getProperty("genre_hints", juce::var()).getArray())
        {
            for (const auto& genre : *genresArray)
                info.genreHints.add(genre.toString());
        }
        
        return info;
    }
};

//==============================================================================
/**
    Category definition for the instrument browser.
*/
struct InstrumentCategory
{
    juce::String name;
    juce::String displayName;
    juce::String icon;
    juce::StringArray subcategories;
    int instrumentCount = 0;
    
    /** Parse from JSON */
    static InstrumentCategory fromJSON(const juce::String& categoryName, const juce::var& json)
    {
        InstrumentCategory cat;
        cat.name = categoryName;
        cat.displayName = json.getProperty("display_name", categoryName).toString();
        cat.icon = json.getProperty("icon", "").toString();
        cat.instrumentCount = json.getProperty("count", 0);
        
        if (auto* subcats = json.getProperty("subcategories", juce::var()).getArray())
        {
            for (const auto& subcat : *subcats)
                cat.subcategories.add(subcat.toString());
        }
        
        return cat;
    }
};

//==============================================================================
/**
    Single instrument card for the browser list.
*/
class InstrumentCard : public juce::Component
{
public:
    InstrumentCard(const InstrumentInfo& info);
    
    void paint(juce::Graphics& g) override;
    void resized() override;
    void mouseEnter(const juce::MouseEvent&) override;
    void mouseExit(const juce::MouseEvent&) override;
    void mouseDown(const juce::MouseEvent&) override;
    void mouseDoubleClick(const juce::MouseEvent&) override;
    
    const InstrumentInfo& getInfo() const { return instrumentInfo; }
    
    void setSelected(bool selected);
    bool isSelected() const { return selected; }
    
    /** Listener for card events */
    class Listener
    {
    public:
        virtual ~Listener() = default;
        virtual void instrumentCardClicked(InstrumentCard* card) = 0;
        virtual void instrumentCardDoubleClicked(InstrumentCard* card) = 0;
    };
    
    void setListener(Listener* l) { listener = l; }
    
private:
    InstrumentInfo instrumentInfo;
    bool hovered = false;
    bool selected = false;
    Listener* listener = nullptr;
    
    juce::TextButton favoriteButton { "★" };
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(InstrumentCard)
};

//==============================================================================
/**
    List of instrument cards with scrolling.
*/
class InstrumentListComponent : public juce::Component,
                                 public InstrumentCard::Listener
{
public:
    InstrumentListComponent();
    ~InstrumentListComponent() override;
    
    void resized() override;
    
    void setInstruments(const juce::Array<InstrumentInfo>& instruments);
    void clearInstruments();
    
    const InstrumentInfo* getSelectedInstrument() const;
    void clearSelection();
    
    /** Listener for selection changes */
    class Listener
    {
    public:
        virtual ~Listener() = default;
        virtual void instrumentSelected(const InstrumentInfo& info) = 0;
        virtual void instrumentActivated(const InstrumentInfo& info) = 0;
    };
    
    void addListener(Listener* l) { listeners.add(l); }
    void removeListener(Listener* l) { listeners.remove(l); }
    
private:
    void instrumentCardClicked(InstrumentCard* card) override;
    void instrumentCardDoubleClicked(InstrumentCard* card) override;
    void updateLayout();
    
    juce::OwnedArray<InstrumentCard> cards;
    InstrumentCard* selectedCard = nullptr;
    juce::ListenerList<Listener> listeners;
    
    juce::Viewport viewport;
    juce::Component contentComponent;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(InstrumentListComponent)
};

//==============================================================================
/**
    Category tab bar for switching instrument categories.
*/
class CategoryTabBar : public juce::Component
{
public:
    CategoryTabBar();
    
    void paint(juce::Graphics& g) override;
    void resized() override;
    
    void setCategories(const juce::Array<InstrumentCategory>& categories);
    void setSelectedCategory(const juce::String& categoryName);
    juce::String getSelectedCategory() const;
    
    /** Listener for tab changes */
    class Listener
    {
    public:
        virtual ~Listener() = default;
        virtual void categorySelected(const juce::String& category) = 0;
    };
    
    void addListener(Listener* l) { listeners.add(l); }
    void removeListener(Listener* l) { listeners.remove(l); }
    
private:
    void updateTabs();
    
    juce::Array<InstrumentCategory> categories;
    juce::String selectedCategory;
    juce::OwnedArray<juce::TextButton> tabButtons;
    juce::ListenerList<Listener> listeners;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(CategoryTabBar)
};

//==============================================================================
/**
    Sample preview panel with waveform and playback controls.
*/
class SamplePreviewPanel : public juce::Component,
                           public juce::Button::Listener,
                           public juce::Timer
{
public:
    SamplePreviewPanel(juce::AudioDeviceManager& deviceManager);
    ~SamplePreviewPanel() override;
    
    void paint(juce::Graphics& g) override;
    void resized() override;
    
    void setInstrument(const InstrumentInfo& info);
    void clearInstrument();
    
    void play();
    void stop();
    bool isPlaying() const;
    
private:
    void buttonClicked(juce::Button* button) override;
    void timerCallback() override;
    void loadAudioFile(const juce::String& path);
    
    juce::AudioDeviceManager& audioDeviceManager;
    
    // Audio playback
    juce::AudioFormatManager formatManager;
    std::unique_ptr<juce::AudioFormatReaderSource> readerSource;
    juce::AudioTransportSource transportSource;
    juce::AudioSourcePlayer audioSourcePlayer;
    
    // Waveform thumbnail
    juce::AudioThumbnailCache thumbnailCache { 5 };
    juce::AudioThumbnail thumbnail { 512, formatManager, thumbnailCache };
    
    // UI
    juce::TextButton playButton { "Play" };
    juce::TextButton stopButton { "Stop" };
    
    juce::Label nameLabel;
    juce::Label detailsLabel;
    juce::Label tagsLabel;
    
    InstrumentInfo currentInstrument;
    bool hasInstrument = false;
    bool audioCallbackRegistered = false;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(SamplePreviewPanel)
};

//==============================================================================
/**
    Main instrument browser panel with categories, list, and preview.
    
    Layout:
    ┌─────────────────────────────────────────────────────────────┐
    │ [Search...                                    ] [Filter ▼]  │
    ├─────────────────────────────────────────────────────────────┤
    │ [Drums] [Bass] [Keys] [Synths] [Strings] [FX] [Ethiopian]   │
    ├─────────────────────────────────────────────────────────────┤
    │ ┌─────────────────────────────────────────────────────────┐ │
    │ │ InstrumentList (scrollable)                             │ │
    │ │ ┌───────────────────────────────────────────────────┐   │ │
    │ │ │ 808-Sub-C       │ Trap   │ ★                      │   │ │
    │ │ ├───────────────────────────────────────────────────┤   │ │
    │ │ │ Reese-Bass      │ DnB    │                        │   │ │
    │ │ └───────────────────────────────────────────────────┘   │ │
    │ └─────────────────────────────────────────────────────────┘ │
    ├─────────────────────────────────────────────────────────────┤
    │ Preview Panel                                               │
    │ [▶][■]  808-Sub-C.wav  |  Key: C2  |  1.2s  |  Trap, Dark  │
    │ [                    Waveform                             ] │
    └─────────────────────────────────────────────────────────────┘
*/
class InstrumentBrowserPanel : public juce::Component,
                                public CategoryTabBar::Listener,
                                public InstrumentListComponent::Listener
{
public:
    //==============================================================================
    InstrumentBrowserPanel(juce::AudioDeviceManager& deviceManager);
    ~InstrumentBrowserPanel() override;

    //==============================================================================
    void paint(juce::Graphics&) override;
    void resized() override;
    
    //==============================================================================
    /** Load instrument manifest from JSON (received via OSC) */
    void loadFromJSON(const juce::String& json);
    
    /** Request instrument data from Python backend */
    void requestInstrumentData();
    
    /** Filter instruments by search text */
    void setSearchFilter(const juce::String& searchText);
    
    /** Filter instruments by genre */
    void setGenreFilter(const juce::String& genre);
    
    /** Get currently selected instrument */
    const InstrumentInfo* getSelectedInstrument() const;
    
    //==============================================================================
    /** Listener for instrument selection events */
    class Listener
    {
    public:
        virtual ~Listener() = default;
        virtual void instrumentChosen(const InstrumentInfo& info) = 0;
        virtual void requestLibraryInstruments() {}
    };
    
    void addListener(Listener* l) { listeners.add(l); }
    void removeListener(Listener* l) { listeners.remove(l); }

private:
    //==============================================================================
    void categorySelected(const juce::String& category) override;
    void instrumentSelected(const InstrumentInfo& info) override;
    void instrumentActivated(const InstrumentInfo& info) override;
    
    void updateInstrumentList();
    void applyFilters();
    
    //==============================================================================
    // Search bar
    juce::TextEditor searchBox;
    juce::Label searchLabel { {}, "Search" };
    juce::TextButton scanButton { "Scan" };
    juce::Label statusLabel { {}, "" };
    
    // Category tabs
    CategoryTabBar categoryTabs;
    
    // Instrument list
    InstrumentListComponent instrumentList;
    
    // Preview panel
    SamplePreviewPanel previewPanel;
    
    // Data
    juce::Array<InstrumentCategory> categories;
    std::map<juce::String, juce::Array<InstrumentInfo>> instrumentsByCategory;
    juce::String currentCategory = "drums";
    juce::String searchFilter;
    juce::String genreFilter;
    
    // Listeners
    juce::ListenerList<Listener> listeners;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(InstrumentBrowserPanel)
};
