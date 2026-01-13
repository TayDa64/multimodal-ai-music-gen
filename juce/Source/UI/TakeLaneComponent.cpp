/*
  ==============================================================================

    TakeLaneComponent.cpp
    
    Implementation of take lane UI components.

  ==============================================================================
*/

#include "TakeLaneComponent.h"

//==============================================================================
// TakeLaneItem
//==============================================================================

TakeLaneItem::TakeLaneItem(const TakeLane& take)
    : takeLane(take)
{
    playButton.setColour(juce::TextButton::buttonColourId, juce::Colour(0xff3498db));
    stopButton.setColour(juce::TextButton::buttonColourId, juce::Colour(0xffc0392b));

    for (auto* b : { &muteButton, &soloButton, &keepButton, &favoriteButton })
    {
        b->setClickingTogglesState(true);
        b->setColour(juce::TextButton::buttonColourId, juce::Colour(0xff2c3e50));
        b->setColour(juce::TextButton::buttonOnColourId, juce::Colour(0xff34495e));
    }

    muteButton.setTooltip("Mute this take");
    soloButton.setTooltip("Solo this take");
    keepButton.setTooltip("Keep this take");
    favoriteButton.setTooltip("Favorite this take");
    playButton.setTooltip("Audition this take");
    stopButton.setTooltip("Stop audition");

    playButton.onClick = [this]()
    {
        if (onPlayClicked)
            onPlayClicked(takeLane.takeId, takeLane.midiPath);
    };
    stopButton.onClick = [this]()
    {
        if (onStopClicked)
            onStopClicked();
    };
    muteButton.onClick = [this]()
    {
        setMuted(muteButton.getToggleState());
        if (onMuteToggled)
            onMuteToggled(takeLane.takeId, muted);
    };
    soloButton.onClick = [this]()
    {
        setSolo(soloButton.getToggleState());
        if (onSoloToggled)
            onSoloToggled(takeLane.takeId, solo);
    };
    keepButton.onClick = [this]()
    {
        setKept(keepButton.getToggleState());
        if (onKeepToggled)
            onKeepToggled(takeLane.takeId, kept);
    };
    favoriteButton.onClick = [this]()
    {
        setFavorite(favoriteButton.getToggleState());
        if (onFavoriteToggled)
            onFavoriteToggled(takeLane.takeId, favorite);
    };

    addAndMakeVisible(playButton);
    addAndMakeVisible(stopButton);
    addAndMakeVisible(muteButton);
    addAndMakeVisible(soloButton);
    addAndMakeVisible(keepButton);
    addAndMakeVisible(favoriteButton);
}

void TakeLaneItem::paint(juce::Graphics& g)
{
    auto bounds = getLocalBounds().toFloat();
    
    // Background
    juce::Colour bgColour;
    if (selected)
        bgColour = juce::Colour(0xff2980b9).withAlpha(0.4f);
    else if (hovered)
        bgColour = juce::Colour(0xff3498db).withAlpha(0.2f);
    else
        bgColour = juce::Colour(0xff2c3e50);

    if (playing)
        bgColour = juce::Colour(0xff16a085).withAlpha(selected ? 0.40f : 0.25f);
    
    g.setColour(bgColour);
    g.fillRoundedRectangle(bounds.reduced(1), Layout::borderRadiusSM);
    
    // Selection indicator
    if (selected)
    {
        g.setColour(juce::Colour(0xff2980b9));
        g.fillRoundedRectangle(bounds.removeFromLeft(4).reduced(0, 2), 2.0f);
    }

    // Keep/Favorite mini indicators
    auto indicatorArea = bounds.removeFromRight(52).reduced(0, 6);
    if (kept)
    {
        g.setColour(juce::Colour(0xfff1c40f).withAlpha(0.9f));
        g.setFont(Layout::fontSizeXS);
        g.drawText("K", indicatorArea.removeFromLeft(16), juce::Justification::centred);
    }
    if (favorite)
    {
        g.setColour(juce::Colour(0xfff39c12).withAlpha(0.9f));
        g.setFont(Layout::fontSizeXS);
        g.drawText("F", indicatorArea.removeFromLeft(16), juce::Justification::centred);
    }
    
    // Take ID
    g.setColour(muted ? juce::Colours::grey : juce::Colours::white);
    g.setFont(Layout::fontSizeMD);
    g.drawText(takeLane.takeId, 98, 0, 120, getHeight(), juce::Justification::centredLeft);
    
    // Variation type badge
    auto badgeBounds = juce::Rectangle<float>(220, (getHeight() - 18) / 2.0f, 70, 18);
    juce::Colour badgeColour;
    
    if (takeLane.variationType == "rhythm")
        badgeColour = juce::Colour(0xffe74c3c);
    else if (takeLane.variationType == "pitch")
        badgeColour = juce::Colour(0xff3498db);
    else if (takeLane.variationType == "timing")
        badgeColour = juce::Colour(0xff2ecc71);
    else
        badgeColour = juce::Colour(0xff9b59b6);
    
    g.setColour(badgeColour.withAlpha(0.8f));
    g.fillRoundedRectangle(badgeBounds, 3.0f);
    
    g.setColour(juce::Colours::white);
    g.setFont(Layout::fontSizeXS);
    g.drawText(takeLane.variationType, badgeBounds, juce::Justification::centred);
    
    // Seed (smaller, dimmed)
    g.setColour(juce::Colours::grey);
    g.setFont(Layout::fontSizeXS);
    g.drawText("seed: " + juce::String(takeLane.seed), 295, 0, 90, getHeight(), juce::Justification::centredLeft);
}

void TakeLaneItem::resized()
{
    auto bounds = getLocalBounds().reduced(6, 4);

    auto left = bounds.removeFromLeft(92);
    playButton.setBounds(left.removeFromLeft(44).reduced(2));
    stopButton.setBounds(left.removeFromLeft(44).reduced(2));

    auto right = bounds.removeFromRight(110);
    favoriteButton.setBounds(right.removeFromRight(24).reduced(2));
    keepButton.setBounds(right.removeFromRight(24).reduced(2));
    soloButton.setBounds(right.removeFromRight(24).reduced(2));
    muteButton.setBounds(right.removeFromRight(24).reduced(2));
}

void TakeLaneItem::mouseDown(const juce::MouseEvent& e)
{
    if (!selected && onSelected)
        onSelected(takeLane.takeId, takeLane.midiPath);
}

void TakeLaneItem::mouseEnter(const juce::MouseEvent& e)
{
    hovered = true;
    repaint();
}

void TakeLaneItem::mouseExit(const juce::MouseEvent& e)
{
    hovered = false;
    repaint();
}

void TakeLaneItem::setSelected(bool shouldBeSelected)
{
    if (selected != shouldBeSelected)
    {
        selected = shouldBeSelected;
        repaint();
    }
}

void TakeLaneItem::setPlaying(bool shouldBePlaying)
{
    if (playing != shouldBePlaying)
    {
        playing = shouldBePlaying;
        repaint();
    }
}

void TakeLaneItem::setMuted(bool shouldBeMuted)
{
    muted = shouldBeMuted;
    muteButton.setToggleState(muted, juce::dontSendNotification);
    repaint();
}

void TakeLaneItem::setSolo(bool shouldBeSolo)
{
    solo = shouldBeSolo;
    soloButton.setToggleState(solo, juce::dontSendNotification);
    repaint();
}

void TakeLaneItem::setKept(bool shouldBeKept)
{
    kept = shouldBeKept;
    keepButton.setToggleState(kept, juce::dontSendNotification);
    repaint();
}

void TakeLaneItem::setFavorite(bool shouldBeFavorite)
{
    favorite = shouldBeFavorite;
    favoriteButton.setToggleState(favorite, juce::dontSendNotification);
    repaint();
}

//==============================================================================
// TrackTakeLaneContainer
//==============================================================================

TrackTakeLaneContainer::TrackTakeLaneContainer(const juce::String& name)
    : trackName(name)
{
    headerLabel.setText(trackName.toUpperCase(), juce::dontSendNotification);
    headerLabel.setFont(juce::Font(Layout::fontSizeLG).boldened());
    headerLabel.setColour(juce::Label::textColourId, juce::Colours::white);
    addAndMakeVisible(headerLabel);
}

int TrackTakeLaneContainer::getPreferredHeight() const
{
    const int numTakes = takeItems.size();
    const int takesHeight = numTakes > 0 ? (takeItemSpacing + numTakes * (takeItemHeight + takeItemSpacing)) : 0;
    return headerHeight + takesHeight + Layout::paddingSM;
}

void TrackTakeLaneContainer::paint(juce::Graphics& g)
{
    auto bounds = getLocalBounds().toFloat();
    
    // Container background
    g.setColour(juce::Colour(0xff1e272e).withAlpha(0.5f));
    g.fillRoundedRectangle(bounds, Layout::borderRadiusMD);
    
    // Header separator
    g.setColour(juce::Colour(0xff3498db).withAlpha(0.3f));
    g.fillRect(Layout::paddingMD, headerHeight - 1, getWidth() - Layout::paddingMD * 2, 1);
}

void TrackTakeLaneContainer::resized()
{
    auto bounds = getLocalBounds();
    
    headerLabel.setBounds(bounds.removeFromTop(headerHeight).reduced(Layout::paddingMD, 0));
    
    // Layout take items
    int y = headerHeight + takeItemSpacing;
    for (auto* item : takeItems)
    {
        item->setBounds(Layout::paddingSM, y, bounds.getWidth() - Layout::paddingSM * 2, takeItemHeight);
        y += takeItemHeight + takeItemSpacing;
    }
}

void TrackTakeLaneContainer::setTakes(const std::vector<TakeLane>& takes)
{
    takeItems.clear();
    selectedTakeId.clear();
    playingTakeId.clear();
    
    for (const auto& take : takes)
    {
        auto* item = new TakeLaneItem(take);
        item->onSelected = [this](const juce::String& takeId, const juce::String& midiPath)
        {
            handleTakeSelected(takeId, midiPath);
        };
        item->onPlayClicked = [this](const juce::String& takeId, const juce::String& midiPath)
        {
            handlePlayRequested(takeId, midiPath);
        };
        item->onStopClicked = [this]()
        {
            handleStopRequested();
        };
        auto updateAlpha = [this]()
        {
            bool anySolo = false;
            for (auto* i : takeItems)
                anySolo = anySolo || i->isSolo();

            for (auto* i : takeItems)
            {
                float a = 1.0f;
                if (i->isMuted())
                    a = 0.50f;
                if (anySolo && !i->isSolo())
                    a = 0.35f;
                i->setAlpha(a);
            }
        };

        item->onSoloToggled = [updateAlpha](const juce::String&, bool)
        {
            updateAlpha();
        };
        item->onMuteToggled = [updateAlpha](const juce::String&, bool)
        {
            updateAlpha();
        };
        takeItems.add(item);
        addAndMakeVisible(item);
    }
    
    // Select first take by default
    if (!takeItems.isEmpty())
    {
        takeItems[0]->setSelected(true);
        selectedTakeId = takeItems[0]->getTakeLane().takeId;
    }
    
    resized();
}

void TrackTakeLaneContainer::clearTakes()
{
    takeItems.clear();
    selectedTakeId.clear();
    resized();
}

void TrackTakeLaneContainer::selectTake(const juce::String& takeId)
{
    for (auto* item : takeItems)
    {
        bool shouldSelect = (item->getTakeLane().takeId == takeId);
        item->setSelected(shouldSelect);
    }
    selectedTakeId = takeId;
}

void TrackTakeLaneContainer::handlePlayRequested(const juce::String& takeId, const juce::String& midiPath)
{
    playingTakeId = takeId;
    for (auto* item : takeItems)
        item->setPlaying(item->getTakeLane().takeId == takeId);

    if (onPlayRequested)
        onPlayRequested(trackName, takeId, midiPath);
}

void TrackTakeLaneContainer::handleStopRequested()
{
    playingTakeId.clear();
    for (auto* item : takeItems)
        item->setPlaying(false);

    if (onStopRequested)
        onStopRequested(trackName);
}

void TrackTakeLaneContainer::handleTakeSelected(const juce::String& takeId, const juce::String& midiPath)
{
    selectTake(takeId);
    
    if (onTakeSelected)
    onTakeSelected(trackName, takeId, midiPath);
}

//==============================================================================
// TakeLanePanel
//==============================================================================

TakeLanePanel::TakeLanePanel()
{
    titleLabel.setText("Take Lanes", juce::dontSendNotification);
    titleLabel.setFont(juce::Font(Layout::fontSizeXL).boldened());
    titleLabel.setColour(juce::Label::textColourId, juce::Colours::white);
    addAndMakeVisible(titleLabel);
    
    renderButton.setColour(juce::TextButton::buttonColourId, juce::Colour(0xff27ae60));
    renderButton.onClick = [this]() { handleRenderClicked(); };
    addAndMakeVisible(renderButton);

    commitButton.setColour(juce::TextButton::buttonColourId, juce::Colour(0xff2980b9));
    commitButton.onClick = [this]() { handleCommitClicked(); };
    addAndMakeVisible(commitButton);

    revertButton.setColour(juce::TextButton::buttonColourId, juce::Colour(0xff8e44ad));
    revertButton.onClick = [this]() { handleRevertClicked(); };
    addAndMakeVisible(revertButton);
    
    emptyLabel.setText("Generate music with multiple takes to see options here.\nSet 'Takes' > 1 in generation settings.", 
                       juce::dontSendNotification);
    emptyLabel.setFont(Layout::fontSizeMD);
    emptyLabel.setColour(juce::Label::textColourId, juce::Colours::grey);
    emptyLabel.setJustificationType(juce::Justification::centred);
    addAndMakeVisible(emptyLabel);
    
    viewport.setViewedComponent(&containerHolder, false);
    viewport.setScrollBarsShown(true, false);
    addAndMakeVisible(viewport);
}

TakeLanePanel::~TakeLanePanel()
{
}

void TakeLanePanel::paint(juce::Graphics& g)
{
    g.fillAll(juce::Colour(0xff1a1a2e));
}

void TakeLanePanel::resized()
{
    auto bounds = getLocalBounds();
    
    // Header
    auto headerBounds = bounds.removeFromTop(40);
    titleLabel.setBounds(headerBounds.removeFromLeft(200).reduced(Layout::paddingMD));
    renderButton.setBounds(headerBounds.removeFromRight(140).reduced(Layout::paddingMD));
    revertButton.setBounds(headerBounds.removeFromRight(120).reduced(Layout::paddingMD));
    commitButton.setBounds(headerBounds.removeFromRight(120).reduced(Layout::paddingMD));
    
    // Main content area
    bounds.reduce(Layout::paddingMD, 0);
    
    if (trackContainers.isEmpty())
    {
        emptyLabel.setVisible(true);
        viewport.setVisible(false);
        emptyLabel.setBounds(bounds);
    }
    else
    {
        emptyLabel.setVisible(false);
        viewport.setVisible(true);
        viewport.setBounds(bounds);
        updateLayout();
    }
}

void TakeLanePanel::setAvailableTakes(const juce::String& takesJson)
{
    clearAllTakes();
    
    auto json = juce::JSON::parse(takesJson);
    if (!json.isObject())
        return;
    
    auto* obj = json.getDynamicObject();
    if (!obj)
        return;
    
    // Check for "tracks" key (direct response) or root object (tracks as keys)
    auto tracksVar = obj->getProperty("tracks");
    auto* tracksObj = tracksVar.isObject() ? tracksVar.getDynamicObject() : obj;
    
    if (!tracksObj)
        return;
    
    for (const auto& prop : tracksObj->getProperties())
    {
        juce::String trackName = prop.name.toString();
        auto takesArray = prop.value;
        
        if (!takesArray.isArray())
            continue;
        
        std::vector<TakeLane> takes;
        for (int i = 0; i < takesArray.size(); ++i)
        {
            takes.push_back(TakeLane::fromJson(takesArray[i]));
        }
        
        if (!takes.empty())
        {
            auto* container = new TrackTakeLaneContainer(trackName);
            container->setTakes(takes);
            container->onTakeSelected = [this](const juce::String& track, const juce::String& takeId, const juce::String& midiPath)
            {
                handleTrackTakeSelected(track, takeId, midiPath);
            };
            container->onPlayRequested = [this](const juce::String& track, const juce::String& takeId, const juce::String& midiPath)
            {
                handlePlayRequested(track, takeId, midiPath);
            };
            container->onStopRequested = [this](const juce::String& track)
            {
                handleStopRequested(track);
            };
            trackContainers.add(container);
            containerHolder.addAndMakeVisible(container);
        }
    }
    
    resized();
}

void TakeLanePanel::clearAllTakes()
{
    trackContainers.clear();
    resized();
}

void TakeLanePanel::confirmTakeSelection(const juce::String& track, const juce::String& takeId)
{
    for (auto* container : trackContainers)
    {
        if (container->getTrackName() == track)
        {
            container->selectTake(takeId);
            break;
        }
    }
}

void TakeLanePanel::addListener(Listener* listener)
{
    listeners.add(listener);
}

void TakeLanePanel::removeListener(Listener* listener)
{
    listeners.remove(listener);
}

void TakeLanePanel::handleTrackTakeSelected(const juce::String& track, const juce::String& takeId, const juce::String& midiPath)
{
    listeners.call([track, takeId, midiPath](Listener& l)
    {
        l.takeSelected(track, takeId, midiPath);
    });
}

void TakeLanePanel::handlePlayRequested(const juce::String& track, const juce::String& takeId, const juce::String& midiPath)
{
    listeners.call([track, takeId, midiPath](Listener& l)
    {
        l.takePlayRequested(track, takeId, midiPath);
    });
}

void TakeLanePanel::handleStopRequested(const juce::String& track)
{
    listeners.call([track](Listener& l)
    {
        l.takeStopRequested(track);
    });
}

void TakeLanePanel::handleRenderClicked()
{
    listeners.call([](Listener& l)
    {
        l.renderTakesRequested();
    });
}

void TakeLanePanel::handleCommitClicked()
{
    listeners.call([](Listener& l)
    {
        l.commitCompRequested();
    });
}

void TakeLanePanel::handleRevertClicked()
{
    listeners.call([](Listener& l)
    {
        l.revertCompRequested();
    });
}

void TakeLanePanel::updateLayout()
{
    int totalHeight = 0;
    for (auto* container : trackContainers)
        totalHeight += container->getPreferredHeight() + Layout::paddingMD;

    containerHolder.setBounds(0, 0, juce::jmax(0, viewport.getWidth() - 12), totalHeight);

    int y = 0;
    for (auto* container : trackContainers)
    {
        const int h = container->getPreferredHeight();
        container->setBounds(0, y, containerHolder.getWidth(), h);
        y += h + Layout::paddingMD;
    }
}
