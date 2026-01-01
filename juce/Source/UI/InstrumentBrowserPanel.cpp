/*
  ==============================================================================

    InstrumentBrowserPanel.cpp
    
    Implementation of the instrument browser panel.

  ==============================================================================
*/

#include "InstrumentBrowserPanel.h"

//==============================================================================
// InstrumentCard
//==============================================================================

InstrumentCard::InstrumentCard(const InstrumentInfo& info)
    : instrumentInfo(info)
{
    favoriteButton.setColour(juce::TextButton::textColourOnId, juce::Colours::gold);
    favoriteButton.setColour(juce::TextButton::textColourOffId, 
                              info.favorite ? juce::Colours::gold : juce::Colours::grey);
    addAndMakeVisible(favoriteButton);
    
    favoriteButton.onClick = [this]() {
        // Toggle favorite status
    };
}

void InstrumentCard::paint(juce::Graphics& g)
{
    auto bounds = getLocalBounds().reduced(2);
    
    // Background
    juce::Colour bgColor = juce::Colour(40, 40, 45);
    if (selected)
        bgColor = juce::Colour(60, 60, 100);
    else if (hovered)
        bgColor = juce::Colour(50, 50, 55);
    
    g.setColour(bgColor);
    g.fillRoundedRectangle(bounds.toFloat(), 6.0f);
    
    // Border when selected
    if (selected)
    {
        g.setColour(juce::Colour(100, 100, 200));
        g.drawRoundedRectangle(bounds.toFloat(), 6.0f, 2.0f);
    }
    
    // Category indicator (left bar)
    juce::Colour categoryColor = juce::Colours::grey;
    if (instrumentInfo.category == "drums")
        categoryColor = juce::Colour(255, 100, 100);
    else if (instrumentInfo.category == "bass")
        categoryColor = juce::Colour(100, 200, 255);
    else if (instrumentInfo.category == "keys")
        categoryColor = juce::Colour(255, 200, 100);
    else if (instrumentInfo.category == "synths")
        categoryColor = juce::Colour(200, 100, 255);
    else if (instrumentInfo.category == "strings")
        categoryColor = juce::Colour(100, 255, 150);
    else if (instrumentInfo.category == "fx")
        categoryColor = juce::Colour(255, 150, 200);
    else if (instrumentInfo.category == "ethiopian")
        categoryColor = juce::Colour(50, 205, 50);
    
    g.setColour(categoryColor);
    g.fillRoundedRectangle(bounds.getX(), bounds.getY() + 4, 4, bounds.getHeight() - 8, 2.0f);
    
    // Text content
    auto textBounds = bounds.reduced(12, 4);
    
    // Name
    g.setColour(juce::Colours::white);
    g.setFont(juce::Font(14.0f, juce::Font::bold));
    g.drawText(instrumentInfo.name, textBounds.removeFromTop(20), juce::Justification::centredLeft);
    
    // Details line
    juce::String details;
    if (instrumentInfo.subcategory.isNotEmpty())
        details += instrumentInfo.subcategory;
    if (instrumentInfo.key.isNotEmpty())
        details += " | " + instrumentInfo.key;
    if (instrumentInfo.bpm > 0)
        details += " | " + juce::String(instrumentInfo.bpm, 0) + " BPM";
    if (instrumentInfo.durationSec > 0)
        details += " | " + juce::String(instrumentInfo.durationSec, 2) + "s";
    
    g.setColour(juce::Colours::grey);
    g.setFont(12.0f);
    g.drawText(details, textBounds.removeFromTop(18), juce::Justification::centredLeft);
    
    // Tags
    if (instrumentInfo.tags.size() > 0)
    {
        g.setColour(juce::Colour(120, 120, 150));
        g.setFont(11.0f);
        g.drawText(instrumentInfo.tags.joinIntoString(" • "), 
                   textBounds.removeFromTop(16), 
                   juce::Justification::centredLeft);
    }
}

void InstrumentCard::resized()
{
    auto bounds = getLocalBounds();
    favoriteButton.setBounds(bounds.removeFromRight(30).reduced(5));
}

void InstrumentCard::mouseEnter(const juce::MouseEvent&)
{
    hovered = true;
    repaint();
}

void InstrumentCard::mouseExit(const juce::MouseEvent&)
{
    hovered = false;
    repaint();
}

void InstrumentCard::mouseDown(const juce::MouseEvent&)
{
    if (listener)
        listener->instrumentCardClicked(this);
}

void InstrumentCard::mouseDoubleClick(const juce::MouseEvent&)
{
    if (listener)
        listener->instrumentCardDoubleClicked(this);
}

void InstrumentCard::setSelected(bool sel)
{
    selected = sel;
    repaint();
}

//==============================================================================
// InstrumentListComponent
//==============================================================================

InstrumentListComponent::InstrumentListComponent()
{
    addAndMakeVisible(viewport);
    viewport.setViewedComponent(&contentComponent, false);
    viewport.setScrollBarsShown(true, false);
}

InstrumentListComponent::~InstrumentListComponent() {}

void InstrumentListComponent::resized()
{
    viewport.setBounds(getLocalBounds());
    updateLayout();
}

void InstrumentListComponent::setInstruments(const juce::Array<InstrumentInfo>& instruments)
{
    clearInstruments();
    
    for (const auto& info : instruments)
    {
        auto* card = cards.add(new InstrumentCard(info));
        card->setListener(this);
        contentComponent.addAndMakeVisible(card);
    }
    
    updateLayout();
}

void InstrumentListComponent::clearInstruments()
{
    selectedCard = nullptr;
    cards.clear();
}

const InstrumentInfo* InstrumentListComponent::getSelectedInstrument() const
{
    return selectedCard ? &selectedCard->getInfo() : nullptr;
}

void InstrumentListComponent::clearSelection()
{
    if (selectedCard)
    {
        selectedCard->setSelected(false);
        selectedCard = nullptr;
    }
}

void InstrumentListComponent::instrumentCardClicked(InstrumentCard* card)
{
    if (selectedCard && selectedCard != card)
        selectedCard->setSelected(false);
    
    selectedCard = card;
    selectedCard->setSelected(true);
    
    listeners.call([&](Listener& l) { l.instrumentSelected(card->getInfo()); });
}

void InstrumentListComponent::instrumentCardDoubleClicked(InstrumentCard* card)
{
    listeners.call([&](Listener& l) { l.instrumentActivated(card->getInfo()); });
}

void InstrumentListComponent::updateLayout()
{
    const int cardHeight = 70;
    const int spacing = 4;
    const int width = viewport.getWidth() - (viewport.isVerticalScrollBarShown() ? 10 : 0);
    
    int y = 0;
    for (auto* card : cards)
    {
        card->setBounds(0, y, width, cardHeight);
        y += cardHeight + spacing;
    }
    
    contentComponent.setSize(width, y);
}

//==============================================================================
// CategoryTabBar
//==============================================================================

CategoryTabBar::CategoryTabBar() {}

void CategoryTabBar::paint(juce::Graphics& g)
{
    g.setColour(juce::Colour(30, 30, 35));
    g.fillAll();
    
    // Bottom separator
    g.setColour(juce::Colour(50, 50, 60));
    g.drawLine(0, getHeight() - 1, getWidth(), getHeight() - 1, 1.0f);
}

void CategoryTabBar::resized()
{
    updateTabs();
}

void CategoryTabBar::setCategories(const juce::Array<InstrumentCategory>& cats)
{
    categories = cats;
    
    // Rebuild buttons
    tabButtons.clear();
    
    for (const auto& cat : categories)
    {
        auto* btn = tabButtons.add(new juce::TextButton(cat.displayName));
        btn->setRadioGroupId(1);
        btn->setClickingTogglesState(true);
        
        btn->setColour(juce::TextButton::buttonColourId, juce::Colour(40, 40, 45));
        btn->setColour(juce::TextButton::buttonOnColourId, juce::Colour(70, 70, 120));
        btn->setColour(juce::TextButton::textColourOffId, juce::Colours::grey);
        btn->setColour(juce::TextButton::textColourOnId, juce::Colours::white);
        
        juce::String catName = cat.name;
        btn->onClick = [this, catName]() {
            selectedCategory = catName;
            listeners.call([&](Listener& l) { l.categorySelected(catName); });
        };
        
        addAndMakeVisible(btn);
    }
    
    if (tabButtons.size() > 0 && selectedCategory.isEmpty())
    {
        selectedCategory = categories[0].name;
        tabButtons[0]->setToggleState(true, juce::dontSendNotification);
    }
    
    updateTabs();
}

void CategoryTabBar::setSelectedCategory(const juce::String& categoryName)
{
    selectedCategory = categoryName;
    
    for (int i = 0; i < categories.size(); ++i)
    {
        if (categories[i].name == categoryName)
        {
            tabButtons[i]->setToggleState(true, juce::dontSendNotification);
            break;
        }
    }
}

juce::String CategoryTabBar::getSelectedCategory() const
{
    return selectedCategory;
}

void CategoryTabBar::updateTabs()
{
    if (tabButtons.isEmpty()) return;
    
    int tabWidth = getWidth() / tabButtons.size();
    int x = 0;
    
    for (auto* btn : tabButtons)
    {
        btn->setBounds(x, 2, tabWidth - 2, getHeight() - 4);
        x += tabWidth;
    }
}

//==============================================================================
// SamplePreviewPanel
//==============================================================================

SamplePreviewPanel::SamplePreviewPanel(juce::AudioDeviceManager& dm)
    : audioDeviceManager(dm)
{
    formatManager.registerBasicFormats();
    
    // Defer audio callback registration - will be done when first audio file is loaded
    // This prevents issues if the device manager isn't fully ready yet
    
    playButton.setColour(juce::TextButton::buttonColourId, juce::Colour(50, 120, 50));
    stopButton.setColour(juce::TextButton::buttonColourId, juce::Colour(120, 50, 50));
    
    addAndMakeVisible(playButton);
    addAndMakeVisible(stopButton);
    addAndMakeVisible(nameLabel);
    addAndMakeVisible(detailsLabel);
    addAndMakeVisible(tagsLabel);
    
    playButton.addListener(this);
    stopButton.addListener(this);
    
    nameLabel.setFont(juce::Font(16.0f, juce::Font::bold));
    nameLabel.setColour(juce::Label::textColourId, juce::Colours::white);
    
    detailsLabel.setFont(13.0f);
    detailsLabel.setColour(juce::Label::textColourId, juce::Colours::lightgrey);
    
    tagsLabel.setFont(12.0f);
    tagsLabel.setColour(juce::Label::textColourId, juce::Colour(100, 150, 200));
}

SamplePreviewPanel::~SamplePreviewPanel()
{
    stopTimer();
    transportSource.setSource(nullptr);
    audioSourcePlayer.setSource(nullptr);
    
    // Only remove callback if we actually added it
    if (audioCallbackRegistered)
        audioDeviceManager.removeAudioCallback(&audioSourcePlayer);
}

void SamplePreviewPanel::paint(juce::Graphics& g)
{
    auto bounds = getLocalBounds();
    
    // Background
    g.setColour(juce::Colour(35, 35, 40));
    g.fillAll();
    
    // Top separator
    g.setColour(juce::Colour(50, 50, 60));
    g.drawLine(0, 0, getWidth(), 0, 1.0f);
    
    // Waveform area
    auto waveformArea = bounds.removeFromBottom(60).reduced(10, 5);
    
    g.setColour(juce::Colour(25, 25, 30));
    g.fillRoundedRectangle(waveformArea.toFloat(), 4.0f);
    
    if (hasInstrument && thumbnail.getNumChannels() > 0)
    {
        g.setColour(juce::Colour(100, 150, 255));
        thumbnail.drawChannels(g, waveformArea.reduced(2), 
                                0.0, thumbnail.getTotalLength(), 1.0f);
        
        // Playback position
        if (transportSource.isPlaying())
        {
            double pos = transportSource.getCurrentPosition() / transportSource.getLengthInSeconds();
            int xPos = waveformArea.getX() + (int)(waveformArea.getWidth() * pos);
            
            g.setColour(juce::Colours::white.withAlpha(0.8f));
            g.drawLine(xPos, waveformArea.getY(), xPos, waveformArea.getBottom(), 2.0f);
        }
    }
    else
    {
        g.setColour(juce::Colours::grey);
        g.setFont(12.0f);
        g.drawText("Select an instrument to preview", waveformArea, juce::Justification::centred);
    }
}

void SamplePreviewPanel::resized()
{
    auto bounds = getLocalBounds();
    bounds.removeFromBottom(70); // Waveform area
    bounds = bounds.reduced(10, 5);
    
    auto buttonArea = bounds.removeFromLeft(70);
    playButton.setBounds(buttonArea.removeFromLeft(32).reduced(2));
    stopButton.setBounds(buttonArea.removeFromLeft(32).reduced(2));
    
    bounds.removeFromLeft(10);
    nameLabel.setBounds(bounds.removeFromTop(22));
    detailsLabel.setBounds(bounds.removeFromTop(18));
    tagsLabel.setBounds(bounds.removeFromTop(16));
}

void SamplePreviewPanel::setInstrument(const InstrumentInfo& info)
{
    stop();
    
    currentInstrument = info;
    hasInstrument = true;
    
    nameLabel.setText(info.name, juce::dontSendNotification);
    
    juce::String details;
    if (info.subcategory.isNotEmpty())
        details += info.subcategory + "  •  ";
    if (info.key.isNotEmpty())
        details += "Key: " + info.key + "  •  ";
    if (info.durationSec > 0)
        details += juce::String(info.durationSec, 2) + "s";
    if (info.bpm > 0)
        details += "  •  " + juce::String(info.bpm, 0) + " BPM";
    
    detailsLabel.setText(details, juce::dontSendNotification);
    tagsLabel.setText(info.tags.joinIntoString(" • "), juce::dontSendNotification);
    
    // Load audio for preview
    loadAudioFile(info.absolutePath);
    
    repaint();
}

void SamplePreviewPanel::clearInstrument()
{
    stop();
    hasInstrument = false;
    currentInstrument = {};
    nameLabel.setText("", juce::dontSendNotification);
    detailsLabel.setText("", juce::dontSendNotification);
    tagsLabel.setText("", juce::dontSendNotification);
    thumbnail.clear();
    repaint();
}

void SamplePreviewPanel::loadAudioFile(const juce::String& path)
{
    juce::File file(path);
    
    if (!file.existsAsFile())
        return;
    
    // Register audio callback on first load
    if (!audioCallbackRegistered)
    {
        audioSourcePlayer.setSource(&transportSource);
        audioDeviceManager.addAudioCallback(&audioSourcePlayer);
        audioCallbackRegistered = true;
    }
    
    auto* reader = formatManager.createReaderFor(file);
    
    if (reader != nullptr)
    {
        auto newSource = std::make_unique<juce::AudioFormatReaderSource>(reader, true);
        transportSource.setSource(newSource.get(), 0, nullptr, reader->sampleRate);
        readerSource.reset(newSource.release());
        
        thumbnail.setSource(new juce::FileInputSource(file));
    }
}

void SamplePreviewPanel::play()
{
    if (readerSource)
    {
        transportSource.setPosition(0.0);
        transportSource.start();
        startTimerHz(30);
    }
}

void SamplePreviewPanel::stop()
{
    transportSource.stop();
    transportSource.setPosition(0.0);
    stopTimer();
    repaint();
}

bool SamplePreviewPanel::isPlaying() const
{
    return transportSource.isPlaying();
}

void SamplePreviewPanel::buttonClicked(juce::Button* button)
{
    if (button == &playButton)
        play();
    else if (button == &stopButton)
        stop();
}

void SamplePreviewPanel::timerCallback()
{
    if (!transportSource.isPlaying())
    {
        stop();
    }
    repaint();
}

//==============================================================================
// InstrumentBrowserPanel
//==============================================================================

InstrumentBrowserPanel::InstrumentBrowserPanel(juce::AudioDeviceManager& deviceManager)
    : previewPanel(deviceManager)
{
    // Search box
    searchBox.setTextToShowWhenEmpty("Search instruments...", juce::Colours::grey);
    searchBox.setColour(juce::TextEditor::backgroundColourId, juce::Colour(40, 40, 45));
    searchBox.setColour(juce::TextEditor::outlineColourId, juce::Colour(60, 60, 70));
    searchBox.setColour(juce::TextEditor::textColourId, juce::Colours::white);
    searchBox.onTextChange = [this]() { setSearchFilter(searchBox.getText()); };
    
    // Setup Scan Button
    scanButton.setColour(juce::TextButton::buttonColourId, juce::Colour(60, 60, 70));
    scanButton.onClick = [this]() { requestInstrumentData(); };
    addAndMakeVisible(scanButton);

    addAndMakeVisible(searchLabel);
    addAndMakeVisible(searchBox);
    addAndMakeVisible(categoryTabs);
    addAndMakeVisible(instrumentList);
    addAndMakeVisible(previewPanel);
    
    categoryTabs.addListener(this);
    instrumentList.addListener(this);
    
    // Load default categories
    juce::Array<InstrumentCategory> defaultCategories;
    
    InstrumentCategory drums;
    drums.name = "drums";
    drums.displayName = "🥁 Drums";
    drums.subcategories = { "kicks", "snares", "hihats", "claps", "808s" };
    defaultCategories.add(drums);
    
    InstrumentCategory bass;
    bass.name = "bass";
    bass.displayName = "🎸 Bass";
    bass.subcategories = { "808", "sub", "reese", "pluck" };
    defaultCategories.add(bass);
    
    InstrumentCategory keys;
    keys.name = "keys";
    keys.displayName = "🎹 Keys";
    keys.subcategories = { "piano", "organ", "rhodes" };
    defaultCategories.add(keys);
    
    InstrumentCategory synths;
    synths.name = "synths";
    synths.displayName = "🎛️ Synths";
    synths.subcategories = { "lead", "pad", "pluck", "arp" };
    defaultCategories.add(synths);
    
    InstrumentCategory strings;
    strings.name = "strings";
    strings.displayName = "🎻 Strings";
    strings.subcategories = { "violin", "cello", "ensemble" };
    defaultCategories.add(strings);
    
    InstrumentCategory fx;
    fx.name = "fx";
    fx.displayName = "✨ FX";
    fx.subcategories = { "riser", "impact", "texture", "foley" };
    defaultCategories.add(fx);
    
    InstrumentCategory ethiopian;
    ethiopian.name = "ethiopian";
    ethiopian.displayName = "🇪🇹 Ethiopian";
    ethiopian.subcategories = { "masinko", "krar", "washint", "kebero" };
    defaultCategories.add(ethiopian);
    
    categoryTabs.setCategories(defaultCategories);
    categories = defaultCategories;
}

InstrumentBrowserPanel::~InstrumentBrowserPanel() {}

void InstrumentBrowserPanel::paint(juce::Graphics& g)
{
    g.fillAll(juce::Colour(25, 25, 30));
}

void InstrumentBrowserPanel::resized()
{
    auto bounds = getLocalBounds();
    
    // Search bar
    auto searchArea = bounds.removeFromTop(40).reduced(10, 5);
    searchLabel.setBounds(searchArea.removeFromLeft(25));
    
    // Scan button on the right
    scanButton.setBounds(searchArea.removeFromRight(60));
    searchArea.removeFromRight(5); // Gap
    
    searchBox.setBounds(searchArea);
    
    // Category tabs
    categoryTabs.setBounds(bounds.removeFromTop(36));
    
    // Preview panel (bottom)
    previewPanel.setBounds(bounds.removeFromBottom(130));
    
    // Instrument list (remaining space)
    instrumentList.setBounds(bounds.reduced(5));
}

void InstrumentBrowserPanel::loadFromJSON(const juce::String& json)
{
    auto parsedJSON = juce::JSON::parse(json);
    
    if (parsedJSON.isVoid())
        return;
    
    // Parse categories
    if (auto* catsObj = parsedJSON.getProperty("categories", juce::var()).getDynamicObject())
    {
        categories.clear();
        
        for (const auto& prop : catsObj->getProperties())
        {
            categories.add(InstrumentCategory::fromJSON(prop.name.toString(), prop.value));
        }
        
        categoryTabs.setCategories(categories);
    }
    
    // Parse instruments by category
    if (auto* instrumentsObj = parsedJSON.getProperty("instruments", juce::var()).getDynamicObject())
    {
        instrumentsByCategory.clear();
        
        for (const auto& prop : instrumentsObj->getProperties())
        {
            juce::Array<InstrumentInfo> categoryInstruments;
            
            if (auto* arr = prop.value.getArray())
            {
                for (const auto& instVar : *arr)
                {
                    categoryInstruments.add(InstrumentInfo::fromJSON(instVar));
                }
            }
            
            instrumentsByCategory[prop.name.toString()] = categoryInstruments;
        }
    }
    
    updateInstrumentList();
}

void InstrumentBrowserPanel::requestInstrumentData()
{
    // Request data from backend via listener
    listeners.call([&](Listener& l) { l.requestLibraryInstruments(); });
}

void InstrumentBrowserPanel::setSearchFilter(const juce::String& searchText)
{
    searchFilter = searchText.toLowerCase();
    applyFilters();
}

void InstrumentBrowserPanel::setGenreFilter(const juce::String& genre)
{
    genreFilter = genre;
    applyFilters();
}

const InstrumentInfo* InstrumentBrowserPanel::getSelectedInstrument() const
{
    return instrumentList.getSelectedInstrument();
}

void InstrumentBrowserPanel::categorySelected(const juce::String& category)
{
    currentCategory = category;
    updateInstrumentList();
}

void InstrumentBrowserPanel::instrumentSelected(const InstrumentInfo& info)
{
    previewPanel.setInstrument(info);
}

void InstrumentBrowserPanel::instrumentActivated(const InstrumentInfo& info)
{
    listeners.call([&](Listener& l) { l.instrumentChosen(info); });
}

void InstrumentBrowserPanel::updateInstrumentList()
{
    auto it = instrumentsByCategory.find(currentCategory);
    
    if (it != instrumentsByCategory.end())
    {
        instrumentList.setInstruments(it->second);
    }
    else
    {
        instrumentList.clearInstruments();
    }
    
    applyFilters();
}

void InstrumentBrowserPanel::applyFilters()
{
    // For now, just reload. In a full implementation, we'd filter the list
    // based on searchFilter and genreFilter
    
    auto it = instrumentsByCategory.find(currentCategory);
    if (it == instrumentsByCategory.end())
        return;
    
    if (searchFilter.isEmpty() && genreFilter.isEmpty())
    {
        instrumentList.setInstruments(it->second);
        return;
    }
    
    juce::Array<InstrumentInfo> filtered;
    
    for (const auto& inst : it->second)
    {
        bool matchesSearch = searchFilter.isEmpty() ||
                             inst.name.toLowerCase().contains(searchFilter) ||
                             inst.subcategory.toLowerCase().contains(searchFilter) ||
                             inst.tags.joinIntoString(" ").toLowerCase().contains(searchFilter);
        
        bool matchesGenre = genreFilter.isEmpty() ||
                            inst.genreHints.contains(genreFilter, true);
        
        if (matchesSearch && matchesGenre)
            filtered.add(inst);
    }
    
    instrumentList.setInstruments(filtered);
}
