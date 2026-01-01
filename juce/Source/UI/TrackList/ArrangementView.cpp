/*
  ==============================================================================

    ArrangementView.cpp
    
    Implementation of professional DAW-style arrangement view.

  ==============================================================================
*/

#include "ArrangementView.h"
#include "../Theme/ThemeManager.h"

namespace UI
{

//==============================================================================
// TrackLaneContent
//==============================================================================

TrackLaneContent::TrackLaneContent(int index, mmg::AudioEngine& engine)
    : trackIndex(index), audioEngine(engine)
{
    // Create piano roll by default (for MIDI tracks)
    pianoRoll = std::make_unique<PianoRollComponent>(engine);
    pianoRoll->soloTrack(trackIndex);  // Show only this track's notes
    addAndMakeVisible(*pianoRoll);
}

TrackLaneContent::~TrackLaneContent() = default;

void TrackLaneContent::setTrackIndex(int index)
{
    trackIndex = index;
    if (pianoRoll)
        pianoRoll->soloTrack(index);
}

void TrackLaneContent::setTrackType(TrackType type)
{
    trackType = type;
    
    // For now, we only support MIDI with piano roll
    // Future: Add waveform component for audio tracks
    if (type == TrackType::Audio)
    {
        // pianoRoll->setVisible(false);
        // waveform->setVisible(true);
    }
    else
    {
        if (pianoRoll)
            pianoRoll->setVisible(true);
    }
}

void TrackLaneContent::setProjectState(Project::ProjectState* state)
{
    projectState = state;
    if (pianoRoll && state)
        pianoRoll->setProjectState(state);
}

void TrackLaneContent::setHorizontalZoom(float zoom)
{
    hZoom = zoom;
    if (pianoRoll)
        pianoRoll->setHorizontalZoom(zoom);
}

void TrackLaneContent::setScrollX(double scroll)
{
    scrollPosX = scroll;
    // Piano roll handles its own scroll internally
    repaint();
}

void TrackLaneContent::paint(juce::Graphics& g)
{
    // Background
    auto bgColour = ThemeManager::getCurrentScheme().background;
    if (trackIndex % 2 == 1)
        bgColour = bgColour.brighter(0.03f);
    
    g.fillAll(bgColour);
    
    // Grid lines (vertical bar markers)
    if (pianoRoll == nullptr || trackType == TrackType::Audio)
    {
        // Draw placeholder grid for audio tracks
        g.setColour(ThemeManager::getCurrentScheme().outline.withAlpha(0.2f));
        
        double secondsPerBeat = 60.0 / 120.0;  // Default 120 BPM
        double secondsPerBar = secondsPerBeat * 4.0;
        float pixelsPerSecond = 100.0f * hZoom;
        
        for (double time = 0.0; time < 60.0; time += secondsPerBar)
        {
            float x = (float)((time - scrollPosX) * pixelsPerSecond);
            if (x >= 0 && x < getWidth())
                g.drawVerticalLine((int)x, 0.0f, (float)getHeight());
        }
    }
}

void TrackLaneContent::resized()
{
    if (pianoRoll)
        pianoRoll->setBounds(getLocalBounds());
}


//==============================================================================
// ArrangementView
//==============================================================================

ArrangementView::ArrangementView(mmg::AudioEngine& engine)
    : audioEngine(engine)
{
    // Track list on left
    trackList.addListener(this);
    addAndMakeVisible(trackList);
    
    // Lanes viewport
    lanesViewport.setViewedComponent(&lanesContent, false);
    lanesViewport.setScrollBarsShown(true, true);
    addAndMakeVisible(lanesViewport);
    
    // Create initial track lanes
    syncTrackLanes();
}

ArrangementView::~ArrangementView()
{
    if (projectState)
        projectState->getState().removeListener(this);
    
    trackList.removeListener(this);
}

//==============================================================================
void ArrangementView::setProjectState(Project::ProjectState* state)
{
    if (projectState)
        projectState->getState().removeListener(this);
    
    projectState = state;
    
    if (projectState)
    {
        projectState->getState().addListener(this);
        trackList.bindToProject(*projectState);
        
        // Update track lanes
        syncTrackLanes();
        
        // Bind each lane to project state
        for (auto* lane : trackLanes)
        {
            lane->setProjectState(projectState);
        }
    }
}

void ArrangementView::setBPM(int bpm)
{
    currentBPM = bpm;
    repaint();
}

void ArrangementView::setHorizontalZoom(float zoom)
{
    hZoom = juce::jlimit(0.1f, 10.0f, zoom);
    
    for (auto* lane : trackLanes)
        lane->setHorizontalZoom(hZoom);
    
    updateLanesLayout();
    repaint();
}

//==============================================================================
void ArrangementView::paint(juce::Graphics& g)
{
    g.fillAll(ThemeManager::getCurrentScheme().background);
    
    // Draw timeline ruler at top
    auto rulerBounds = getLocalBounds().removeFromTop(rulerHeight);
    rulerBounds.removeFromLeft(trackListWidth);
    drawTimelineRuler(g, rulerBounds);
}

void ArrangementView::resized()
{
    auto bounds = getLocalBounds();
    
    // Timeline ruler space
    bounds.removeFromTop(rulerHeight);
    
    // Track list on left
    trackList.setBounds(bounds.removeFromLeft(trackListWidth));
    
    // Lanes viewport takes the rest
    lanesViewport.setBounds(bounds);
    
    updateLanesLayout();
}

void ArrangementView::mouseWheelMove(const juce::MouseEvent& event, const juce::MouseWheelDetails& wheel)
{
    if (event.mods.isCtrlDown() || event.mods.isCommandDown())
    {
        // Zoom with Ctrl+scroll
        float zoomFactor = wheel.deltaY > 0 ? 1.15f : 0.87f;
        setHorizontalZoom(hZoom * zoomFactor);
    }
    else
    {
        // Pass to viewport for normal scrolling
        lanesViewport.mouseWheelMove(event, wheel);
    }
}

//==============================================================================
void ArrangementView::trackSelectionChanged(int trackIndex)
{
    DBG("Arrangement: Track " + juce::String(trackIndex + 1) + " selected");
    
    // Highlight corresponding lane
    for (int i = 0; i < trackLanes.size(); ++i)
    {
        // Could add visual highlighting here
    }
}

void ArrangementView::trackCountChanged(int newCount)
{
    syncTrackLanes();
}

void ArrangementView::trackExpandedChanged(int trackIndex, bool expanded)
{
    updateLanesLayout();
}

//==============================================================================
void ArrangementView::valueTreePropertyChanged(juce::ValueTree& tree, const juce::Identifier& property)
{
    // Handle project state changes
}

void ArrangementView::valueTreeChildAdded(juce::ValueTree& parent, juce::ValueTree& child)
{
    if (child.hasType(Project::IDs::TRACK))
        syncTrackLanes();
}

void ArrangementView::valueTreeChildRemoved(juce::ValueTree& parent, juce::ValueTree& child, int index)
{
    if (child.hasType(Project::IDs::TRACK))
        syncTrackLanes();
}

//==============================================================================
void ArrangementView::syncTrackLanes()
{
    int trackCount = trackList.getTrackCount();
    
    // Remove excess lanes
    while (trackLanes.size() > trackCount)
    {
        trackLanes.removeLast();
    }
    
    // Add missing lanes
    while (trackLanes.size() < trackCount)
    {
        int index = trackLanes.size();
        auto* lane = trackLanes.add(new TrackLaneContent(index, audioEngine));
        
        if (projectState)
            lane->setProjectState(projectState);
        
        lane->setHorizontalZoom(hZoom);
        lanesContent.addAndMakeVisible(lane);
    }
    
    updateLanesLayout();
}

void ArrangementView::updateLanesLayout()
{
    int y = 0;
    int width = juce::jmax(1000, lanesViewport.getWidth());  // Minimum width for scrolling
    
    // Calculate total height based on expanded/collapsed state
    for (int i = 0; i < trackLanes.size(); ++i)
    {
        auto* header = trackList.getTrackHeader(i);
        int height = (header && header->isExpanded()) 
            ? trackList.getExpandedTrackHeight() 
            : trackList.getCollapsedTrackHeight();
        
        trackLanes[i]->setBounds(0, y, width, height);
        y += height;
    }
    
    // Extend width based on zoom and duration
    float totalDuration = 60.0f;  // Default 60 seconds view
    float pixelsPerSecond = 100.0f * hZoom;
    int contentWidth = (int)(totalDuration * pixelsPerSecond);
    
    lanesContent.setSize(juce::jmax(width, contentWidth), juce::jmax(y, lanesViewport.getHeight()));
}

void ArrangementView::drawTimelineRuler(juce::Graphics& g, juce::Rectangle<int> bounds)
{
    // Background
    g.setColour(ThemeManager::getSurface());
    g.fillRect(bounds);
    
    // Border
    g.setColour(ThemeManager::getCurrentScheme().outline);
    g.drawLine((float)bounds.getX(), (float)bounds.getBottom(),
               (float)bounds.getRight(), (float)bounds.getBottom());
    
    // Time markers
    double secondsPerBeat = 60.0 / currentBPM;
    double secondsPerBar = secondsPerBeat * 4.0;
    float pixelsPerSecond = 100.0f * hZoom;
    
    // Get current scroll position
    double scrollOffset = lanesViewport.getViewPositionX() / pixelsPerSecond;
    
    g.setFont(10.0f);
    
    // Draw bar numbers and beat markers
    for (double time = 0.0; time < 120.0; time += secondsPerBeat)
    {
        float x = bounds.getX() + (float)((time - scrollOffset) * pixelsPerSecond);
        
        if (x < bounds.getX() - 50 || x > bounds.getRight() + 50)
            continue;
        
        bool isBar = std::fmod(time, secondsPerBar) < 0.001;
        
        if (isBar)
        {
            // Bar marker - thicker line and number
            g.setColour(ThemeManager::getCurrentScheme().text);
            g.drawVerticalLine((int)x, (float)bounds.getY() + 15, (float)bounds.getBottom());
            
            int barNumber = (int)(time / secondsPerBar) + 1;
            g.drawText(juce::String(barNumber), 
                      (int)x + 2, bounds.getY(), 30, 15,
                      juce::Justification::centredLeft);
        }
        else
        {
            // Beat marker - thinner line
            g.setColour(ThemeManager::getCurrentScheme().textSecondary.withAlpha(0.5f));
            g.drawVerticalLine((int)x, (float)bounds.getY() + 20, (float)bounds.getBottom());
        }
    }
}

} // namespace UI
