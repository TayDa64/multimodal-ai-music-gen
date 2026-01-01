/*
  ==============================================================================

    TrackHeaderComponent.h
    
    Professional DAW-style track header with:
    - Track type indicator (MIDI/Audio)
    - Color-coded track identification
    - Arm/Monitor/Mute/Solo buttons
    - Input selector
    - Expand/collapse for piano roll

  ==============================================================================
*/

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include "../../Project/ProjectState.h"

namespace UI
{

//==============================================================================
/**
    Track types supported by the system.
*/
enum class TrackType
{
    MIDI,
    Audio,
    Master
};

//==============================================================================
/**
    Individual track header component - displays track info and controls.
    Similar to Pro Tools/Ableton track headers.
*/
class TrackHeaderComponent : public juce::Component,
                              public juce::ValueTree::Listener
{
public:
    TrackHeaderComponent(int trackIndex = 0);
    ~TrackHeaderComponent() override;

    //==============================================================================
    /** Set the track index this header represents. */
    void setTrackIndex(int index);
    int getTrackIndex() const { return trackIndex; }
    
    /** Set the track name. */
    void setTrackName(const juce::String& name);
    juce::String getTrackName() const { return trackName; }
    
    /** Set the track type (MIDI/Audio/Master). */
    void setTrackType(TrackType type);
    TrackType getTrackType() const { return trackType; }
    
    /** Set the track color for identification. */
    void setTrackColour(juce::Colour colour);
    juce::Colour getTrackColour() const { return trackColour; }
    
    /** Get/set selected state. */
    void setSelected(bool isSelected);
    bool isSelected() const { return selected; }
    
    /** Get/set expanded state (shows piano roll). */
    void setExpanded(bool isExpanded);
    bool isExpanded() const { return expanded; }
    
    /** Get/set arm state. */
    void setArmed(bool isArmed);
    bool isArmed() const { return armed; }
    
    /** Bind to a project state track node. */
    void bindToTrackNode(juce::ValueTree trackNode);
    
    //==============================================================================
    /** Listener interface for track events. */
    class Listener
    {
    public:
        virtual ~Listener() = default;
        
        virtual void trackSelected(TrackHeaderComponent* track) = 0;
        virtual void trackExpandToggled(TrackHeaderComponent* track, bool expanded) = 0;
        virtual void trackArmToggled(TrackHeaderComponent* track, bool armed) = 0;
        virtual void trackMuteToggled(TrackHeaderComponent* track, bool muted) = 0;
        virtual void trackSoloToggled(TrackHeaderComponent* track, bool soloed) = 0;
        virtual void trackNameChanged(TrackHeaderComponent* track, const juce::String& newName) = 0;
    };
    
    void addListener(Listener* listener);
    void removeListener(Listener* listener);
    
    //==============================================================================
    void paint(juce::Graphics& g) override;
    void resized() override;
    void mouseDown(const juce::MouseEvent& event) override;
    void mouseDoubleClick(const juce::MouseEvent& event) override;
    
    // ValueTree::Listener
    void valueTreePropertyChanged(juce::ValueTree& tree, const juce::Identifier& property) override;
    void valueTreeChildAdded(juce::ValueTree&, juce::ValueTree&) override {}
    void valueTreeChildRemoved(juce::ValueTree&, juce::ValueTree&, int) override {}
    void valueTreeChildOrderChanged(juce::ValueTree&, int, int) override {}
    void valueTreeParentChanged(juce::ValueTree&) override {}

private:
    int trackIndex = 0;
    juce::String trackName = "Track 1";
    TrackType trackType = TrackType::MIDI;
    juce::Colour trackColour = juce::Colours::cyan;
    bool selected = false;
    bool expanded = false;
    bool armed = false;
    bool muted = false;
    bool soloed = false;
    
    juce::ValueTree boundTrackNode;
    
    // UI Components
    juce::Label nameLabel;
    juce::TextButton expandButton { "▶" };
    juce::TextButton armButton { "R" };
    juce::TextButton muteButton { "M" };
    juce::TextButton soloButton { "S" };
    
    // Track type icon area (drawn in paint)
    juce::Rectangle<int> typeIconBounds;
    juce::Rectangle<int> colorStripBounds;
    
    juce::ListenerList<Listener> listeners;
    
    void updateFromBoundNode();
    void syncToProjectState();
    void onNameEdited();
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(TrackHeaderComponent)
};


//==============================================================================
/**
    Track list component containing all track headers.
    Similar to Pro Tools track list or Ableton Session view rows.
*/
class TrackListComponent : public juce::Component,
                            public TrackHeaderComponent::Listener
{
public:
    TrackListComponent();
    ~TrackListComponent() override;
    
    //==============================================================================
    /** Set the number of tracks. */
    void setTrackCount(int count);
    int getTrackCount() const { return trackHeaders.size(); }
    
    /** Add a new track. */
    void addTrack(TrackType type = TrackType::MIDI, const juce::String& name = "");
    
    /** Remove a track. */
    void removeTrack(int index);
    
    /** Get track header at index. */
    TrackHeaderComponent* getTrackHeader(int index);
    
    /** Get currently selected track index. */
    int getSelectedTrackIndex() const { return selectedTrackIndex; }
    
    /** Set the selected track. */
    void selectTrack(int index);
    
    /** Bind to project state. */
    void bindToProject(Project::ProjectState& projectState);
    
    /** Get collapsed/expanded track height. */
    int getCollapsedTrackHeight() const { return collapsedTrackHeight; }
    int getExpandedTrackHeight() const { return expandedTrackHeight; }
    
    void setCollapsedTrackHeight(int height) { collapsedTrackHeight = height; }
    void setExpandedTrackHeight(int height) { expandedTrackHeight = height; }
    
    //==============================================================================
    /** Listener interface. */
    class Listener
    {
    public:
        virtual ~Listener() = default;
        virtual void trackSelectionChanged(int trackIndex) = 0;
        virtual void trackCountChanged(int newCount) = 0;
        virtual void trackExpandedChanged(int trackIndex, bool expanded) = 0;
    };
    
    void addListener(Listener* listener);
    void removeListener(Listener* listener);
    
    //==============================================================================
    void paint(juce::Graphics& g) override;
    void resized() override;
    
    // TrackHeaderComponent::Listener
    void trackSelected(TrackHeaderComponent* track) override;
    void trackExpandToggled(TrackHeaderComponent* track, bool expanded) override;
    void trackArmToggled(TrackHeaderComponent* track, bool armed) override;
    void trackMuteToggled(TrackHeaderComponent* track, bool muted) override;
    void trackSoloToggled(TrackHeaderComponent* track, bool soloed) override;
    void trackNameChanged(TrackHeaderComponent* track, const juce::String& newName) override;

private:
    juce::OwnedArray<TrackHeaderComponent> trackHeaders;
    Project::ProjectState* projectState = nullptr;
    
    int selectedTrackIndex = 0;
    int collapsedTrackHeight = 40;
    int expandedTrackHeight = 120;
    
    // Track colors palette (like Ableton/Pro Tools)
    juce::Array<juce::Colour> trackColours = {
        juce::Colour(0xFFE91E63),  // Pink
        juce::Colour(0xFF2196F3),  // Blue
        juce::Colour(0xFF4CAF50),  // Green
        juce::Colour(0xFFFF9800),  // Orange
        juce::Colour(0xFF9C27B0),  // Purple
        juce::Colour(0xFF00BCD4),  // Cyan
        juce::Colour(0xFFFFEB3B),  // Yellow
        juce::Colour(0xFFF44336),  // Red
    };
    
    juce::TextButton addTrackButton { "+" };
    
    juce::Viewport viewport;
    juce::Component contentComponent;
    
    juce::ListenerList<Listener> listeners;
    
    void updateLayout();
    juce::Colour getNextTrackColour();
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(TrackListComponent)
};

} // namespace UI
