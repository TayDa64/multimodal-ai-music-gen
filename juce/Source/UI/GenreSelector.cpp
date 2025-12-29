/*
  ==============================================================================

    GenreSelector.cpp
    
    Genre selection component implementation.
    Part of NB Phase 2: JUCE Framework & UI Standardization.

  ==============================================================================
*/

#include "GenreSelector.h"

//==============================================================================
GenreSelector::GenreSelector()
{
    // Setup genre combo box
    genreCombo.setTextWhenNothingSelected("Select Genre...");
    genreCombo.addListener(this);
    addAndMakeVisible(genreCombo);
    
    // Setup label
    genreLabel.setJustificationType(juce::Justification::right);
    genreLabel.setFont(juce::Font(14.0f));
    addAndMakeVisible(genreLabel);
    
    // Setup info labels
    bpmRangeLabel.setFont(juce::Font(11.0f));
    bpmRangeLabel.setColour(juce::Label::textColourId, juce::Colours::grey);
    addAndMakeVisible(bpmRangeLabel);
    
    swingLabel.setFont(juce::Font(11.0f));
    swingLabel.setColour(juce::Label::textColourId, juce::Colours::grey);
    addAndMakeVisible(swingLabel);
    
    hihatLabel.setFont(juce::Font(11.0f));
    hihatLabel.setColour(juce::Label::textColourId, juce::Colours::grey);
    addAndMakeVisible(hihatLabel);
    
    // Color indicator (small colored rectangle)
    addAndMakeVisible(colorIndicator);
    
    // Load default genres
    loadDefaults();
}

GenreSelector::~GenreSelector()
{
    genreCombo.removeListener(this);
}

//==============================================================================
void GenreSelector::paint(juce::Graphics& g)
{
    // Draw color indicator for current genre
    auto indicatorBounds = colorIndicator.getBounds().toFloat();
    if (!indicatorBounds.isEmpty())
    {
        auto color = getThemeColor();
        g.setColour(color);
        g.fillRoundedRectangle(indicatorBounds, 4.0f);
        
        g.setColour(color.brighter(0.3f));
        g.drawRoundedRectangle(indicatorBounds, 4.0f, 1.0f);
    }
}

void GenreSelector::resized()
{
    auto bounds = getLocalBounds().reduced(4);
    
    // Layout: [Label][ColorIndicator][ComboBox] on top row
    // [BPM Range][Swing][HiHat] on bottom row (info)
    
    auto topRow = bounds.removeFromTop(24);
    auto bottomRow = bounds;
    
    // Top row
    genreLabel.setBounds(topRow.removeFromLeft(50));
    topRow.removeFromLeft(4);
    
    colorIndicator.setBounds(topRow.removeFromLeft(16).reduced(2));
    topRow.removeFromLeft(4);
    
    genreCombo.setBounds(topRow);
    
    // Bottom row - info labels
    if (bottomRow.getHeight() > 0)
    {
        bottomRow.removeFromTop(4);
        auto infoHeight = juce::jmin(16, bottomRow.getHeight());
        auto infoRow = bottomRow.removeFromTop(infoHeight);
        
        int labelWidth = infoRow.getWidth() / 3;
        bpmRangeLabel.setBounds(infoRow.removeFromLeft(labelWidth));
        swingLabel.setBounds(infoRow.removeFromLeft(labelWidth));
        hihatLabel.setBounds(infoRow);
    }
}

//==============================================================================
void GenreSelector::loadFromJSON(const juce::String& json)
{
    auto parsed = juce::JSON::parse(json);
    if (parsed.isVoid())
    {
        DBG("GenreSelector: Failed to parse JSON");
        return;
    }
    
    genres.clear();
    genreCombo.clear();
    
    // Parse genres from manifest
    auto genresObj = parsed.getProperty("genres", juce::var());
    if (auto* genresMap = genresObj.getDynamicObject())
    {
        int itemId = 1;
        for (const auto& prop : genresMap->getProperties())
        {
            juce::String genreId = prop.name.toString();
            GenreTemplate tmpl = GenreTemplate::fromJSON(genreId, prop.value);
            genres[genreId] = tmpl;
            
            genreCombo.addItem(tmpl.displayName, itemId++);
        }
    }
    
    // Select default
    if (genres.count(currentGenreId) > 0)
    {
        setSelectedGenre(currentGenreId);
    }
    else if (!genres.empty())
    {
        setSelectedGenre(genres.begin()->first);
    }
    
    updateInfoDisplay();
    repaint();
}

void GenreSelector::loadDefaults()
{
    genres.clear();
    genreCombo.clear();
    
    // Hardcoded defaults matching genres.json
    struct DefaultGenre {
        const char* id;
        const char* name;
        const char* color;
        int bpmMin, bpmMax, bpmDefault;
        float swing;
        bool hihatRolls;
    };
    
    DefaultGenre defaults[] = {
        { "trap",        "Trap",                 "#FF1744", 130, 160, 140, 0.00f, true  },
        { "trap_soul",   "Trap Soul",            "#E91E63", 70,  95,  82,  0.08f, false },
        { "g_funk",      "G-Funk",               "#9C27B0", 85,  105, 96,  0.15f, false },
        { "rnb",         "R&B",                  "#673AB7", 65,  90,  78,  0.10f, false },
        { "lofi",        "Lo-Fi",                "#FF9800", 70,  90,  80,  0.12f, false },
        { "boom_bap",    "Boom Bap",             "#795548", 85,  98,  90,  0.10f, false },
        { "house",       "House",                "#00BCD4", 118, 132, 124, 0.00f, false },
        { "drill",       "Drill",                "#263238", 138, 145, 140, 0.00f, true  },
        { "ethiopian_traditional", "Ethiopian Traditional", "#4CAF50", 90, 130, 110, 0.15f, false },
        { "eskista",     "Eskista",              "#8BC34A", 110, 160, 130, 0.18f, false },
    };
    
    int itemId = 1;
    for (const auto& d : defaults)
    {
        GenreTemplate t;
        t.id = d.id;
        t.displayName = d.name;
        t.themeColor = juce::Colour::fromString(d.color);
        t.bpmMin = d.bpmMin;
        t.bpmMax = d.bpmMax;
        t.bpmDefault = d.bpmDefault;
        t.swingAmount = d.swing;
        t.hihatRolls = d.hihatRolls;
        
        genres[t.id] = t;
        genreCombo.addItem(t.displayName, itemId++);
    }
    
    // Select default genre
    setSelectedGenre("trap_soul");
}

//==============================================================================
juce::String GenreSelector::getSelectedGenreId() const
{
    return currentGenreId;
}

const GenreTemplate* GenreSelector::getSelectedGenre() const
{
    auto it = genres.find(currentGenreId);
    return (it != genres.end()) ? &it->second : nullptr;
}

void GenreSelector::setSelectedGenre(const juce::String& genreId)
{
    if (genres.count(genreId) == 0)
        return;
    
    currentGenreId = genreId;
    
    // Find the combo box item
    int itemIndex = 1;
    for (const auto& [id, tmpl] : genres)
    {
        if (id == genreId)
        {
            genreCombo.setSelectedId(itemIndex, juce::dontSendNotification);
            break;
        }
        itemIndex++;
    }
    
    updateInfoDisplay();
    repaint();
}

juce::Colour GenreSelector::getThemeColor() const
{
    if (auto* tmpl = getSelectedGenre())
        return tmpl->themeColor;
    return juce::Colour(0xFF808080);
}

int GenreSelector::getDefaultBPM() const
{
    if (auto* tmpl = getSelectedGenre())
        return tmpl->bpmDefault;
    return 120;
}

std::pair<int, int> GenreSelector::getBPMRange() const
{
    if (auto* tmpl = getSelectedGenre())
        return { tmpl->bpmMin, tmpl->bpmMax };
    return { 60, 180 };
}

float GenreSelector::getSwingAmount() const
{
    if (auto* tmpl = getSelectedGenre())
        return tmpl->swingAmount;
    return 0.0f;
}

bool GenreSelector::usesHihatRolls() const
{
    if (auto* tmpl = getSelectedGenre())
        return tmpl->hihatRolls;
    return false;
}

juce::StringArray GenreSelector::getAvailableGenres() const
{
    juce::StringArray result;
    for (const auto& [id, tmpl] : genres)
        result.add(id);
    return result;
}

//==============================================================================
void GenreSelector::addListener(Listener* listener)
{
    listeners.add(listener);
}

void GenreSelector::removeListener(Listener* listener)
{
    listeners.remove(listener);
}

//==============================================================================
void GenreSelector::comboBoxChanged(juce::ComboBox* comboBox)
{
    if (comboBox != &genreCombo)
        return;
    
    int selectedId = genreCombo.getSelectedId();
    int itemIndex = 1;
    
    for (const auto& [id, tmpl] : genres)
    {
        if (itemIndex == selectedId)
        {
            currentGenreId = id;
            break;
        }
        itemIndex++;
    }
    
    updateInfoDisplay();
    notifyListeners();
    repaint();
}

void GenreSelector::updateInfoDisplay()
{
    auto* tmpl = getSelectedGenre();
    if (!tmpl)
    {
        bpmRangeLabel.setText("", juce::dontSendNotification);
        swingLabel.setText("", juce::dontSendNotification);
        hihatLabel.setText("", juce::dontSendNotification);
        return;
    }
    
    // BPM range
    bpmRangeLabel.setText(
        juce::String::formatted("BPM: %d-%d", tmpl->bpmMin, tmpl->bpmMax),
        juce::dontSendNotification);
    
    // Swing
    if (tmpl->swingAmount > 0.0f)
    {
        swingLabel.setText(
            juce::String::formatted("Swing: %.0f%%", tmpl->swingAmount * 100.0f),
            juce::dontSendNotification);
    }
    else
    {
        swingLabel.setText("No swing", juce::dontSendNotification);
    }
    
    // Hi-hat rolls
    hihatLabel.setText(
        tmpl->hihatRolls ? "16th HH rolls" : "No HH rolls",
        juce::dontSendNotification);
}

void GenreSelector::notifyListeners()
{
    auto* tmpl = getSelectedGenre();
    if (tmpl)
    {
        listeners.call([this, tmpl](Listener& l) {
            l.genreChanged(currentGenreId, *tmpl);
        });
    }
}
