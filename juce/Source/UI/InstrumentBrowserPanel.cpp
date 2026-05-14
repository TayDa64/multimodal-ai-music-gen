/*
  ==============================================================================

    InstrumentBrowserPanel.cpp

    Implementation of the instrument browser panel.

  ==============================================================================
*/

#include "InstrumentBrowserPanel.h"
#include "Theme/ColourScheme.h"
#include "Theme/LayoutConstants.h"

namespace
{
    juce::String normalisedCategory(const juce::String& category)
    {
        return category.trim().toLowerCase();
    }

    juce::String displayCategoryName(const juce::String& category)
    {
        const auto c = normalisedCategory(category);
        if (c.isEmpty())       return "Other";
        if (c == "fx")        return "FX";
        if (c == "synths")    return "Synth";
        if (c == "ethiopian") return "Ethiopian";
        return c.substring(0, 1).toUpperCase() + c.substring(1);
    }

    juce::Colour categoryColourFor(const juce::String& category)
    {
        const auto c = normalisedCategory(category);
        if (c == "drums" || c == "drum") return AppColours::categoryDrums;
        if (c == "bass")                 return AppColours::categoryBass;
        if (c == "guitar" || c == "guitars") return AppColours::categoryGuitar;
        if (c == "keys" || c == "piano" || c == "organ") return AppColours::categoryKeys;
        if (c == "synths" || c == "synth") return AppColours::categorySynths;
        if (c == "strings")              return AppColours::categoryStrings;
        if (c == "fx" || c == "effects") return AppColours::categoryFx;
        if (c == "ethiopian")            return AppColours::categoryEthiopian;
        return AppColours::categoryDefault;
    }

    juce::String sourceBadgeFor(const InstrumentInfo& info)
    {
        const auto path = (info.path + " " + info.absolutePath).toLowerCase();
        if (path.contains("expansion")) return "Expansion";
        if (path.contains("instrument")) return "Library";
        if (info.absolutePath.isNotEmpty()) return "Local";
        if (info.filename.isNotEmpty()) return "Sample";
        return {};
    }

    void drawBadge(juce::Graphics& g,
                   juce::Rectangle<int>& badgeArea,
                   const juce::String& text,
                   juce::Colour accent)
    {
        if (text.isEmpty() || badgeArea.getWidth() < Layout::badgeMinWidth)
            return;

        auto badgeFont = juce::Font(Layout::fontSizeXS, juce::Font::bold);
        const int desiredWidth = badgeFont.getStringWidth(text) + Layout::badgePaddingX * 2;
        const int badgeWidth = juce::jlimit(Layout::badgeMinWidth, badgeArea.getWidth(), desiredWidth);
        auto badgeBounds = badgeArea.removeFromRight(badgeWidth).withHeight(Layout::badgeHeight);
        badgeArea.removeFromRight(Layout::componentGapSM);

        g.setColour(accent.withAlpha(0.18f));
        g.fillRoundedRectangle(badgeBounds.toFloat(), Layout::borderRadiusSM);
        g.setColour(accent.withAlpha(0.72f));
        g.drawRoundedRectangle(badgeBounds.toFloat(), Layout::borderRadiusSM, 1.0f);
        g.setColour(AppColours::textPrimary);
        g.setFont(badgeFont);
        g.drawText(text, badgeBounds.reduced(Layout::paddingSM, 0), juce::Justification::centred);
    }
}

//==============================================================================
// InstrumentCard
//==============================================================================

InstrumentCard::InstrumentCard(const InstrumentInfo& info)
    : instrumentInfo(info)
{
    favoriteButton.setColour(juce::TextButton::buttonColourId, AppColours::surfaceRaised);
    favoriteButton.setColour(juce::TextButton::buttonOnColourId, AppColours::surfaceHighlight);
    favoriteButton.setColour(juce::TextButton::textColourOnId, AppColours::warning);
    favoriteButton.setColour(juce::TextButton::textColourOffId,
                              info.favorite ? AppColours::warning : AppColours::textSecondary);
    addAndMakeVisible(favoriteButton);

    favoriteButton.onClick = [this]() {
        // Toggle favorite status
    };
}

void InstrumentCard::paint(juce::Graphics& g)
{
    auto bounds = getLocalBounds().reduced(2);

    // Background
    juce::Colour bgColor = AppColours::surfaceRaised;
    if (selected)
        bgColor = AppColours::rowSelected;
    else if (hovered)
        bgColor = AppColours::rowHover;

    g.setColour(bgColor);
    g.fillRoundedRectangle(bounds.toFloat(), Layout::borderRadiusMD);
    g.setColour(selected ? AppColours::rowSelectedEdge.withAlpha(0.9f)
                         : AppColours::borderSubtle.withAlpha(0.8f));
    g.drawRoundedRectangle(bounds.toFloat(), Layout::borderRadiusMD, selected ? 2.0f : 1.0f);

    // Category indicator (left bar)
    auto categoryColor = categoryColourFor(instrumentInfo.category);

    g.setColour(categoryColor);
    g.fillRoundedRectangle((float) bounds.getX(), (float) bounds.getY() + 4.0f,
                           4.0f, (float) bounds.getHeight() - 8.0f, 2.0f);

    // Text content
    auto textBounds = bounds.reduced(Layout::paddingLG, Layout::paddingSM);
    textBounds.removeFromRight(32);

    auto badgeArea = textBounds.removeFromRight(juce::jmin(170, textBounds.getWidth() / 2));
    badgeArea.removeFromTop(1);
    drawBadge(g, badgeArea, sourceBadgeFor(instrumentInfo), AppColours::badgeBorder);
    drawBadge(g, badgeArea, displayCategoryName(instrumentInfo.category), categoryColor);

    // Name
    g.setColour(AppColours::textPrimary);
    g.setFont(juce::Font(Layout::fontSizeLG, juce::Font::bold));
    g.drawText(instrumentInfo.name, textBounds.removeFromTop(20), juce::Justification::centredLeft);

    // Details line
    juce::StringArray details;
    if (instrumentInfo.subcategory.isNotEmpty())
        details.add(instrumentInfo.subcategory);
    if (instrumentInfo.key.isNotEmpty())
        details.add(instrumentInfo.key);
    if (instrumentInfo.bpm > 0)
        details.add(juce::String(instrumentInfo.bpm, 0) + " BPM");
    if (instrumentInfo.durationSec > 0)
        details.add(juce::String(instrumentInfo.durationSec, 2) + "s");

    g.setColour(AppColours::textSecondary);
    g.setFont(Layout::fontSizeSM);
    g.drawText(details.joinIntoString(" • "), textBounds.removeFromTop(18), juce::Justification::centredLeft);

    // Tags
    if (instrumentInfo.tags.size() > 0)
    {
        g.setColour(AppColours::primaryLight.withAlpha(0.75f));
        g.setFont(Layout::fontSizeSM);
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

void InstrumentListComponent::paint(juce::Graphics& g)
{
    auto bounds = getLocalBounds().reduced(Layout::paddingSM);
    g.setColour(AppColours::surfaceSunken.withAlpha(0.65f));
    g.fillRoundedRectangle(bounds.toFloat(), Layout::borderRadiusMD);
}

void InstrumentListComponent::paintOverChildren(juce::Graphics& g)
{
    if (cards.isEmpty())
    {
        auto bounds = getLocalBounds().reduced(Layout::paddingSM);
        g.setColour(AppColours::textSecondary);
        g.setFont(juce::Font(Layout::fontSizeMD, juce::Font::plain));
        g.drawText(emptyStateMessage, bounds.reduced(Layout::paddingXL), juce::Justification::centred, true);
    }
}

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
    repaint();
}

void InstrumentListComponent::clearInstruments()
{
    selectedCard = nullptr;
    cards.clear();
    updateLayout();
    repaint();
}

void InstrumentListComponent::setEmptyStateMessage(const juce::String& message)
{
    emptyStateMessage = message;
    repaint();
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
    const int cardHeight = Layout::instrumentCardHeight;
    const int spacing = Layout::listItemSpacing;
    const int width = juce::jmax(0, viewport.getWidth() - (viewport.isVerticalScrollBarShown() ? 10 : 0));

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
    g.setColour(AppColours::surface);
    g.fillAll();

    // Bottom separator
    g.setColour(AppColours::borderSubtle);
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
        auto label = cat.displayName;
        if (cat.instrumentCount > 0)
            label << "  " << cat.instrumentCount;

        auto* btn = tabButtons.add(new juce::TextButton(label));
        btn->setRadioGroupId(1);
        btn->setClickingTogglesState(true);

        btn->setColour(juce::TextButton::buttonColourId, AppColours::surfaceRaised);
        btn->setColour(juce::TextButton::buttonOnColourId, categoryColourFor(cat.name).withAlpha(0.45f));
        btn->setColour(juce::TextButton::textColourOffId, AppColours::textSecondary);
        btn->setColour(juce::TextButton::textColourOnId, AppColours::textPrimary);

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

    playButton.setColour(juce::TextButton::buttonColourId, AppColours::success.darker(0.15f));
    playButton.setColour(juce::TextButton::textColourOffId, AppColours::textPrimary);
    stopButton.setColour(juce::TextButton::buttonColourId, AppColours::error.darker(0.2f));
    stopButton.setColour(juce::TextButton::textColourOffId, AppColours::textPrimary);

    addAndMakeVisible(playButton);
    addAndMakeVisible(stopButton);
    addAndMakeVisible(nameLabel);
    addAndMakeVisible(detailsLabel);
    addAndMakeVisible(tagsLabel);

    playButton.addListener(this);
    stopButton.addListener(this);

    nameLabel.setFont(juce::Font(16.0f, juce::Font::bold));
    nameLabel.setColour(juce::Label::textColourId, AppColours::textPrimary);

    detailsLabel.setFont(13.0f);
    detailsLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);

    tagsLabel.setFont(12.0f);
    tagsLabel.setColour(juce::Label::textColourId, AppColours::primaryLight.withAlpha(0.8f));

    playButton.setTooltip("Play preview");
    stopButton.setTooltip("Stop preview");
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
    g.setColour(AppColours::surface);
    g.fillAll();

    // Top separator
    g.setColour(AppColours::borderSubtle);
    g.drawLine(0, 0, getWidth(), 0, 1.0f);

    // Waveform area
    auto waveformArea = bounds.removeFromBottom(60).reduced(10, 5);

    g.setColour(AppColours::waveformBg);
    g.fillRoundedRectangle(waveformArea.toFloat(), Layout::borderRadiusSM);

    if (hasInstrument && thumbnail.getNumChannels() > 0)
    {
        g.setColour(AppColours::waveformFg.brighter(0.25f));
        thumbnail.drawChannels(g, waveformArea.reduced(2),
                                0.0, thumbnail.getTotalLength(), 1.0f);

        // Playback position
        if (transportSource.isPlaying())
        {
            double pos = transportSource.getCurrentPosition() / transportSource.getLengthInSeconds();
            int xPos = waveformArea.getX() + (int)(waveformArea.getWidth() * pos);

            g.setColour(AppColours::playhead.withAlpha(0.8f));
            g.drawLine(xPos, waveformArea.getY(), xPos, waveformArea.getBottom(), 2.0f);
        }
    }
    else
    {
        g.setColour(AppColours::textSecondary);
        g.setFont(Layout::fontSizeSM);
        g.drawText("Select an instrument to preview", waveformArea, juce::Justification::centred);
    }
}

void SamplePreviewPanel::resized()
{
    auto bounds = getLocalBounds();
    bounds.removeFromBottom(70); // Waveform area
    bounds = bounds.reduced(10, 5);

    auto buttonArea = bounds.removeFromLeft(124);
    playButton.setBounds(buttonArea.removeFromLeft(58).reduced(2));
    stopButton.setBounds(buttonArea.removeFromLeft(58).reduced(2));

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
    searchBox.setTextToShowWhenEmpty("Search instruments...", AppColours::textSecondary);
    searchBox.setColour(juce::TextEditor::backgroundColourId, AppColours::inputBg);
    searchBox.setColour(juce::TextEditor::outlineColourId, AppColours::inputBorder);
    searchBox.setColour(juce::TextEditor::focusedOutlineColourId, AppColours::focusRing);
    searchBox.setColour(juce::TextEditor::textColourId, AppColours::textPrimary);
    searchBox.onTextChange = [this]() { setSearchFilter(searchBox.getText()); };

    // Setup Scan Button
    scanButton.setColour(juce::TextButton::buttonColourId, AppColours::buttonBg);
    scanButton.setColour(juce::TextButton::textColourOffId, AppColours::textPrimary);
    scanButton.onClick = [this]() { requestInstrumentData(); };
    addAndMakeVisible(scanButton);

    searchLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);

    statusLabel.setFont(juce::Font(12.0f));
    statusLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    statusLabel.setJustificationType(juce::Justification::centredLeft);
    statusLabel.setText("Ready", juce::dontSendNotification);
    addAndMakeVisible(statusLabel);

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
    drums.displayName = "Drums";
    drums.subcategories = { "kicks", "snares", "hihats", "claps", "808s" };
    defaultCategories.add(drums);

    InstrumentCategory bass;
    bass.name = "bass";
    bass.displayName = "Bass";
    bass.subcategories = { "808", "sub", "reese", "pluck" };
    defaultCategories.add(bass);

    InstrumentCategory guitar;
    guitar.name = "guitar";
    guitar.displayName = "Guitar";
    guitar.subcategories = { "electric", "acoustic", "riff", "power_chord" };
    defaultCategories.add(guitar);

    InstrumentCategory keys;
    keys.name = "keys";
    keys.displayName = "Keys";
    keys.subcategories = { "piano", "organ", "rhodes" };
    defaultCategories.add(keys);

    InstrumentCategory synths;
    synths.name = "synths";
    synths.displayName = "Synths";
    synths.subcategories = { "lead", "pad", "pluck", "arp" };
    defaultCategories.add(synths);

    InstrumentCategory strings;
    strings.name = "strings";
    strings.displayName = "Strings";
    strings.subcategories = { "violin", "cello", "ensemble" };
    defaultCategories.add(strings);

    InstrumentCategory fx;
    fx.name = "fx";
    fx.displayName = "FX";
    fx.subcategories = { "riser", "impact", "texture", "foley" };
    defaultCategories.add(fx);

    InstrumentCategory ethiopian;
    ethiopian.name = "ethiopian";
    ethiopian.displayName = "Ethiopian";
    ethiopian.subcategories = { "masinko", "krar", "washint", "kebero" };
    defaultCategories.add(ethiopian);

    InstrumentCategory other;
    other.name = "other";
    other.displayName = "Other";
    other.subcategories = { "misc", "uncategorized" };
    defaultCategories.add(other);

    categoryTabs.setCategories(defaultCategories);
    categories = defaultCategories;
}

InstrumentBrowserPanel::~InstrumentBrowserPanel() {}

void InstrumentBrowserPanel::paint(juce::Graphics& g)
{
    g.fillAll(AppColours::background);

    auto bounds = getLocalBounds().toFloat().reduced(1.0f);
    g.setColour(AppColours::surface.withAlpha(0.72f));
    g.fillRoundedRectangle(bounds, Layout::borderRadiusLG);
    g.setColour(AppColours::borderSubtle);
    g.drawRoundedRectangle(bounds, Layout::borderRadiusLG, 1.0f);
}

void InstrumentBrowserPanel::resized()
{
    auto bounds = getLocalBounds();

    // Use FlexBox for search bar layout
    auto searchArea = bounds.removeFromTop(40).reduced(Layout::paddingMD, Layout::paddingSM);

    juce::FlexBox searchFlex = Layout::createRowFlex();
    searchFlex.items.add(juce::FlexItem(searchLabel).withWidth(60.0f).withHeight(30.0f));
    searchFlex.items.add(juce::FlexItem(searchBox).withFlex(1.0f).withHeight(30.0f).withMargin({0, Layout::paddingSM, 0, Layout::paddingSM}));
    searchFlex.items.add(juce::FlexItem(statusLabel).withWidth(180.0f).withHeight(30.0f).withMargin({0, 0, 0, Layout::paddingSM}));
    searchFlex.items.add(juce::FlexItem(scanButton).withWidth(70.0f).withHeight(30.0f));
    searchFlex.performLayout(searchArea);

    // Category tabs (adaptive height)
    int tabHeight = juce::jmax(32, juce::jmin(40, bounds.getHeight() / 10));
    categoryTabs.setBounds(bounds.removeFromTop(tabHeight));

    // Preview panel (bottom) - adaptive height based on available space
    int previewHeight = juce::jmax(100, juce::jmin(150, bounds.getHeight() / 3));
    previewPanel.setBounds(bounds.removeFromBottom(previewHeight));

    // Instrument list (remaining space)
    instrumentList.setBounds(bounds.reduced(Layout::paddingSM));
}

void InstrumentBrowserPanel::loadFromJSON(const juce::String& json)
{
    scanButton.setEnabled(true);

    auto parsedJSON = juce::JSON::parse(json);
    if (parsedJSON.isVoid())
    {
        statusLabel.setText("Invalid instrument data", juce::dontSendNotification);
        return;
    }

    // If backend provided a manifest file path (to avoid oversized OSC payloads), load it.
    auto manifestVar = parsedJSON.getProperty("manifest_path", juce::var());
    if (manifestVar.isString())
    {
        const auto manifestPath = manifestVar.toString();
        juce::File manifestFile(manifestPath);
        if (manifestFile.existsAsFile())
        {
            auto manifestText = manifestFile.loadFileAsString();
            auto manifestJson = juce::JSON::parse(manifestText);
            if (!manifestJson.isVoid())
                parsedJSON = manifestJson;
        }
    }

    // Parse categories (supports either object map or string array)
    auto catsVar = parsedJSON.getProperty("categories", juce::var());
    if (auto* catsObj = catsVar.getDynamicObject())
    {
        categories.clear();
        for (const auto& prop : catsObj->getProperties())
            categories.add(InstrumentCategory::fromJSON(prop.name.toString(), prop.value));
        categoryTabs.setCategories(categories);
    }
    else if (auto* catsArr = catsVar.getArray())
    {
        juce::Array<InstrumentCategory> parsedCategories;
        for (const auto& c : *catsArr)
        {
            InstrumentCategory cat;
            cat.name = c.toString();
            cat.displayName = cat.name.substring(0, 1).toUpperCase() + cat.name.substring(1);
            parsedCategories.add(cat);
        }

        if (!parsedCategories.isEmpty())
        {
            categories = parsedCategories;
            categoryTabs.setCategories(categories);
        }
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

    const int count = (int) parsedJSON.getProperty("count", 0);
    if (count > 0)
        statusLabel.setText("Loaded " + juce::String(count) + " instruments", juce::dontSendNotification);
    else
        statusLabel.setText("Loaded", juce::dontSendNotification);

    // If current category isn't present, fall back to the first available category.
    if (instrumentsByCategory.find(currentCategory) == instrumentsByCategory.end() && !instrumentsByCategory.empty())
        currentCategory = instrumentsByCategory.begin()->first;

    updateInstrumentList();
}

void InstrumentBrowserPanel::requestInstrumentData()
{
    statusLabel.setText("Scanning...", juce::dontSendNotification);
    scanButton.setEnabled(false);
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
        instrumentList.setEmptyStateMessage("No " + displayCategoryName(currentCategory).toLowerCase()
                                            + " instruments loaded. Click Scan to refresh the library.");
        instrumentList.setInstruments(it->second);
    }
    else
    {
        instrumentList.setEmptyStateMessage("No instruments loaded for " + displayCategoryName(currentCategory)
                                            + ". Click Scan to refresh the library.");
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
    {
        instrumentList.setEmptyStateMessage("No instruments loaded for " + displayCategoryName(currentCategory)
                                            + ". Click Scan to refresh the library.");
        instrumentList.clearInstruments();
        return;
    }

    if (searchFilter.isEmpty() && genreFilter.isEmpty())
    {
        instrumentList.setEmptyStateMessage("No " + displayCategoryName(currentCategory).toLowerCase()
                                            + " instruments loaded. Click Scan to refresh the library.");
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

    instrumentList.setEmptyStateMessage("No instruments match the current search or genre filter.");
    instrumentList.setInstruments(filtered);
}
