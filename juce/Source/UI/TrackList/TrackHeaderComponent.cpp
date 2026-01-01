/*
  ==============================================================================

    TrackHeaderComponent.cpp
    
    Implementation of professional DAW-style track headers.

  ==============================================================================
*/

#include "TrackHeaderComponent.h"
#include "../Theme/ThemeManager.h"

namespace UI
{

//==============================================================================
// TrackHeaderComponent
//==============================================================================

TrackHeaderComponent::TrackHeaderComponent(int index)
    : trackIndex(index)
{
    trackName = "Track " + juce::String(index + 1);
    
    // Name label (editable on double-click)
    nameLabel.setText(trackName, juce::dontSendNotification);
    nameLabel.setFont(juce::Font(12.0f).boldened());
    nameLabel.setColour(juce::Label::textColourId, ThemeManager::getCurrentScheme().text);
    nameLabel.setEditable(false, true);  // Double-click to edit
    nameLabel.onTextChange = [this]() { onNameEdited(); };
    addAndMakeVisible(nameLabel);
    
    // Expand/collapse button
    expandButton.setButtonText(expanded ? juce::String(juce::CharPointer_UTF8("▼")) 
                                        : juce::String(juce::CharPointer_UTF8("▶")));
    expandButton.setColour(juce::TextButton::buttonColourId, juce::Colours::transparentBlack);
    expandButton.setColour(juce::TextButton::textColourOffId, ThemeManager::getCurrentScheme().textSecondary);
    expandButton.onClick = [this]() {
        setExpanded(!expanded);
        listeners.call(&Listener::trackExpandToggled, this, expanded);
    };
    addAndMakeVisible(expandButton);
    
    // Arm button (record enable)
    armButton.setColour(juce::TextButton::buttonColourId, ThemeManager::getSurface());
    armButton.setColour(juce::TextButton::buttonOnColourId, juce::Colours::red);
    armButton.setColour(juce::TextButton::textColourOffId, ThemeManager::getCurrentScheme().textSecondary);
    armButton.setColour(juce::TextButton::textColourOnId, juce::Colours::white);
    armButton.setClickingTogglesState(true);
    armButton.onClick = [this]() {
        armed = armButton.getToggleState();
        listeners.call(&Listener::trackArmToggled, this, armed);
        syncToProjectState();
    };
    addAndMakeVisible(armButton);
    
    // Mute button
    muteButton.setColour(juce::TextButton::buttonColourId, ThemeManager::getSurface());
    muteButton.setColour(juce::TextButton::buttonOnColourId, juce::Colour(0xFFFF6B00));  // Orange
    muteButton.setColour(juce::TextButton::textColourOffId, ThemeManager::getCurrentScheme().textSecondary);
    muteButton.setColour(juce::TextButton::textColourOnId, juce::Colours::white);
    muteButton.setClickingTogglesState(true);
    muteButton.onClick = [this]() {
        muted = muteButton.getToggleState();
        listeners.call(&Listener::trackMuteToggled, this, muted);
        syncToProjectState();
    };
    addAndMakeVisible(muteButton);
    
    // Solo button
    soloButton.setColour(juce::TextButton::buttonColourId, ThemeManager::getSurface());
    soloButton.setColour(juce::TextButton::buttonOnColourId, juce::Colours::yellow);
    soloButton.setColour(juce::TextButton::textColourOffId, ThemeManager::getCurrentScheme().textSecondary);
    soloButton.setColour(juce::TextButton::textColourOnId, juce::Colours::black);
    soloButton.setClickingTogglesState(true);
    soloButton.onClick = [this]() {
        soloed = soloButton.getToggleState();
        listeners.call(&Listener::trackSoloToggled, this, soloed);
        syncToProjectState();
    };
    addAndMakeVisible(soloButton);
}

TrackHeaderComponent::~TrackHeaderComponent()
{
    if (boundTrackNode.isValid())
        boundTrackNode.removeListener(this);
}

//==============================================================================
void TrackHeaderComponent::setTrackIndex(int index)
{
    trackIndex = index;
    if (trackName.startsWith("Track "))
        setTrackName("Track " + juce::String(index + 1));
    repaint();
}

void TrackHeaderComponent::setTrackName(const juce::String& name)
{
    trackName = name;
    nameLabel.setText(name, juce::dontSendNotification);
    syncToProjectState();
    repaint();
}

void TrackHeaderComponent::setTrackType(TrackType type)
{
    trackType = type;
    repaint();
}

void TrackHeaderComponent::setTrackColour(juce::Colour colour)
{
    trackColour = colour;
    repaint();
}

void TrackHeaderComponent::setSelected(bool isSelected)
{
    if (selected != isSelected)
    {
        selected = isSelected;
        repaint();
    }
}

void TrackHeaderComponent::setExpanded(bool isExpanded)
{
    if (expanded != isExpanded)
    {
        expanded = isExpanded;
        expandButton.setButtonText(expanded ? juce::String(juce::CharPointer_UTF8("▼")) 
                                            : juce::String(juce::CharPointer_UTF8("▶")));
        repaint();
    }
}

void TrackHeaderComponent::setArmed(bool isArmed)
{
    armed = isArmed;
    armButton.setToggleState(isArmed, juce::dontSendNotification);
    repaint();
}

void TrackHeaderComponent::bindToTrackNode(juce::ValueTree node)
{
    if (boundTrackNode.isValid())
        boundTrackNode.removeListener(this);
    
    boundTrackNode = node;
    
    if (boundTrackNode.isValid())
    {
        boundTrackNode.addListener(this);
        updateFromBoundNode();
    }
}

//==============================================================================
void TrackHeaderComponent::addListener(Listener* listener)
{
    listeners.add(listener);
}

void TrackHeaderComponent::removeListener(Listener* listener)
{
    listeners.remove(listener);
}

//==============================================================================
void TrackHeaderComponent::paint(juce::Graphics& g)
{
    auto bounds = getLocalBounds();
    
    // Background
    juce::Colour bgColour = ThemeManager::getSurface();
    if (selected)
        bgColour = ThemeManager::getCurrentScheme().accent.withAlpha(0.15f);
    
    g.setColour(bgColour);
    g.fillRect(bounds);
    
    // Color strip on left (like Ableton tracks)
    colorStripBounds = bounds.removeFromLeft(4);
    g.setColour(trackColour);
    g.fillRect(colorStripBounds);
    
    // Selection border
    if (selected)
    {
        g.setColour(ThemeManager::getCurrentScheme().accent);
        g.drawRect(getLocalBounds(), 2);
    }
    else
    {
        // Subtle border
        g.setColour(ThemeManager::getCurrentScheme().outline.withAlpha(0.5f));
        g.drawRect(getLocalBounds(), 1);
    }
    
    // Track type icon
    typeIconBounds = bounds.removeFromLeft(24).reduced(4);
    g.setColour(ThemeManager::getCurrentScheme().textSecondary);
    g.setFont(10.0f);
    
    juce::String typeIcon;
    switch (trackType)
    {
        case TrackType::MIDI:
            typeIcon = "MIDI";
            g.setColour(juce::Colour(0xFF4CAF50));  // Green for MIDI
            break;
        case TrackType::Audio:
            typeIcon = "AUD";
            g.setColour(juce::Colour(0xFF2196F3));  // Blue for Audio
            break;
        case TrackType::Master:
            typeIcon = "MST";
            g.setColour(juce::Colour(0xFFFF9800));  // Orange for Master
            break;
    }
    
    g.drawText(typeIcon, typeIconBounds, juce::Justification::centred);
    
    // Track index number
    auto indexBounds = bounds.removeFromLeft(20);
    g.setColour(ThemeManager::getCurrentScheme().textSecondary);
    g.setFont(10.0f);
    g.drawText(juce::String(trackIndex + 1), indexBounds, juce::Justification::centred);
}

void TrackHeaderComponent::resized()
{
    auto bounds = getLocalBounds();
    
    // Skip color strip area
    bounds.removeFromLeft(4);
    
    // Skip type icon area
    bounds.removeFromLeft(24);
    
    // Skip index area
    bounds.removeFromLeft(20);
    
    // Expand button on the left
    expandButton.setBounds(bounds.removeFromLeft(20));
    
    // Buttons on the right
    auto buttonArea = bounds.removeFromRight(80);
    int buttonSize = 20;
    int buttonPadding = 2;
    
    soloButton.setBounds(buttonArea.removeFromRight(buttonSize).reduced(buttonPadding));
    muteButton.setBounds(buttonArea.removeFromRight(buttonSize).reduced(buttonPadding));
    armButton.setBounds(buttonArea.removeFromRight(buttonSize).reduced(buttonPadding));
    
    // Name label takes remaining space
    nameLabel.setBounds(bounds.reduced(4, 2));
}

void TrackHeaderComponent::mouseDown(const juce::MouseEvent& event)
{
    if (!event.mods.isPopupMenu())
    {
        listeners.call(&Listener::trackSelected, this);
    }
}

void TrackHeaderComponent::mouseDoubleClick(const juce::MouseEvent& event)
{
    // Double-click on name area to edit
    if (nameLabel.getBounds().contains(event.getPosition()))
    {
        nameLabel.showEditor();
    }
}

//==============================================================================
void TrackHeaderComponent::valueTreePropertyChanged(juce::ValueTree& tree, const juce::Identifier& property)
{
    if (tree == boundTrackNode)
    {
        updateFromBoundNode();
    }
}

void TrackHeaderComponent::updateFromBoundNode()
{
    if (!boundTrackNode.isValid())
        return;
    
    // Update name
    juce::String name = boundTrackNode.getProperty(Project::IDs::name);
    if (name.isNotEmpty())
    {
        trackName = name;
        nameLabel.setText(name, juce::dontSendNotification);
    }
    
    // Update mute/solo
    muted = boundTrackNode.getProperty(Project::IDs::mute);
    soloed = boundTrackNode.getProperty(Project::IDs::solo);
    
    muteButton.setToggleState(muted, juce::dontSendNotification);
    soloButton.setToggleState(soloed, juce::dontSendNotification);
    
    repaint();
}

void TrackHeaderComponent::syncToProjectState()
{
    if (!boundTrackNode.isValid())
        return;
    
    boundTrackNode.setProperty(Project::IDs::name, trackName, nullptr);
    boundTrackNode.setProperty(Project::IDs::mute, muted, nullptr);
    boundTrackNode.setProperty(Project::IDs::solo, soloed, nullptr);
}

void TrackHeaderComponent::onNameEdited()
{
    trackName = nameLabel.getText();
    listeners.call(&Listener::trackNameChanged, this, trackName);
    syncToProjectState();
}


//==============================================================================
// TrackListComponent
//==============================================================================

TrackListComponent::TrackListComponent()
{
    viewport.setViewedComponent(&contentComponent, false);
    viewport.setScrollBarsShown(true, false);
    addAndMakeVisible(viewport);
    
    // Add track button
    addTrackButton.setColour(juce::TextButton::buttonColourId, ThemeManager::getSurface());
    addTrackButton.setColour(juce::TextButton::textColourOffId, ThemeManager::getCurrentScheme().textSecondary);
    addTrackButton.onClick = [this]() {
        addTrack(TrackType::MIDI);
    };
    addAndMakeVisible(addTrackButton);
    
    // Create default tracks
    setTrackCount(4);
}

TrackListComponent::~TrackListComponent()
{
    for (auto* header : trackHeaders)
        header->removeListener(this);
}

//==============================================================================
void TrackListComponent::setTrackCount(int count)
{
    // Remove excess
    while (trackHeaders.size() > count)
    {
        trackHeaders.getLast()->removeListener(this);
        trackHeaders.removeLast();
    }
    
    // Add new tracks
    while (trackHeaders.size() < count)
    {
        int index = trackHeaders.size();
        auto* header = trackHeaders.add(new TrackHeaderComponent(index));
        header->setTrackColour(getNextTrackColour());
        header->addListener(this);
        contentComponent.addAndMakeVisible(header);
    }
    
    updateLayout();
    listeners.call(&Listener::trackCountChanged, count);
}

void TrackListComponent::addTrack(TrackType type, const juce::String& name)
{
    int index = trackHeaders.size();
    auto* header = trackHeaders.add(new TrackHeaderComponent(index));
    header->setTrackType(type);
    header->setTrackColour(getNextTrackColour());
    
    if (name.isNotEmpty())
        header->setTrackName(name);
    else
        header->setTrackName("Track " + juce::String(index + 1));
    
    header->addListener(this);
    contentComponent.addAndMakeVisible(header);
    
    // Also add to project state if bound
    if (projectState)
    {
        // getTrackNode will create the track if it doesn't exist
        auto trackNode = projectState->getTrackNode(index);
        if (trackNode.isValid())
        {
            // Set the track name in the project state
            trackNode.setProperty(Project::IDs::name, header->getTrackName(), nullptr);
            header->bindToTrackNode(trackNode);
        }
    }
    
    updateLayout();
    listeners.call(&Listener::trackCountChanged, trackHeaders.size());
}

void TrackListComponent::removeTrack(int index)
{
    if (index >= 0 && index < trackHeaders.size())
    {
        trackHeaders[index]->removeListener(this);
        trackHeaders.remove(index);
        
        // Re-index remaining tracks
        for (int i = index; i < trackHeaders.size(); ++i)
            trackHeaders[i]->setTrackIndex(i);
        
        // Adjust selection
        if (selectedTrackIndex >= trackHeaders.size())
            selectedTrackIndex = trackHeaders.size() - 1;
        
        updateLayout();
        listeners.call(&Listener::trackCountChanged, trackHeaders.size());
    }
}

TrackHeaderComponent* TrackListComponent::getTrackHeader(int index)
{
    if (index >= 0 && index < trackHeaders.size())
        return trackHeaders[index];
    return nullptr;
}

void TrackListComponent::selectTrack(int index)
{
    if (index >= 0 && index < trackHeaders.size())
    {
        // Deselect previous
        if (selectedTrackIndex >= 0 && selectedTrackIndex < trackHeaders.size())
            trackHeaders[selectedTrackIndex]->setSelected(false);
        
        selectedTrackIndex = index;
        trackHeaders[index]->setSelected(true);
        
        listeners.call(&Listener::trackSelectionChanged, index);
    }
}

void TrackListComponent::bindToProject(Project::ProjectState& state)
{
    projectState = &state;
    
    // Get tracks from project state
    auto mixerNode = state.getMixerNode();
    juce::StringArray trackNames;
    
    for (const auto& child : mixerNode)
    {
        if (child.hasType(Project::IDs::TRACK))
            trackNames.add(child.getProperty(Project::IDs::name));
    }
    
    // If no tracks, create defaults
    if (trackNames.isEmpty())
    {
        for (int i = 0; i < 4; ++i)
            trackNames.add("Track " + juce::String(i + 1));
    }
    
    // Update track count and bind to nodes
    setTrackCount(trackNames.size());
    
    for (int i = 0; i < trackHeaders.size(); ++i)
    {
        trackHeaders[i]->setTrackName(trackNames[i]);
        
        auto trackNode = state.getTrackNode(i);
        if (trackNode.isValid())
            trackHeaders[i]->bindToTrackNode(trackNode);
    }
    
    // Select first track
    if (!trackHeaders.isEmpty())
        selectTrack(0);
}

//==============================================================================
void TrackListComponent::addListener(Listener* listener)
{
    listeners.add(listener);
}

void TrackListComponent::removeListener(Listener* listener)
{
    listeners.remove(listener);
}

//==============================================================================
void TrackListComponent::paint(juce::Graphics& g)
{
    g.fillAll(ThemeManager::getCurrentScheme().background);
}

void TrackListComponent::resized()
{
    auto bounds = getLocalBounds();
    
    // Add track button at bottom
    addTrackButton.setBounds(bounds.removeFromBottom(24).reduced(4, 2));
    
    // Viewport takes rest
    viewport.setBounds(bounds);
    
    updateLayout();
}

//==============================================================================
void TrackListComponent::trackSelected(TrackHeaderComponent* track)
{
    selectTrack(track->getTrackIndex());
}

void TrackListComponent::trackExpandToggled(TrackHeaderComponent* track, bool expanded)
{
    updateLayout();
    listeners.call(&Listener::trackExpandedChanged, track->getTrackIndex(), expanded);
}

void TrackListComponent::trackArmToggled(TrackHeaderComponent* track, bool armed)
{
    DBG("Track " + juce::String(track->getTrackIndex() + 1) + " arm: " + (armed ? "ON" : "OFF"));
}

void TrackListComponent::trackMuteToggled(TrackHeaderComponent* track, bool muted)
{
    DBG("Track " + juce::String(track->getTrackIndex() + 1) + " mute: " + (muted ? "ON" : "OFF"));
}

void TrackListComponent::trackSoloToggled(TrackHeaderComponent* track, bool soloed)
{
    DBG("Track " + juce::String(track->getTrackIndex() + 1) + " solo: " + (soloed ? "ON" : "OFF"));
}

void TrackListComponent::trackNameChanged(TrackHeaderComponent* track, const juce::String& newName)
{
    DBG("Track " + juce::String(track->getTrackIndex() + 1) + " renamed to: " + newName);
}

//==============================================================================
void TrackListComponent::updateLayout()
{
    int y = 0;
    int width = viewport.getWidth() - viewport.getScrollBarThickness();
    
    for (auto* header : trackHeaders)
    {
        int height = header->isExpanded() ? expandedTrackHeight : collapsedTrackHeight;
        header->setBounds(0, y, width, height);
        y += height;
    }
    
    contentComponent.setSize(width, y);
}

juce::Colour TrackListComponent::getNextTrackColour()
{
    int index = trackHeaders.size() % trackColours.size();
    return trackColours[index];
}

} // namespace UI
