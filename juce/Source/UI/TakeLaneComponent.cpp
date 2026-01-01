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
    playButton.onClick = [this]()
    {
        if (onPlayClicked)
            onPlayClicked(takeLane.takeId);
    };
    addAndMakeVisible(playButton);
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
    
    g.setColour(bgColour);
    g.fillRoundedRectangle(bounds.reduced(1), Layout::borderRadiusSM);
    
    // Selection indicator
    if (selected)
    {
        g.setColour(juce::Colour(0xff2980b9));
        g.fillRoundedRectangle(bounds.removeFromLeft(4).reduced(0, 2), 2.0f);
    }
    
    // Take ID
    g.setColour(juce::Colours::white);
    g.setFont(Layout::fontSizeMD);
    g.drawText(takeLane.takeId, 40, 0, 100, getHeight(), juce::Justification::centredLeft);
    
    // Variation type badge
    auto badgeBounds = juce::Rectangle<float>(145, (getHeight() - 18) / 2.0f, 70, 18);
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
    g.drawText("seed: " + juce::String(takeLane.seed), 220, 0, 80, getHeight(), juce::Justification::centredLeft);
}

void TakeLaneItem::resized()
{
    auto bounds = getLocalBounds();
    playButton.setBounds(8, (bounds.getHeight() - 24) / 2, 28, 24);
}

void TakeLaneItem::mouseDown(const juce::MouseEvent& e)
{
    if (!selected && onSelected)
        onSelected(takeLane.takeId);
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
    
    for (const auto& take : takes)
    {
        auto* item = new TakeLaneItem(take);
        item->onSelected = [this](const juce::String& takeId) { handleTakeSelected(takeId); };
        item->onPlayClicked = [this](const juce::String& takeId)
        {
            if (onPlayRequested)
                onPlayRequested(trackName, takeId);
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

void TrackTakeLaneContainer::handleTakeSelected(const juce::String& takeId)
{
    selectTake(takeId);
    
    if (onTakeSelected)
        onTakeSelected(trackName, takeId);
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
    renderButton.setBounds(headerBounds.removeFromRight(130).reduced(Layout::paddingMD));
    
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
            container->onTakeSelected = [this](const juce::String& track, const juce::String& takeId)
            {
                handleTrackTakeSelected(track, takeId);
            };
            container->onPlayRequested = [this](const juce::String& track, const juce::String& takeId)
            {
                handlePlayRequested(track, takeId);
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

void TakeLanePanel::handleTrackTakeSelected(const juce::String& track, const juce::String& takeId)
{
    listeners.call([track, takeId](Listener& l)
    {
        l.takeSelected(track, takeId);
    });
}

void TakeLanePanel::handlePlayRequested(const juce::String& track, const juce::String& takeId)
{
    listeners.call([track, takeId](Listener& l)
    {
        l.takePlayRequested(track, takeId);
    });
}

void TakeLanePanel::handleRenderClicked()
{
    listeners.call([](Listener& l)
    {
        l.renderTakesRequested();
    });
}

void TakeLanePanel::updateLayout()
{
    // Calculate total height needed for all containers
    int totalHeight = 0;
    
    for (auto* container : trackContainers)
    {
        // Each container: header + takes
        int containerHeight = 28 + 2; // header + spacing
        auto* takeItems = reinterpret_cast<juce::OwnedArray<TakeLaneItem>*>(
            static_cast<char*>(static_cast<void*>(container)) + 
            sizeof(juce::String) * 2 + // trackName, selectedTakeId
            sizeof(juce::Label) // headerLabel
        );
        
        // Safer: just estimate based on track name
        containerHeight += 4 * (36 + 2); // Assume max 4 takes per track for sizing
        
        totalHeight += containerHeight + Layout::paddingMD;
    }
    
    // Set container holder size
    containerHolder.setBounds(0, 0, viewport.getWidth() - 12, totalHeight);
    
    // Layout containers
    int y = 0;
    for (auto* container : trackContainers)
    {
        int numTakes = 3; // Default estimate - TODO: expose count from container
        int containerHeight = 28 + 2 + numTakes * (36 + 2) + Layout::paddingMD;
        container->setBounds(0, y, containerHolder.getWidth(), containerHeight);
        y += containerHeight + Layout::paddingMD;
    }
}
