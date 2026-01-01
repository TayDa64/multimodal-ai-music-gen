/*
  ==============================================================================

    TakeLaneComponent.h
    
    UI component for displaying and managing take lanes.
    Allows users to audition different takes for a track and create comps.

  ==============================================================================
*/

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include "../Communication/Messages.h"
#include "Theme/LayoutConstants.h"

//==============================================================================
/**
    Represents a single take lane in the UI.
    Shows take metadata and selection state.
*/
class TakeLaneItem : public juce::Component
{
public:
    TakeLaneItem(const TakeLane& take);
    ~TakeLaneItem() override = default;
    
    void paint(juce::Graphics& g) override;
    void resized() override;
    void mouseDown(const juce::MouseEvent& e) override;
    void mouseEnter(const juce::MouseEvent& e) override;
    void mouseExit(const juce::MouseEvent& e) override;
    
    void setSelected(bool shouldBeSelected);
    bool isSelected() const { return selected; }
    
    const TakeLane& getTakeLane() const { return takeLane; }
    
    std::function<void(const juce::String& takeId)> onSelected;
    std::function<void(const juce::String& takeId)> onPlayClicked;
    
private:
    TakeLane takeLane;
    bool selected = false;
    bool hovered = false;
    
    juce::TextButton playButton { "▶" };
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(TakeLaneItem)
};

//==============================================================================
/**
    Container for take lanes of a single track.
    Shows header with track name and list of available takes.
*/
class TrackTakeLaneContainer : public juce::Component
{
public:
    TrackTakeLaneContainer(const juce::String& trackName);
    ~TrackTakeLaneContainer() override = default;
    
    void paint(juce::Graphics& g) override;
    void resized() override;
    
    void setTakes(const std::vector<TakeLane>& takes);
    void clearTakes();
    
    void selectTake(const juce::String& takeId);
    juce::String getSelectedTakeId() const { return selectedTakeId; }
    
    const juce::String& getTrackName() const { return trackName; }
    
    std::function<void(const juce::String& track, const juce::String& takeId)> onTakeSelected;
    std::function<void(const juce::String& track, const juce::String& takeId)> onPlayRequested;
    
private:
    juce::String trackName;
    juce::String selectedTakeId;
    
    juce::Label headerLabel;
    juce::OwnedArray<TakeLaneItem> takeItems;
    
    static constexpr int headerHeight = 28;
    static constexpr int takeItemHeight = 36;
    static constexpr int takeItemSpacing = 2;
    
    void handleTakeSelected(const juce::String& takeId);
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(TrackTakeLaneContainer)
};

//==============================================================================
/**
    Main take lane panel for displaying all tracks' takes.
    Integrates with OSCBridge for take management operations.
*/
class TakeLanePanel : public juce::Component
{
public:
    //==============================================================================
    class Listener
    {
    public:
        virtual ~Listener() = default;
        
        /** Called when user selects a take for a track. */
        virtual void takeSelected(const juce::String& track, const juce::String& takeId) = 0;
        
        /** Called when user requests playback of a specific take. */
        virtual void takePlayRequested(const juce::String& track, const juce::String& takeId) = 0;
        
        /** Called when user wants to render the selected takes. */
        virtual void renderTakesRequested() = 0;
    };
    
    //==============================================================================
    TakeLanePanel();
    ~TakeLanePanel() override;
    
    void paint(juce::Graphics& g) override;
    void resized() override;
    
    //==============================================================================
    /**
        Populate the panel with available takes from generation result.
        
        @param takesJson JSON string with track->takes mapping:
               {"drums": [{take_id, seed, variation_type, midi_path}, ...], "bass": [...]}
    */
    void setAvailableTakes(const juce::String& takesJson);
    
    /** Clear all takes (e.g., when starting a new generation). */
    void clearAllTakes();
    
    /** Update selection for a track (e.g., from server confirmation). */
    void confirmTakeSelection(const juce::String& track, const juce::String& takeId);
    
    /** Check if there are any takes available. */
    bool hasTakes() const { return !trackContainers.isEmpty(); }
    
    /** Get number of tracks with takes. */
    int getNumTracks() const { return trackContainers.size(); }
    
    //==============================================================================
    void addListener(Listener* listener);
    void removeListener(Listener* listener);
    
private:
    juce::Label titleLabel;
    juce::TextButton renderButton { "Render Selected" };
    juce::Label emptyLabel;
    
    juce::OwnedArray<TrackTakeLaneContainer> trackContainers;
    juce::Viewport viewport;
    juce::Component containerHolder;
    
    juce::ListenerList<Listener> listeners;
    
    void handleTrackTakeSelected(const juce::String& track, const juce::String& takeId);
    void handlePlayRequested(const juce::String& track, const juce::String& takeId);
    void handleRenderClicked();
    void updateLayout();
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(TakeLanePanel)
};
