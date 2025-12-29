/*
  ==============================================================================

    ExpansionBrowserPanel.h
    
    UI for browsing, importing, and managing instrument expansion packs.
    Communicates with Python ExpansionManager via OSC.

  ==============================================================================
*/

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include <juce_gui_extra/juce_gui_extra.h>
#include "../Application/AppState.h"

//==============================================================================
/**
    Information about an expansion pack from the Python backend.
*/
struct ExpansionInfo
{
    juce::String id;
    juce::String name;
    juce::String path;
    juce::String author;
    juce::String description;
    int instrumentCount = 0;
    juce::StringArray targetGenres;
    bool enabled = true;
    int priority = 100;
    
    /** Parse from JSON object */
    static ExpansionInfo fromJSON(const juce::var& json)
    {
        ExpansionInfo info;
        info.id = json.getProperty("id", "").toString();
        info.name = json.getProperty("name", "").toString();
        info.path = json.getProperty("path", "").toString();
        info.author = json.getProperty("author", "").toString();
        info.description = json.getProperty("description", "").toString();
        info.instrumentCount = json.getProperty("instruments_count", 0);
        info.enabled = json.getProperty("enabled", true);
        info.priority = json.getProperty("priority", 100);
        
        if (auto* genres = json.getProperty("target_genres", juce::var()).getArray())
        {
            for (const auto& genre : *genres)
                info.targetGenres.add(genre.toString());
        }
        
        return info;
    }
};

//==============================================================================
/**
    Information about an instrument within an expansion.
*/
struct ExpansionInstrumentInfo
{
    juce::String id;
    juce::String name;
    juce::String path;
    juce::String expansion;
    juce::String category;
    juce::String subcategory;
    juce::String role;
    juce::StringArray tags;
    
    /** Parse from JSON object */
    static ExpansionInstrumentInfo fromJSON(const juce::var& json)
    {
        ExpansionInstrumentInfo info;
        info.id = json.getProperty("id", "").toString();
        info.name = json.getProperty("name", "").toString();
        info.path = json.getProperty("path", "").toString();
        info.expansion = json.getProperty("expansion", "").toString();
        info.category = json.getProperty("category", "").toString();
        info.subcategory = json.getProperty("subcategory", "").toString();
        info.role = json.getProperty("role", "").toString();
        
        if (auto* tagsArray = json.getProperty("tags", juce::var()).getArray())
        {
            for (const auto& tag : *tagsArray)
                info.tags.add(tag.toString());
        }
        
        return info;
    }
};

//==============================================================================
/**
    Instrument resolution result from intelligent matching.
*/
struct ResolvedInstrumentInfo
{
    juce::String path;
    juce::String name;
    juce::String source;
    juce::String matchType;  // exact, mapped, semantic, spectral, default
    float confidence = 0.0f;
    juce::String note;
    juce::String requested;
    juce::String genre;
    
    /** Parse from JSON */
    static ResolvedInstrumentInfo fromJSON(const juce::var& json)
    {
        ResolvedInstrumentInfo info;
        info.path = json.getProperty("path", "").toString();
        info.name = json.getProperty("name", "").toString();
        info.source = json.getProperty("source", "").toString();
        info.matchType = json.getProperty("match_type", "default").toString();
        info.confidence = static_cast<float>(json.getProperty("confidence", 0.0));
        info.note = json.getProperty("note", "").toString();
        info.requested = json.getProperty("requested", "").toString();
        info.genre = json.getProperty("genre", "").toString();
        return info;
    }
};

//==============================================================================
/**
    Card component displaying an expansion pack.
*/
class ExpansionCard : public juce::Component
{
public:
    ExpansionCard(const ExpansionInfo& info);
    
    void paint(juce::Graphics& g) override;
    void resized() override;
    void mouseEnter(const juce::MouseEvent&) override;
    void mouseExit(const juce::MouseEvent&) override;
    void mouseDown(const juce::MouseEvent&) override;
    
    const ExpansionInfo& getInfo() const { return expansionInfo; }
    
    void setSelected(bool selected);
    bool isSelected() const { return selected; }
    
    /** Listener for card events */
    class Listener
    {
    public:
        virtual ~Listener() = default;
        virtual void expansionCardClicked(ExpansionCard* card) = 0;
    };
    
    void setListener(Listener* l) { listener = l; }
    
private:
    ExpansionInfo expansionInfo;
    bool hovered = false;
    bool selected = false;
    Listener* listener = nullptr;
    
    juce::ToggleButton enableToggle;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(ExpansionCard)
};

//==============================================================================
/**
    List of expansion cards with scrolling.
*/
class ExpansionListComponent : public juce::Component,
                                public ExpansionCard::Listener
{
public:
    ExpansionListComponent();
    ~ExpansionListComponent() override;
    
    void resized() override;
    
    void setExpansions(const juce::Array<ExpansionInfo>& expansions);
    void clearExpansions();
    
    const ExpansionInfo* getSelectedExpansion() const;
    void clearSelection();
    
    /** Listener for selection changes */
    class Listener
    {
    public:
        virtual ~Listener() = default;
        virtual void expansionSelected(const ExpansionInfo& info) = 0;
    };
    
    void addListener(Listener* l) { listeners.add(l); }
    void removeListener(Listener* l) { listeners.remove(l); }
    
private:
    void expansionCardClicked(ExpansionCard* card) override;
    void updateLayout();
    
    juce::OwnedArray<ExpansionCard> cards;
    ExpansionCard* selectedCard = nullptr;
    juce::ListenerList<Listener> listeners;
    
    juce::Viewport viewport;
    juce::Component contentComponent;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(ExpansionListComponent)
};

//==============================================================================
/**
    Instrument list within an expansion.
*/
class ExpansionInstrumentList : public juce::Component,
                                 public juce::TableListBoxModel
{
public:
    ExpansionInstrumentList();
    ~ExpansionInstrumentList() override;
    
    void resized() override;
    
    void setInstruments(const juce::Array<ExpansionInstrumentInfo>& instruments);
    void clearInstruments();
    void setFilter(const juce::String& filter);
    
    // TableListBoxModel
    int getNumRows() override;
    void paintRowBackground(juce::Graphics& g, int rowNumber, int width, int height, bool rowIsSelected) override;
    void paintCell(juce::Graphics& g, int rowNumber, int columnId, int width, int height, bool rowIsSelected) override;
    void selectedRowsChanged(int lastRowSelected) override;
    void cellDoubleClicked(int rowNumber, int columnId, const juce::MouseEvent&) override;
    
    /** Listener for instrument events */
    class Listener
    {
    public:
        virtual ~Listener() = default;
        virtual void instrumentSelected(const ExpansionInstrumentInfo& info) = 0;
        virtual void instrumentActivated(const ExpansionInstrumentInfo& info) = 0;
    };
    
    void addListener(Listener* l) { listeners.add(l); }
    void removeListener(Listener* l) { listeners.remove(l); }
    
private:
    juce::TableListBox table;
    juce::Array<ExpansionInstrumentInfo> allInstruments;
    juce::Array<ExpansionInstrumentInfo> filteredInstruments;
    juce::String filterText;
    
    juce::ListenerList<Listener> listeners;
    
    void applyFilter();
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(ExpansionInstrumentList)
};

//==============================================================================
/**
    Resolution test panel - shows results of intelligent instrument matching.
*/
class ResolutionTestPanel : public juce::Component
{
public:
    ResolutionTestPanel();
    
    void paint(juce::Graphics& g) override;
    void resized() override;
    
    void showResult(const ResolvedInstrumentInfo& result);
    void clear();
    
    /** Listener for test requests */
    class Listener
    {
    public:
        virtual ~Listener() = default;
        virtual void resolveRequested(const juce::String& instrument, const juce::String& genre) = 0;
    };
    
    void setListener(Listener* l) { listener = l; }
    
private:
    juce::Label instructionLabel { {}, "Test Instrument Resolution" };
    juce::TextEditor instrumentInput;
    juce::ComboBox genreCombo;
    juce::TextButton testButton { "Resolve" };
    
    juce::Label resultNameLabel { {}, "" };
    juce::Label resultPathLabel { {}, "" };
    juce::Label resultMatchLabel { {}, "" };
    juce::Label resultNoteLabel { {}, "" };
    
    Listener* listener = nullptr;
    
    void onTestClicked();
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(ResolutionTestPanel)
};

//==============================================================================
/**
    Main expansion browser panel.
    
    Layout:
    ┌─────────────────────────────────────────────────────────────────────────┐
    │  [Import Expansion...]  [Scan Folders]  [Refresh]       [Search...]     │
    ├────────────────────────────┬────────────────────────────────────────────┤
    │  Expansion Packs           │  Instruments in Selected Expansion         │
    │  ┌──────────────────────┐  │  ┌──────────────────────────────────────┐  │
    │  │ ★ Funk o Rama        │  │  │ Name       │ Category │ Tags         │  │
    │  │   52 instruments     │  │  │────────────┼──────────┼──────────────│  │
    │  │   RnB, G-Funk        │  │  │ Amphi Bass │ Bass     │ funk, synth  │  │
    │  ├──────────────────────┤  │  │ Rhodes Key │ Keys     │ keys, rhodes │  │
    │  │   Ethiopian Roots    │  │  │ ...        │          │              │  │
    │  │   24 instruments     │  │  └──────────────────────────────────────┘  │
    │  │   Ethiopian, Eskista │  │                                            │
    │  └──────────────────────┘  │                                            │
    ├────────────────────────────┴────────────────────────────────────────────┤
    │  Resolution Test                                                        │
    │  Instrument: [krar        ] Genre: [eskista ▼] [Resolve]               │
    │  Result: "Guitar Rhodes" (Funk o Rama) - Semantic match (70%)          │
    │  Note: Role match (melodic_string): Guitar Rhodes                       │
    └─────────────────────────────────────────────────────────────────────────┘
*/
class ExpansionBrowserPanel : public juce::Component,
                               public ExpansionListComponent::Listener,
                               public ExpansionInstrumentList::Listener,
                               public ResolutionTestPanel::Listener
{
public:
    //==============================================================================
    ExpansionBrowserPanel();
    ~ExpansionBrowserPanel() override;

    //==============================================================================
    void paint(juce::Graphics& g) override;
    void resized() override;
    
    //==============================================================================
    /** Load expansions data from JSON (received via OSC) */
    void loadExpansionsFromJSON(const juce::String& json);
    
    /** Load instruments for an expansion from JSON */
    void loadInstrumentsFromJSON(const juce::String& json);
    
    /** Show resolution result */
    void showResolutionResult(const juce::String& json);
    
    /** Request expansion list from Python backend */
    void requestExpansionList();
    
    /** Request instruments for an expansion */
    void requestExpansionInstruments(const juce::String& expansionId);
    
    //==============================================================================
    /** Listener for actions requiring OSC communication */
    class Listener
    {
    public:
        virtual ~Listener() = default;
        virtual void requestExpansionListOSC() = 0;
        virtual void requestInstrumentsOSC(const juce::String& expansionId) = 0;
        virtual void requestResolveOSC(const juce::String& instrument, const juce::String& genre) = 0;
        virtual void requestImportExpansionOSC(const juce::String& path) = 0;
        virtual void requestScanExpansionsOSC(const juce::String& directory) = 0;
    };
    
    void addListener(Listener* l) { listeners.add(l); }
    void removeListener(Listener* l) { listeners.remove(l); }

private:
    //==============================================================================
    // ExpansionListComponent::Listener
    void expansionSelected(const ExpansionInfo& info) override;
    
    // ExpansionInstrumentList::Listener
    void instrumentSelected(const ExpansionInstrumentInfo& info) override;
    void instrumentActivated(const ExpansionInstrumentInfo& info) override;
    
    // ResolutionTestPanel::Listener
    void resolveRequested(const juce::String& instrument, const juce::String& genre) override;
    
    //==============================================================================
    void onImportClicked();
    void onScanClicked();
    void onRefreshClicked();
    void onSearchChanged();
    
    //==============================================================================
    // Toolbar
    juce::TextButton importButton { "Import Expansion..." };
    juce::TextButton scanButton { "Scan Folders" };
    juce::TextButton refreshButton { "Refresh" };
    juce::TextEditor searchBox;
    juce::Label searchLabel { {}, "Search:" };
    
    // Main content
    ExpansionListComponent expansionList;
    ExpansionInstrumentList instrumentList;
    
    // Resolution test panel
    ResolutionTestPanel resolutionPanel;
    
    // Data
    juce::Array<ExpansionInfo> expansions;
    juce::String selectedExpansionId;
    
    // Listeners
    juce::ListenerList<Listener> listeners;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(ExpansionBrowserPanel)
};

