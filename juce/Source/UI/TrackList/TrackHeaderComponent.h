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
#include "../../Audio/ExpansionInstrumentLoader.h"
#include <map>

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
    Instrument category and instrument list for UI.
*/
struct InstrumentMenuItem
{
    juce::String id;
    juce::String name;
    juce::String category;
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
    // Instrument Selection
    //==============================================================================
    
    /** Set available instruments from expansion loader. */
    void setAvailableInstruments(const std::map<juce::String, std::vector<const mmg::InstrumentDefinition*>>& byCategory);
    
    /** Get currently selected instrument ID. */
    juce::String getSelectedInstrumentId() const { return selectedInstrumentId; }
    
    /** Set the current instrument (by ID). */
    void setSelectedInstrument(const juce::String& instrumentId);
    
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
        virtual void trackDeleteRequested(TrackHeaderComponent* track) = 0;
        virtual void trackInstrumentChanged(TrackHeaderComponent* track, const juce::String& instrumentId) = 0;
        virtual void trackLoadSF2Requested(TrackHeaderComponent* track) {}
        virtual void trackLoadSFZRequested(TrackHeaderComponent* track) {}
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
    
    // Instrument selection
    juce::String selectedInstrumentId;
    std::vector<InstrumentMenuItem> instrumentItems;  // Flattened list for combo indexing
    
    // UI Components
    juce::Label nameLabel;
    juce::ComboBox instrumentCombo;  // MPC-style instrument/kit selector
    juce::TextButton expandButton { "▶" };
    juce::TextButton armButton { "R" };
    juce::TextButton muteButton { "M" };
    juce::TextButton soloButton { "S" };
    
    // Track areas (for paint)
    juce::Rectangle<int> trackNumberBounds;  // MPC-style colored track number box
    
    juce::ListenerList<Listener> listeners;
    
    void updateFromBoundNode();
    void syncToProjectState();
    void onNameEdited();
    void onInstrumentSelected();
    void rebuildInstrumentCombo();
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(TrackHeaderComponent)
};


//==============================================================================
/**
    MPC-style section header for grouping tracks by type.
*/
class TrackSectionHeader : public juce::Component
{
public:
    TrackSectionHeader(const juce::String& title, juce::Colour colour)
        : sectionTitle(title), sectionColour(colour) {}
    
    void paint(juce::Graphics& g) override
    {
        auto bounds = getLocalBounds();
        
        // Dark background like MPC
        g.setColour(juce::Colour(0xFF1A1A1A));
        g.fillRect(bounds);
        
        // Section title
        g.setColour(sectionColour);
        g.setFont(juce::Font(9.0f).boldened());
        g.drawText(sectionTitle, bounds.reduced(8, 0), juce::Justification::centredLeft);
        
        // Bottom border
        g.setColour(sectionColour.withAlpha(0.3f));
        g.drawHorizontalLine(getHeight() - 1, 0.0f, (float)getWidth());
    }
    
private:
    juce::String sectionTitle;
    juce::Colour sectionColour;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(TrackSectionHeader)
};


//==============================================================================
/**
    Track list component containing all track headers.
    Similar to MPC track list with MIDI/Audio section headers.
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
    
    /** Set available instruments for all tracks (from expansion loader). */
    void setAvailableInstruments(const std::map<juce::String, std::vector<const mmg::InstrumentDefinition*>>& byCategory);
    
    /** Get uniform track height for all tracks. */
    int getTrackHeight() const { return trackHeight; }
    void setTrackHeight(int height) { trackHeight = height; }
    
    /** Get section header height for layout alignment. */
    int getSectionHeaderHeight() const { return sectionHeaderHeight; }
    
    /** Get the viewport for scroll synchronization. */
    juce::Viewport& getViewport() { return viewport; }
    
    //==============================================================================
    /** Listener interface. */
    class Listener
    {
    public:
        virtual ~Listener() = default;
        virtual void trackSelectionChanged(int trackIndex) = 0;
        virtual void trackCountChanged(int newCount) = 0;
        virtual void trackExpandedChanged(int trackIndex, bool expanded) = 0;
        virtual void trackInstrumentSelected(int trackIndex, const juce::String& instrumentId) {}
        virtual void trackLoadSF2Requested(int trackIndex) {}
        virtual void trackLoadSFZRequested(int trackIndex) {}
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
    void trackDeleteRequested(TrackHeaderComponent* track) override;
    void trackInstrumentChanged(TrackHeaderComponent* track, const juce::String& instrumentId) override;
    void trackLoadSF2Requested(TrackHeaderComponent* track) override;
    void trackLoadSFZRequested(TrackHeaderComponent* track) override;

private:
    juce::OwnedArray<TrackHeaderComponent> trackHeaders;
    Project::ProjectState* projectState = nullptr;
    
    // Available instruments for track selection (cached for new tracks)
    std::map<juce::String, std::vector<const mmg::InstrumentDefinition*>> availableInstruments;
    
    int selectedTrackIndex = 0;
    int trackHeight = 120;          // Uniform track height for all tracks
    int sectionHeaderHeight = 18;   // MPC-style section header height
    
    // MPC-style section headers
    std::unique_ptr<TrackSectionHeader> midiSectionHeader;
    std::unique_ptr<TrackSectionHeader> audioSectionHeader;
    
    // Track colors palette (MPC-style cyan/red scheme)
    juce::Array<juce::Colour> trackColours = {
        juce::Colour(0xFF00D4AA),  // Cyan/teal (MPC MIDI)
        juce::Colour(0xFF2196F3),  // Blue
        juce::Colour(0xFF4CAF50),  // Green
        juce::Colour(0xFFFF6B00),  // Orange
        juce::Colour(0xFF9C27B0),  // Purple
        juce::Colour(0xFFE91E63),  // Pink
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
