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

    void setPlaying(bool shouldBePlaying);
    bool isPlaying() const { return playing; }

    void setMuted(bool shouldBeMuted);
    bool isMuted() const { return muted; }

    void setSolo(bool shouldBeSolo);
    bool isSolo() const { return solo; }

    void setKept(bool shouldBeKept);
    bool isKept() const { return kept; }

    void setFavorite(bool shouldBeFavorite);
    bool isFavorite() const { return favorite; }
    
    const TakeLane& getTakeLane() const { return takeLane; }
    
    std::function<void(const juce::String& takeId, const juce::String& midiPath)> onSelected;
    std::function<void(const juce::String& takeId, const juce::String& midiPath)> onPlayClicked;
    std::function<void()> onStopClicked;
    std::function<void(const juce::String& takeId, bool muted)> onMuteToggled;
    std::function<void(const juce::String& takeId, bool solo)> onSoloToggled;
    std::function<void(const juce::String& takeId, bool kept)> onKeepToggled;
    std::function<void(const juce::String& takeId, bool favorite)> onFavoriteToggled;
    
private:
    TakeLane takeLane;
    bool selected = false;
    bool hovered = false;
    bool playing = false;
    bool muted = false;
    bool solo = false;
    bool kept = false;
    bool favorite = false;
    
    juce::TextButton playButton { "Play" };
    juce::TextButton stopButton { "Stop" };
    juce::TextButton muteButton { "M" };
    juce::TextButton soloButton { "S" };
    juce::TextButton keepButton { "K" };
    juce::TextButton favoriteButton { "F" };
    
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

    int getNumTakes() const { return takeItems.size(); }
    int getPreferredHeight() const;
    
    const juce::String& getTrackName() const { return trackName; }
    
    std::function<void(const juce::String& track, const juce::String& takeId, const juce::String& midiPath)> onTakeSelected;
    std::function<void(const juce::String& track, const juce::String& takeId, const juce::String& midiPath)> onPlayRequested;
    std::function<void(const juce::String& track)> onStopRequested;
    
private:
    juce::String trackName;
    juce::String selectedTakeId;
    juce::String playingTakeId;
    
    juce::Label headerLabel;
    juce::OwnedArray<TakeLaneItem> takeItems;
    
    static constexpr int headerHeight = 28;
    static constexpr int takeItemHeight = 36;
    static constexpr int takeItemSpacing = 2;
    
    void handleTakeSelected(const juce::String& takeId, const juce::String& midiPath);
    void handlePlayRequested(const juce::String& takeId, const juce::String& midiPath);
    void handleStopRequested();
    
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
        virtual void takeSelected(const juce::String& track, const juce::String& takeId, const juce::String& midiPath) = 0;
        
        /** Called when user requests playback of a specific take. */
        virtual void takePlayRequested(const juce::String& track, const juce::String& takeId, const juce::String& midiPath) = 0;

        /** Called when user requests stop of take playback. */
        virtual void takeStopRequested(const juce::String& track) { juce::ignoreUnused(track); }
        
        /** Called when user wants to render the selected takes. */
        virtual void renderTakesRequested() = 0;

        /** Called when user commits the current comp (clears revert buffer). */
        virtual void commitCompRequested() {}

        /** Called when user reverts the comp back to pre-selection notes. */
        virtual void revertCompRequested() {}
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
    juce::TextButton commitButton { "Commit Comp" };
    juce::TextButton revertButton { "Revert Comp" };
    juce::Label emptyLabel;
    
    juce::OwnedArray<TrackTakeLaneContainer> trackContainers;
    juce::Viewport viewport;
    juce::Component containerHolder;
    
    juce::ListenerList<Listener> listeners;
    
    void handleTrackTakeSelected(const juce::String& track, const juce::String& takeId, const juce::String& midiPath);
    void handlePlayRequested(const juce::String& track, const juce::String& takeId, const juce::String& midiPath);
    void handleStopRequested(const juce::String& track);
    void handleRenderClicked();
    void handleCommitClicked();
    void handleRevertClicked();
    void updateLayout();
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(TakeLanePanel)
};
