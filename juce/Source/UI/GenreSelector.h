/*
  ==============================================================================

    GenreSelector.h
    
    Genre selection component that loads genre templates from Python backend.
    Part of NB Phase 2: JUCE Framework & UI Standardization.

  ==============================================================================
*/

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include "../Application/AppState.h"

//==============================================================================
/**
    Genre template data loaded from genres.json via Python backend.
*/
struct GenreTemplate
{
    juce::String id;           // e.g., "trap", "g_funk", "lofi"
    juce::String displayName;  // e.g., "Trap", "G-Funk", "Lo-Fi"
    juce::Colour themeColor;   // UI accent color for this genre
    
    // Tempo settings
    int bpmMin = 60;
    int bpmMax = 180;
    int bpmDefault = 120;
    float swingAmount = 0.0f;
    
    // Drum configuration
    bool hihatRolls = false;
    bool halfTimeSnare = false;
    juce::String hihatDensity = "8th";
    
    // Default instruments
    juce::StringArray defaultInstruments;
    juce::StringArray forbiddenElements;
    
    // FX chains
    juce::StringArray fxChainMaster;
    juce::StringArray fxChainDrums;
    
    // Spectral profile hints
    float subBassPresence = 0.5f;
    float brightness = 0.5f;
    float warmth = 0.5f;
    juce::String character808 = "clean";
    
    /** Parse from JSON object */
    static GenreTemplate fromJSON(const juce::String& genreId, const juce::var& json)
    {
        GenreTemplate t;
        t.id = genreId;
        t.displayName = json.getProperty("display_name", genreId).toString();
        
        // Parse color
        juce::String colorStr = json.getProperty("color", "#808080").toString();
        t.themeColor = juce::Colour::fromString(colorStr);
        
        // Parse BPM range
        if (auto* bpmRange = json.getProperty("bpm_range", juce::var()).getArray())
        {
            if (bpmRange->size() >= 2)
            {
                t.bpmMin = (*bpmRange)[0];
                t.bpmMax = (*bpmRange)[1];
            }
        }
        t.bpmDefault = json.getProperty("default_bpm", 120);
        t.swingAmount = json.getProperty("swing", 0.0f);
        
        // Parse drum config
        t.hihatRolls = json.getProperty("hihat_rolls", false);
        
        // Parse instruments
        if (auto* instruments = json.getProperty("instruments", juce::var()).getArray())
        {
            for (const auto& inst : *instruments)
                t.defaultInstruments.add(inst.toString());
        }
        
        // Parse forbidden
        if (auto* forbidden = json.getProperty("forbidden", juce::var()).getArray())
        {
            for (const auto& elem : *forbidden)
                t.forbiddenElements.add(elem.toString());
        }
        
        return t;
    }
};

//==============================================================================
/**
    Genre selector component with visual theme support.
    
    Features:
    - Dropdown selector for genre
    - Color-coded UI based on selected genre
    - BPM range indicator
    - Swing amount display
    - Integration with prompt parser
*/
class GenreSelector : public juce::Component,
                      public juce::ComboBox::Listener
{
public:
    //==============================================================================
    GenreSelector();
    ~GenreSelector() override;

    //==============================================================================
    void paint(juce::Graphics&) override;
    void resized() override;
    
    //==============================================================================
    /** Load genre templates from JSON manifest (received via OSC) */
    void loadFromJSON(const juce::String& json);
    
    /** Load hardcoded defaults (fallback if backend unavailable) */
    void loadDefaults();
    
    /** Get the currently selected genre ID */
    juce::String getSelectedGenreId() const;
    
    /** Get the currently selected genre template */
    const GenreTemplate* getSelectedGenre() const;
    
    /** Set the selected genre by ID */
    void setSelectedGenre(const juce::String& genreId);
    
    /** Get the theme color for the current genre */
    juce::Colour getThemeColor() const;
    
    /** Get the default BPM for the current genre */
    int getDefaultBPM() const;
    
    /** Get the BPM range for the current genre */
    std::pair<int, int> getBPMRange() const;
    
    /** Get swing amount for current genre (0.0 - 1.0) */
    float getSwingAmount() const;
    
    /** Check if current genre uses hi-hat rolls */
    bool usesHihatRolls() const;
    
    /** Get all available genre IDs */
    juce::StringArray getAvailableGenres() const;
    
    //==============================================================================
    /** Listener for genre selection changes */
    class Listener
    {
    public:
        virtual ~Listener() = default;
        virtual void genreChanged(const juce::String& genreId, const GenreTemplate& genre) = 0;
    };
    
    void addListener(Listener* listener);
    void removeListener(Listener* listener);

private:
    //==============================================================================
    void comboBoxChanged(juce::ComboBox* comboBox) override;
    void updateInfoDisplay();
    void notifyListeners();
    
    //==============================================================================
    juce::ComboBox genreCombo;
    juce::Label genreLabel { {}, "Genre:" };
    
    // Info display
    juce::Label bpmRangeLabel;
    juce::Label swingLabel;
    juce::Label hihatLabel;
    
    // Color indicator
    juce::Component colorIndicator;
    
    // Genre templates
    std::map<juce::String, GenreTemplate> genres;
    juce::StringArray genreOrder;  // Preserves combo box item order (std::map iterates alphabetically!)
    juce::String currentGenreId = "trap";
    
    // Listeners
    juce::ListenerList<Listener> listeners;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(GenreSelector)
};
