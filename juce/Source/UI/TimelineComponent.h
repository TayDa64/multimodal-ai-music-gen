/*
  ==============================================================================

    TimelineComponent.h
    
    Visual timeline showing song sections, beat markers, and playhead.
    Task 4.5: Create timeline component for visual song structure display.

  ==============================================================================
*/

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include "../Application/AppState.h"
#include "../Audio/AudioEngine.h"

//==============================================================================
/**
    Represents a song section (intro, verse, chorus, etc.)
*/
struct TimelineSection
{
    juce::String name;
    double startTime = 0.0;     // Start time in seconds
    double endTime = 0.0;       // End time in seconds
    juce::Colour colour;
    
    double getDuration() const { return endTime - startTime; }
};

//==============================================================================
/**
    Visual timeline component showing:
    - Song sections (colored blocks)
    - Beat/bar markers
    - Playhead position
    - Click-to-seek functionality
*/
class TimelineComponent : public juce::Component,
                          private mmg::AudioEngine::Listener,
                          private juce::Timer
{
public:
    //==============================================================================
    TimelineComponent(AppState& state, mmg::AudioEngine& engine);
    ~TimelineComponent() override;

    //==============================================================================
    /** Set the song sections to display */
    void setSections(const juce::Array<TimelineSection>& sections);
    
    /** Clear all sections */
    void clearSections();
    
    /** Set total duration (in seconds) - used when no sections are set */
    void setTotalDuration(double durationSeconds);
    
    /** Set BPM for beat marker calculation */
    void setBPM(int bpm);
    
    /** Get current BPM */
    int getBPM() const { return currentBPM; }
    
    //==============================================================================
    // Loop Region
    //==============================================================================
    
    /** Set the loop region (start and end in seconds) */
    void setLoopRegion(double startSeconds, double endSeconds);
    
    /** Clear the loop region */
    void clearLoopRegion();
    
    /** Check if a loop region is set */
    bool hasLoopRegion() const { return loopRegionStart >= 0 && loopRegionEnd > loopRegionStart; }
    
    /** Get loop region start (returns -1 if no region set) */
    double getLoopRegionStart() const { return loopRegionStart; }
    
    /** Get loop region end (returns -1 if no region set) */
    double getLoopRegionEnd() const { return loopRegionEnd; }
    
    //==============================================================================
    // Component overrides
    void paint(juce::Graphics& g) override;
    void resized() override;
    void mouseDown(const juce::MouseEvent& event) override;
    void mouseDrag(const juce::MouseEvent& event) override;
    void mouseUp(const juce::MouseEvent& event) override;
    
    //==============================================================================
    /** Listener for timeline seek events */
    class Listener
    {
    public:
        virtual ~Listener() = default;
        virtual void timelineSeekRequested(double positionSeconds) = 0;
        virtual void loopRegionChanged(double startSeconds, double endSeconds) {}
    };
    
    void addListener(Listener* listener);
    void removeListener(Listener* listener);

private:
    //==============================================================================
    // AudioEngine::Listener
    void transportStateChanged(mmg::AudioEngine::TransportState newState) override;
    void playbackPositionChanged(double positionSeconds) override;
    void audioDeviceChanged() override {}
    
    // Timer for position updates
    void timerCallback() override;
    
    //==============================================================================
    // Drawing helpers
    void drawBackground(juce::Graphics& g);
    void drawSections(juce::Graphics& g);
    void drawBeatMarkers(juce::Graphics& g);
    void drawBarMarkers(juce::Graphics& g);
    void drawPlayhead(juce::Graphics& g);
    void drawTimeLabels(juce::Graphics& g);
    void drawLoopRegion(juce::Graphics& g);
    
    // Coordinate conversion
    double positionToX(double timeSeconds) const;
    double xToPosition(float x) const;
    
    // Seek handling
    void seekToPosition(float x);
    
    //==============================================================================
    AppState& appState;
    mmg::AudioEngine& audioEngine;
    juce::ListenerList<Listener> listeners;
    
    // Timeline data
    juce::Array<TimelineSection> sections;
    double totalDuration = 60.0;  // Default 60 seconds
    double currentPosition = 0.0;
    int currentBPM = 120;
    
    // Loop region (-1 means not set)
    double loopRegionStart = -1.0;
    double loopRegionEnd = -1.0;
    bool isDraggingLoopRegion = false;
    enum class LoopDragMode { None, Start, End, Create };
    LoopDragMode loopDragMode = LoopDragMode::None;
    
    // Visual settings
    static constexpr int headerHeight = 20;     // Height for time labels
    static constexpr int sectionHeight = 30;    // Height for section blocks
    static constexpr int markerHeight = 15;     // Height for beat markers
    
    // Colors for different section types
    juce::Colour getSectionColour(const juce::String& sectionName) const;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(TimelineComponent)
};
