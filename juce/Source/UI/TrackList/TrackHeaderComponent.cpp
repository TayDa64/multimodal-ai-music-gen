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
    
    // Name label (editable on double-click, single line) - MPC style compact
    nameLabel.setText(trackName, juce::dontSendNotification);
    nameLabel.setFont(juce::Font(10.0f));
    nameLabel.setColour(juce::Label::textColourId, ThemeManager::getCurrentScheme().text);
    nameLabel.setEditable(false, true);  // Double-click to edit
    nameLabel.setMinimumHorizontalScale(1.0f);
    nameLabel.setJustificationType(juce::Justification::centredLeft);
    nameLabel.onTextChange = [this]() { onNameEdited(); };
    addAndMakeVisible(nameLabel);
    
    // Instrument/Kit dropdown (MPC style) 
    instrumentCombo.setTextWhenNothingSelected("Select Instrument...");
    instrumentCombo.addItem("Default (Sine)", 1);
    instrumentCombo.setSelectedId(1, juce::dontSendNotification);
    instrumentCombo.setColour(juce::ComboBox::backgroundColourId, ThemeManager::getSurface().brighter(0.1f));
    instrumentCombo.setColour(juce::ComboBox::textColourId, ThemeManager::getCurrentScheme().textSecondary);
    instrumentCombo.setColour(juce::ComboBox::outlineColourId, juce::Colours::transparentBlack);
    instrumentCombo.onChange = [this]() { onInstrumentSelected(); };
    addAndMakeVisible(instrumentCombo);
    
    // Piano Roll button - opens this track in Piano Roll view
    expandButton.setButtonText(juce::String(juce::CharPointer_UTF8("\xe2\x96\xb6")));  // Always show ▶ (play/edit icon)
    expandButton.setColour(juce::TextButton::buttonColourId, juce::Colours::transparentBlack);
    expandButton.setColour(juce::TextButton::textColourOffId, ThemeManager::getCurrentScheme().textSecondary);
    expandButton.setTooltip("Edit in Piano Roll");
    expandButton.onClick = [this]() {
        // Signal to open Piano Roll for this track (expanded=true means "open piano roll")
        listeners.call(&Listener::trackExpandToggled, this, true);
    };
    addAndMakeVisible(expandButton);
    
    // Arm button (record enable) - hidden by default in compact mode, shown on hover/expand
    armButton.setColour(juce::TextButton::buttonColourId, ThemeManager::getSurface());
    armButton.setColour(juce::TextButton::buttonOnColourId, juce::Colours::red);
    armButton.setColour(juce::TextButton::textColourOffId, ThemeManager::getCurrentScheme().textSecondary);
    armButton.setColour(juce::TextButton::textColourOnId, juce::Colours::white);
    armButton.setClickingTogglesState(true);
    armButton.setTooltip("Record Arm");
    armButton.onClick = [this]() {
        armed = armButton.getToggleState();
        listeners.call(&Listener::trackArmToggled, this, armed);
        syncToProjectState();
    };
    armButton.setVisible(false);  // Hidden in compact MPC mode
    addAndMakeVisible(armButton);
    
    // Mute button - MPC style compact (small inline toggle)
    muteButton.setColour(juce::TextButton::buttonColourId, ThemeManager::getSurface().brighter(0.05f));
    muteButton.setColour(juce::TextButton::buttonOnColourId, juce::Colour(0xFFFF6B00));  // Orange when active
    muteButton.setColour(juce::TextButton::textColourOffId, ThemeManager::getCurrentScheme().textSecondary);
    muteButton.setColour(juce::TextButton::textColourOnId, juce::Colours::white);
    muteButton.setClickingTogglesState(true);
    muteButton.setTooltip("Mute");
    muteButton.onClick = [this]() {
        muted = muteButton.getToggleState();
        listeners.call(&Listener::trackMuteToggled, this, muted);
        syncToProjectState();
    };
    addAndMakeVisible(muteButton);
    
    // Solo button - MPC style compact (small inline toggle)
    soloButton.setColour(juce::TextButton::buttonColourId, ThemeManager::getSurface().brighter(0.05f));
    soloButton.setColour(juce::TextButton::buttonOnColourId, juce::Colours::yellow);
    soloButton.setColour(juce::TextButton::textColourOffId, ThemeManager::getCurrentScheme().textSecondary);
    soloButton.setColour(juce::TextButton::textColourOnId, juce::Colours::black);
    soloButton.setClickingTogglesState(true);
    soloButton.setTooltip("Solo");
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
    // No longer toggles visual state - button always shows ▶
    // This method kept for API compatibility but doesn't change appearance
    expanded = isExpanded;
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
    
    // Background - darker for MPC look
    juce::Colour bgColour = ThemeManager::getSurface().darker(0.1f);
    if (selected)
        bgColour = ThemeManager::getCurrentScheme().accent.withAlpha(0.2f);
    
    g.setColour(bgColour);
    g.fillRect(bounds);
    
    // Track number box with track color (MPC style)
    trackNumberBounds = bounds.removeFromLeft(24);
    g.setColour(trackColour);
    g.fillRect(trackNumberBounds);
    
    // Track number text (white on colored background)
    g.setColour(juce::Colours::white);
    g.setFont(juce::Font(10.0f).boldened());
    g.drawText(juce::String(trackIndex + 1), trackNumberBounds, juce::Justification::centred);
    
    // Subtle bottom border like MPC
    g.setColour(ThemeManager::getCurrentScheme().outline.withAlpha(0.3f));
    g.drawHorizontalLine(getHeight() - 1, 0.0f, (float)getWidth());
    
    // Selection highlight
    if (selected)
    {
        g.setColour(ThemeManager::getCurrentScheme().accent.withAlpha(0.5f));
        g.drawRect(getLocalBounds(), 1);
    }
}

void TrackHeaderComponent::resized()
{
    auto bounds = getLocalBounds();
    int height = bounds.getHeight();
    
    // Skip track number box area (painted)
    bounds.removeFromLeft(24);
    
    // Small padding
    bounds.removeFromLeft(4);
    
    // M/S buttons on the right - MPC style tiny toggles (16x16)
    auto buttonArea = bounds.removeFromRight(40);
    int buttonSize = 16;
    int buttonY = (height - buttonSize) / 2;
    int buttonPadding = 4;
    
    int x = buttonArea.getX();
    muteButton.setBounds(x, buttonY, buttonSize, buttonSize);
    x += buttonSize + buttonPadding;
    soloButton.setBounds(x, buttonY, buttonSize, buttonSize);
    
    // Arm button (hidden in compact mode)
    armButton.setBounds(0, 0, 0, 0);
    
    // Expand button (small, before name)
    expandButton.setBounds(bounds.removeFromLeft(16).reduced(0, (height - 14) / 2));
    
    // Split remaining space: track name (45%) and instrument dropdown (55%)
    int nameWidth = (int)(bounds.getWidth() * 0.45f);
    int comboWidth = bounds.getWidth() - nameWidth - 4;
    
    nameLabel.setBounds(bounds.removeFromLeft(nameWidth).reduced(2, (height - 16) / 2));
    bounds.removeFromLeft(4);  // gap
    instrumentCombo.setBounds(bounds.removeFromLeft(comboWidth).reduced(0, (height - 18) / 2));
}

void TrackHeaderComponent::mouseDown(const juce::MouseEvent& event)
{
    if (event.mods.isPopupMenu())
    {
        // Show context menu with delete option
        juce::PopupMenu menu;
        menu.addItem(1, "Rename Track");
        menu.addSeparator();
        menu.addItem(2, "Delete Track");
        
        menu.showMenuAsync(juce::PopupMenu::Options().withTargetScreenArea(
            juce::Rectangle<int>(event.getScreenX(), event.getScreenY(), 1, 1)),
            [this](int result) {
                if (result == 1)
                    nameLabel.showEditor();
                else if (result == 2)
                    listeners.call(&Listener::trackDeleteRequested, this);
            });
    }
    else
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

void TrackHeaderComponent::setAvailableInstruments(const std::map<juce::String, std::vector<const mmg::InstrumentDefinition*>>& byCategory)
{
    instrumentItems.clear();
    
    // Add default sine instrument
    InstrumentMenuItem defaultItem;
    defaultItem.id = "default_sine";
    defaultItem.name = "Default (Sine)";
    defaultItem.category = "Default";
    instrumentItems.push_back(defaultItem);
    
    // Add instruments from each category
    for (const auto& [category, instruments] : byCategory)
    {
        for (const auto* inst : instruments)
        {
            InstrumentMenuItem item;
            item.id = inst->id;
            item.name = inst->name;
            item.category = category;
            instrumentItems.push_back(item);
        }
    }
    
    rebuildInstrumentCombo();
}

void TrackHeaderComponent::rebuildInstrumentCombo()
{
    instrumentCombo.clear();
    
    juce::String currentCategory;
    int itemId = 1;
    
    for (const auto& item : instrumentItems)
    {
        // Add category header if category changed
        if (item.category != currentCategory)
        {
            if (itemId > 1)  // Add separator before new categories (except first)
                instrumentCombo.addSeparator();
            
            // Add category as disabled item (header)
            instrumentCombo.addSectionHeading(item.category);
            currentCategory = item.category;
        }
        
        instrumentCombo.addItem(item.name, itemId);
        itemId++;
    }
    
    // Select the current instrument or default
    if (!selectedInstrumentId.isEmpty())
        setSelectedInstrument(selectedInstrumentId);
    else if (!instrumentItems.empty())
        instrumentCombo.setSelectedId(1, juce::dontSendNotification);
}

void TrackHeaderComponent::onInstrumentSelected()
{
    int selectedIndex = instrumentCombo.getSelectedId() - 1;  // 1-based to 0-based
    
    if (selectedIndex >= 0 && selectedIndex < (int)instrumentItems.size())
    {
        selectedInstrumentId = instrumentItems[selectedIndex].id;
        listeners.call(&Listener::trackInstrumentChanged, this, selectedInstrumentId);
    }
}

void TrackHeaderComponent::setSelectedInstrument(const juce::String& instrumentId)
{
    selectedInstrumentId = instrumentId;
    
    // Find the instrument in the list
    for (size_t i = 0; i < instrumentItems.size(); ++i)
    {
        if (instrumentItems[i].id == instrumentId)
        {
            instrumentCombo.setSelectedId((int)i + 1, juce::dontSendNotification);
            return;
        }
    }
    
    // If not found, select default
    if (!instrumentItems.empty())
        instrumentCombo.setSelectedId(1, juce::dontSendNotification);
}

//==============================================================================
// TrackListComponent
//==============================================================================

TrackListComponent::TrackListComponent()
{
    viewport.setViewedComponent(&contentComponent, false);
    viewport.setScrollBarsShown(true, false);
    addAndMakeVisible(viewport);
    
    // MPC-style section headers
    midiSectionHeader = std::make_unique<TrackSectionHeader>("MIDI", juce::Colour(0xFF00D4AA));
    contentComponent.addAndMakeVisible(*midiSectionHeader);
    
    audioSectionHeader = std::make_unique<TrackSectionHeader>("AUDIO", juce::Colour(0xFF2196F3));
    contentComponent.addAndMakeVisible(*audioSectionHeader);
    audioSectionHeader->setVisible(false);  // Hidden until we have audio tracks
    
    // Add track button - MPC style
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
        
        // Set available instruments if we have them
        if (!availableInstruments.empty())
            header->setAvailableInstruments(availableInstruments);
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
    
    // Set available instruments if we have them
    if (!availableInstruments.empty())
        header->setAvailableInstruments(availableInstruments);
    
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

void TrackListComponent::trackDeleteRequested(TrackHeaderComponent* track)
{
    int index = track->getTrackIndex();
    
    // Don't allow deleting the last track
    if (trackHeaders.size() <= 1)
    {
        DBG("Cannot delete the last track");
        return;
    }
    
    DBG("Track " + juce::String(index + 1) + " delete requested");
    removeTrack(index);
}

void TrackListComponent::trackInstrumentChanged(TrackHeaderComponent* track, const juce::String& instrumentId)
{
    int index = track->getTrackIndex();
    DBG("Track " + juce::String(index + 1) + " instrument changed to: " + instrumentId);
    listeners.call(&Listener::trackInstrumentSelected, index, instrumentId);
}

void TrackListComponent::setAvailableInstruments(const std::map<juce::String, std::vector<const mmg::InstrumentDefinition*>>& byCategory)
{
    availableInstruments = byCategory;
    
    // Propagate to all track headers
    for (auto* header : trackHeaders)
    {
        header->setAvailableInstruments(byCategory);
    }
}

//==============================================================================
void TrackListComponent::updateLayout()
{
    int y = 0;
    int width = viewport.getWidth() - viewport.getScrollBarThickness();
    if (width <= 0) width = 200;  // Fallback width
    
    // Count MIDI and Audio tracks
    int midiCount = 0;
    int audioCount = 0;
    for (auto* header : trackHeaders)
    {
        if (header->getTrackType() == TrackType::Audio)
            audioCount++;
        else
            midiCount++;
    }
    
    // MIDI section header (always visible if we have MIDI tracks)
    if (midiCount > 0)
    {
        midiSectionHeader->setVisible(true);
        midiSectionHeader->setBounds(0, y, width, sectionHeaderHeight);
        y += sectionHeaderHeight;
        
        // Layout MIDI tracks - all uniform height
        for (auto* header : trackHeaders)
        {
            if (header->getTrackType() != TrackType::Audio)
            {
                header->setBounds(0, y, width, trackHeight);
                y += trackHeight;
            }
        }
    }
    
    // AUDIO section header (visible if we have audio tracks)
    if (audioCount > 0)
    {
        audioSectionHeader->setVisible(true);
        audioSectionHeader->setBounds(0, y, width, sectionHeaderHeight);
        y += sectionHeaderHeight;
        
        // Layout Audio tracks - all uniform height
        for (auto* header : trackHeaders)
        {
            if (header->getTrackType() == TrackType::Audio)
            {
                header->setBounds(0, y, width, trackHeight);
                y += trackHeight;
            }
        }
    }
    else
    {
        audioSectionHeader->setVisible(false);
    }
    
    contentComponent.setSize(width, y);
}

juce::Colour TrackListComponent::getNextTrackColour()
{
    int index = trackHeaders.size() % trackColours.size();
    return trackColours[index];
}

} // namespace UI
