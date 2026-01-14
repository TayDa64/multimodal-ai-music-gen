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
    pianoRoll->setEmbeddedMode(true);  // Hide track selector - redundant in arrangement view
    pianoRoll->setMinimumDuration(600.0);  // 10 minutes minimum playable area
    pianoRoll->addListener(this);  // Listen for zoom requests
    addAndMakeVisible(*pianoRoll);
}

TrackLaneContent::~TrackLaneContent()
{
    if (pianoRoll)
        pianoRoll->removeListener(this);
}

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
    {
        pianoRoll->setProjectState(state);
        
        // IMPORTANT: Reset and trigger zoomToFit after loading new project
        // This ensures notes are visible regardless of track pitch range
        pianoRoll->resetInitialZoom();
        pianoRoll->zoomToFit();
    }
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
    if (pianoRoll)
        pianoRoll->setScrollX(scroll);
    repaint();
}

void TrackLaneContent::pianoRollHorizontalZoomRequested(float newZoom)
{
    // Forward zoom request to parent ArrangementView via callback
    if (onZoomRequested)
        onZoomRequested(newZoom);
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
    
    // Set up scroll bar listeners for synchronization (vertical + horizontal)
    lanesViewport.getVerticalScrollBar().addListener(this);
    lanesViewport.getHorizontalScrollBar().addListener(this);
    trackList.getViewport().getVerticalScrollBar().addListener(this);
    
    // Create initial track lanes
    syncTrackLanes();
}

ArrangementView::~ArrangementView()
{
    // Remove scroll bar listeners
    lanesViewport.getVerticalScrollBar().removeListener(this);
    lanesViewport.getHorizontalScrollBar().removeListener(this);
    trackList.getViewport().getVerticalScrollBar().removeListener(this);
    
    if (projectState)
        projectState->removeStateListener(this);
    
    trackList.removeListener(this);
}

//==============================================================================
void ArrangementView::setProjectState(Project::ProjectState* state)
{
    if (projectState)
        projectState->removeStateListener(this);
    
    projectState = state;
    
    if (projectState)
    {
        projectState->addStateListener(this);
        trackList.bindToProject(*projectState);
        
        // Update track lanes
        syncTrackLanes();
        
        // Bind each lane to project state
        for (auto* lane : trackLanes)
        {
            lane->setProjectState(projectState);
        }
        
        // Calculate optimal zoom to show the entire song
        zoomToShowFullSong();
    }
}

void ArrangementView::zoomToShowFullSong()
{
    if (!projectState)
        return;
    
    // Find total duration from all notes
    double maxTime = 0.0;
    auto notesNode = projectState->getState().getChildWithName(Project::IDs::NOTES);
    if (notesNode.isValid())
    {
        double bpm = projectState->getState().getProperty(Project::IDs::bpm, 120.0);
        double secondsPerBeat = 60.0 / bpm;
        
        for (int i = 0; i < notesNode.getNumChildren(); ++i)
        {
            auto noteNode = notesNode.getChild(i);
            double startBeats = noteNode.getProperty(Project::IDs::start);
            double lengthBeats = noteNode.getProperty(Project::IDs::length);
            double endTime = (startBeats + lengthBeats) * secondsPerBeat;
            maxTime = juce::jmax(maxTime, endTime);
        }
    }
    
    // Add some padding (10%)
    maxTime *= 1.1;
    
    // Minimum 30 seconds visible
    maxTime = juce::jmax(maxTime, 30.0);
    
    // Calculate zoom to fit in viewport
    int viewportWidth = lanesViewport.getWidth() - 20;  // Account for scrollbar
    if (viewportWidth > 0 && maxTime > 0)
    {
        float pixelsPerSecond = (float)viewportWidth / (float)maxTime;
        float newZoom = pixelsPerSecond / 100.0f;
        setHorizontalZoom(juce::jlimit(0.1f, 2.0f, newZoom));  // Cap at 2x for readability
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
    
    // Debug: Show total notes in ProjectState
    if (projectState)
    {
        auto notesNode = projectState->getState().getChildWithName(Project::IDs::NOTES);
        int totalNotes = notesNode.isValid() ? notesNode.getNumChildren() : -1;
        juce::String nodeStatus = notesNode.isValid() ? "valid" : "INVALID";
        
        // Show notes count and last import stats
        g.setColour(juce::Colours::yellow);
        g.setFont(10.0f);
        g.drawText("NOTES: " + juce::String(totalNotes) + " | " + projectState->getLastImportStats(), 
                   rulerBounds.withX(trackListWidth + 10).withWidth(500), 
                   juce::Justification::centredLeft);
    }
    
    // Draw focus mode indicator
    if (hasFocusedTrack())
    {
        auto* header = trackList.getTrackHeader(focusedTrackIndex);
        juce::String focusLabel = "FOCUSED: " + (header ? header->getTrackName() : "Track " + juce::String(focusedTrackIndex + 1));
        focusLabel += "  (Right-click to exit)";
        
        g.setColour(ThemeManager::getCurrentScheme().accent);
        g.setFont(11.0f);
        g.drawText(focusLabel, rulerBounds.reduced(10, 0), juce::Justification::centredRight);
    }
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

void ArrangementView::mouseDown(const juce::MouseEvent& event)
{
    if (event.mods.isPopupMenu())
    {
        showContextMenu(event);
    }
}

void ArrangementView::showContextMenu(const juce::MouseEvent& event)
{
    juce::PopupMenu menu;
    
    // Get track at click position (if any)
    int clickedTrackIndex = -1;
    auto localPos = event.position;
    
    // Check if click is in the lanes area
    if (localPos.x > trackListWidth)
    {
        // Calculate which track was clicked based on y position
        int y = (int)localPos.y - rulerHeight + lanesViewport.getViewPositionY();
        int currentY = 0;
        
        for (int i = 0; i < trackLanes.size(); ++i)
        {
            int height = trackLanes[i]->getHeight();
            if (y >= currentY && y < currentY + height)
            {
                clickedTrackIndex = i;
                break;
            }
            currentY += height;
        }
    }
    
    // Build context menu
    if (clickedTrackIndex >= 0)
    {
        auto* header = trackList.getTrackHeader(clickedTrackIndex);
        juce::String trackName = header ? header->getTrackName() : "Track " + juce::String(clickedTrackIndex + 1);
        
        if (focusedTrackIndex == clickedTrackIndex)
        {
            menu.addItem(1, "Exit Focus View", true, false);
        }
        else
        {
            menu.addItem(2, "Focus: " + trackName, true, false);
        }
        
        menu.addSeparator();
        menu.addItem(3, "Expand Track", true, header && header->isExpanded());
        menu.addItem(4, "Solo Track", true, false);
        menu.addItem(5, "Mute Track", true, false);
        menu.addSeparator();
        
        // Regeneration options
        menu.addItem(20, "Regenerate Track", true, false);
        menu.addItem(21, "Regenerate All Tracks", true, false);
        menu.addSeparator();
        
        menu.addItem(6, "Delete Track", trackList.getTrackCount() > 1, false);  // Only enable if more than 1 track
    }
    else if (hasFocusedTrack())
    {
        menu.addItem(1, "Exit Focus View", true, false);
    }
    
    menu.addSeparator();
    menu.addItem(10, "Zoom to Fit", true, false);
    menu.addItem(11, "Reset Zoom", true, false);
    
    menu.showMenuAsync(juce::PopupMenu::Options().withTargetScreenArea(
        juce::Rectangle<int>(event.getScreenX(), event.getScreenY(), 1, 1)),
        [this, clickedTrackIndex](int result) {
            switch (result)
            {
                case 1: // Exit Focus View
                    clearFocusedTrack();
                    break;
                case 2: // Focus Track
                    setFocusedTrack(clickedTrackIndex);
                    break;
                case 3: // Expand Track
                    if (auto* header = trackList.getTrackHeader(clickedTrackIndex))
                        header->setExpanded(!header->isExpanded());
                    updateLanesLayout();
                    break;
                case 6: // Delete Track
                    if (clickedTrackIndex >= 0)
                    {
                        // Exit focus view if we're deleting the focused track
                        if (focusedTrackIndex == clickedTrackIndex)
                            clearFocusedTrack();
                        else if (focusedTrackIndex > clickedTrackIndex)
                            focusedTrackIndex--;  // Adjust focused index
                        
                        trackList.removeTrack(clickedTrackIndex);
                    }
                    break;
                case 10: // Zoom to Fit
                    // TODO: Implement zoom to fit
                    break;
                case 11: // Reset Zoom
                    setHorizontalZoom(1.0f);
                    break;
                case 20: // Regenerate Track
                    if (clickedTrackIndex >= 0)
                    {
                        // Get track name
                        juce::StringArray tracks;
                        if (auto* header = trackList.getTrackHeader(clickedTrackIndex))
                            tracks.add(header->getTrackName());
                        else
                            tracks.add("Track " + juce::String(clickedTrackIndex + 1));
                        
                        // Regenerate all bars (0-8 default, should come from project state)
                        listeners.call([&](Listener& l) {
                            l.arrangementRegenerateRequested(0, 8, tracks);
                        });
                    }
                    break;
                case 21: // Regenerate All Tracks
                    {
                        // Empty tracks array means all tracks
                        juce::StringArray emptyTracks;
                        listeners.call([&](Listener& l) {
                            l.arrangementRegenerateRequested(0, 8, emptyTracks);
                        });
                    }
                    break;
            }
        });
}

void ArrangementView::setFocusedTrack(int trackIndex)
{
    if (focusedTrackIndex == trackIndex)
        return;
    
    focusedTrackIndex = trackIndex;
    
    if (focusedTrackIndex >= 0)
    {
        DBG("Arrangement: Focusing on Track " + juce::String(focusedTrackIndex + 1));
        trackList.selectTrack(focusedTrackIndex);
    }
    else
    {
        DBG("Arrangement: Exiting focus view");
    }
    
    updateLanesLayout();
    repaint();
}

//==============================================================================
void ArrangementView::trackSelectionChanged(int trackIndex)
{
    DBG("Arrangement: Track " + juce::String(trackIndex + 1) + " selected");

    // Keep downstream panels (e.g., Piano Roll) in sync with the user's active track.
    listeners.call(&ArrangementView::Listener::arrangementTrackSelected, trackIndex);
    
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

void ArrangementView::trackExpandedChanged(int trackIndex, bool /*expanded*/)
{
    // When expand button (▶) is clicked, open Piano Roll view for this track
    // All tracks remain at uniform height - no in-place expansion
    listeners.call(&ArrangementView::Listener::arrangementTrackPianoRollRequested, trackIndex);
}

void ArrangementView::trackInstrumentSelected(int trackIndex, const juce::String& instrumentId)
{
    // Forward instrument selection to listeners (MainComponent will handle loading)
    listeners.call(&ArrangementView::Listener::arrangementTrackInstrumentSelected, trackIndex, instrumentId);
}

void ArrangementView::trackLoadSF2Requested(int trackIndex)
{
    // Forward SF2 loading request to listeners
    listeners.call(&ArrangementView::Listener::arrangementTrackLoadSF2Requested, trackIndex);
}

void ArrangementView::trackLoadSFZRequested(int trackIndex)
{
    // Forward SFZ loading request to listeners
    listeners.call(&ArrangementView::Listener::arrangementTrackLoadSFZRequested, trackIndex);
}

//==============================================================================
void ArrangementView::valueTreePropertyChanged(juce::ValueTree& tree, const juce::Identifier& property)
{
    // Handle project state changes
}

void ArrangementView::valueTreeChildAdded(juce::ValueTree& parent, juce::ValueTree& child)
{
    if (child.hasType(Project::IDs::TRACK) && projectState)
    {
        // Rebind track list to pick up new tracks from project state
        trackList.bindToProject(*projectState);
        syncTrackLanes();
    }
}

void ArrangementView::valueTreeChildRemoved(juce::ValueTree& parent, juce::ValueTree& child, int index)
{
    if (child.hasType(Project::IDs::TRACK))
        syncTrackLanes();
}

//==============================================================================
void ArrangementView::scrollBarMoved(juce::ScrollBar* scrollBar, double newRangeStart)
{
    // Prevent feedback loops
    if (isSyncingScroll)
        return;
    
    isSyncingScroll = true;
    
    // Determine which viewport was scrolled and sync the other
    if (scrollBar == &lanesViewport.getVerticalScrollBar())
    {
        // Lanes viewport was scrolled vertically - sync track list
        trackList.getViewport().setViewPosition(
            trackList.getViewport().getViewPositionX(),
            (int)newRangeStart
        );
    }
    else if (scrollBar == &trackList.getViewport().getVerticalScrollBar())
    {
        // Track list was scrolled - sync lanes viewport
        lanesViewport.setViewPosition(
            lanesViewport.getViewPositionX(),
            (int)newRangeStart
        );
    }
    else if (scrollBar == &lanesViewport.getHorizontalScrollBar())
    {
        // Horizontal scroll changed - update scrollX and sync track lanes
        syncScrollFromViewport();
    }
    
    isSyncingScroll = false;
    
    // Repaint to update timeline ruler
    repaint();
}

void ArrangementView::syncScrollFromViewport()
{
    float pixelsPerSecond = 100.0f * hZoom;
    scrollX = lanesViewport.getViewPositionX() / pixelsPerSecond;
    
    // NOTE: We do NOT sync scrollX to embedded PianoRolls because the viewport
    // already handles visual scrolling. Setting scrollX on embedded PianoRolls
    // would cause double-scrolling and misalignment with the timeline ruler.
    // The PianoRolls draw from time=0 at x=0, and the viewport clips/translates.
    
    // Repaint timeline ruler to stay in sync
    repaint();
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
        int laneIndex = trackLanes.size();
        // IMPORTANT: In our ProjectState model, note "channel" is the 0-based track index.
        // Track headers are also 0-based (Track 1 == index 0). So lanes must use laneIndex.
        auto* lane = trackLanes.add(new TrackLaneContent(laneIndex, audioEngine));
        
        // Wire up zoom callback for synchronized zooming across all tracks
        lane->onZoomRequested = [this](float newZoom) {
            setHorizontalZoom(newZoom);  // This will sync all lanes + timeline
        };
        
        if (projectState)
            lane->setProjectState(projectState);
        
        lane->setHorizontalZoom(hZoom);
        lanesContent.addAndMakeVisible(lane);
    }
    
    updateLanesLayout();
}

void ArrangementView::updateLanesLayout()
{
    // Account for MIDI section header in track list (so lanes align with headers)
    int sectionHeaderOffset = trackList.getSectionHeaderHeight();
    int y = sectionHeaderOffset;  // Start lanes below the section header space
    
    int width = juce::jmax(1000, lanesViewport.getWidth());  // Minimum width for scrolling
    int viewportHeight = lanesViewport.getHeight();
    
    // In focused track mode, show the focused track at half viewport height
    if (focusedTrackIndex >= 0 && focusedTrackIndex < trackLanes.size())
    {
        int focusedHeight = viewportHeight / 2;  // Half the viewport height
        
        for (int i = 0; i < trackLanes.size(); ++i)
        {
            if (i == focusedTrackIndex)
            {
                // Focused track takes half viewport height
                trackLanes[i]->setVisible(true);
                trackLanes[i]->setBounds(0, 0, width, focusedHeight);
            }
            else
            {
                // Hide other tracks
                trackLanes[i]->setVisible(false);
            }
        }
        
        // Extend width based on zoom and duration - 10 minutes for professional workflow
        float totalDuration = 600.0f;  // 10 minutes of scrollable content
        float pixelsPerSecond = 100.0f * hZoom;
        int contentWidth = (int)(totalDuration * pixelsPerSecond);
        
        lanesContent.setSize(juce::jmax(width, contentWidth), focusedHeight);
    }
    else
    {
        // Normal mode: show all tracks stacked vertically at uniform height
        for (int i = 0; i < trackLanes.size(); ++i)
        {
            trackLanes[i]->setVisible(true);
            
            // All tracks use uniform height (120px)
            int height = trackList.getTrackHeight();
            
            trackLanes[i]->setBounds(0, y, width, height);
            y += height;
        }
        
        // Extend width based on zoom and duration - 10 minutes for professional workflow
        float totalDuration = 600.0f;  // 10 minutes of scrollable content
        float pixelsPerSecond = 100.0f * hZoom;
        int contentWidth = (int)(totalDuration * pixelsPerSecond);
        
        lanesContent.setSize(juce::jmax(width, contentWidth), juce::jmax(y, viewportHeight));
    }
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
    
    // Bar numbers only - grid lines are drawn in paintOverChildren for perfect alignment
    double secondsPerBeat = 60.0 / currentBPM;
    double secondsPerBar = secondsPerBeat * 4.0;
    float pixelsPerSecond = 100.0f * hZoom;
    int viewportScrollX = lanesViewport.getViewPositionX();
    
    g.setFont(11.0f);
    
    // Draw bar numbers
    for (double time = 0.0; time < 600.0; time += secondsPerBar)
    {
        float x = bounds.getX() + (float)(time * pixelsPerSecond) - viewportScrollX;
        
        if (x < bounds.getX() - 50 || x > bounds.getRight() + 50)
            continue;
        
        int bar, beat, tick;
        timeToBarBeat(time, bar, beat, tick);
        
        // Bar number
        g.setColour(ThemeManager::getCurrentScheme().text);
        g.drawText(juce::String(bar), 
                  (int)x + 4, bounds.getY(), 40, bounds.getHeight(),
                  juce::Justification::centredLeft);
    }
}

void ArrangementView::paintOverChildren(juce::Graphics& g)
{
    // Draw unified grid lines that extend from timeline through ALL track lanes
    // This ensures perfect alignment - ONE source of truth for grid positions
    
    double secondsPerBeat = 60.0 / currentBPM;
    double secondsPerBar = secondsPerBeat * 4.0;
    float pixelsPerSecond = 100.0f * hZoom;
    int viewportScrollX = lanesViewport.getViewPositionX();

    auto chooseGridDivisionsPerBeat = [](float pixelsPerBeat) {
        // 1 = quarter notes, 2 = eighth notes, 4 = sixteenth notes
        if (pixelsPerBeat >= 140.0f) return 4;
        if (pixelsPerBeat >= 80.0f)  return 2;
        return 1;
    };
    const float pixelsPerBeat = (float)(secondsPerBeat * pixelsPerSecond);
    const int gridDiv = chooseGridDivisionsPerBeat(pixelsPerBeat);
    const double stepSeconds = secondsPerBeat / (double)gridDiv;
    
    // Grid area: from timeline ruler through track lanes
    auto gridArea = getLocalBounds();
    gridArea.removeFromLeft(trackListWidth);  // Start after track list
    int rulerTop = 0;
    int lanesBottom = gridArea.getBottom();
    
    // Draw grid lines (adaptive subdivision up to 1/16)
    for (double time = 0.0; time < 600.0; time += stepSeconds)
    {
        float x = gridArea.getX() + (float)(time * pixelsPerSecond) - viewportScrollX;
        
        if (x < gridArea.getX() - 2 || x > gridArea.getRight() + 2)
            continue;
        
        const double beats = time / secondsPerBeat;
        const int subIndex = (int)std::llround(beats * (double)gridDiv);
        const bool isBar = (subIndex % (gridDiv * 4)) == 0;
        const bool isBeat = (subIndex % gridDiv) == 0;
        
        if (isBar)
        {
            // Bar line - thicker, more visible, extends full height
            g.setColour(ThemeManager::getCurrentScheme().outline.withAlpha(0.8f));
            g.drawLine(x, (float)rulerTop + 14, x, (float)lanesBottom, 2.0f);  // 2px thick
        }
        else if (isBeat)
        {
            // Beat line - thinner, extends only through track lanes
            g.setColour(ThemeManager::getCurrentScheme().outline.withAlpha(0.25f));
            g.drawVerticalLine((int)x, (float)rulerHeight, (float)lanesBottom);
            
            // Small tick mark in ruler area
            g.setColour(ThemeManager::getCurrentScheme().textSecondary.withAlpha(0.4f));
            g.drawVerticalLine((int)x, (float)rulerHeight - 6, (float)rulerHeight);
        }
        else
        {
            // Subdivision line - very light, only through lanes
            g.setColour(ThemeManager::getCurrentScheme().outline.withAlpha(0.12f));
            g.drawVerticalLine((int)x, (float)rulerHeight, (float)lanesBottom);
        }
    }
}

//==============================================================================
// Time formatting helpers
void ArrangementView::timeToBarBeat(double timeSeconds, int& bar, int& beat, int& tick) const
{
    if (currentBPM <= 0)
    {
        bar = 0; beat = 0; tick = 0;
        return;
    }
    
    double secondsPerBeat = 60.0 / currentBPM;
    double beatsTotal = timeSeconds / secondsPerBeat;
    
    int beatsInt = (int)beatsTotal;
    bar = beatsInt / 4;  // 4/4 time signature, 0-indexed
    beat = beatsInt % 4;  // 0-indexed beats (0-3)
    tick = (int)((beatsTotal - beatsInt) * 480);  // 480 ticks per beat (standard MIDI)
}

juce::String ArrangementView::formatBarBeat(double timeSeconds) const
{
    int bar, beat, tick;
    timeToBarBeat(timeSeconds, bar, beat, tick);
    
    // Format as "Bar.Beat.Tick" like Cubase/DAWs
    return juce::String(bar) + "." + juce::String(beat) + "." + juce::String(tick).paddedLeft('0', 3);
}

} // namespace UI
