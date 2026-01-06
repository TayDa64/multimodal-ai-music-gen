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
    if (pianoRoll)
        pianoRoll->setScrollX(scroll);
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
    
    // Sync all track lane piano rolls
    for (auto* lane : trackLanes)
        lane->setScrollX(scrollX);
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
        // MIDI track 0 is typically metadata (tempo, time signature) with no notes.
        // Track headers are 0-indexed but display as "Track 1", "Track 2", etc.
        // So lane 0 should show MIDI track 1's notes, lane 1 shows track 2, etc.
        int midiTrackIndex = laneIndex + 1;  // Offset by 1 to skip metadata track
        
        auto* lane = trackLanes.add(new TrackLaneContent(midiTrackIndex, audioEngine));
        
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
    
    // Time markers
    double secondsPerBeat = 60.0 / currentBPM;
    double secondsPerBar = secondsPerBeat * 4.0;
    float pixelsPerSecond = 100.0f * hZoom;
    
    // Get current scroll position from viewport (synced with track lanes)
    double scrollOffset = lanesViewport.getViewPositionX() / pixelsPerSecond;
    
    g.setFont(10.0f);
    
    // Draw bar numbers and beat markers with bar.beat format
    for (double time = 0.0; time < 600.0; time += secondsPerBeat)
    {
        float x = bounds.getX() + (float)((time - scrollOffset) * pixelsPerSecond);
        
        if (x < bounds.getX() - 50 || x > bounds.getRight() + 50)
            continue;
        
        int bar, beat, tick;
        timeToBarBeat(time, bar, beat, tick);
        bool isBar = (beat == 1 && tick == 0);
        
        if (isBar)
        {
            // Bar marker - thicker line and bar number
            g.setColour(ThemeManager::getCurrentScheme().text);
            g.drawVerticalLine((int)x, (float)bounds.getY() + 12, (float)bounds.getBottom());
            
            // Bar number (format: "1" for bar 1, or "1.1" to show bar.beat)
            g.setFont(11.0f);
            g.drawText(juce::String(bar), 
                      (int)x + 3, bounds.getY(), 40, 14,
                      juce::Justification::centredLeft);
        }
        else
        {
            // Beat marker - short tick with beat number at higher zoom
            g.setColour(ThemeManager::getCurrentScheme().textSecondary.withAlpha(0.5f));
            g.drawVerticalLine((int)x, (float)bounds.getBottom() - 8, (float)bounds.getBottom());
            
            // Show beat numbers when zoomed in enough
            if (hZoom >= 0.8f)
            {
                g.setFont(8.0f);
                g.setColour(ThemeManager::getCurrentScheme().textSecondary.withAlpha(0.6f));
                g.drawText(juce::String(bar) + "." + juce::String(beat), 
                          (int)x + 2, bounds.getY() + 16, 25, 10,
                          juce::Justification::centredLeft);
            }
        }
    }
}

//==============================================================================
// Time formatting helpers
void ArrangementView::timeToBarBeat(double timeSeconds, int& bar, int& beat, int& tick) const
{
    if (currentBPM <= 0)
    {
        bar = 1; beat = 1; tick = 0;
        return;
    }
    
    double secondsPerBeat = 60.0 / currentBPM;
    double beatsTotal = timeSeconds / secondsPerBeat;
    
    int beatsInt = (int)beatsTotal;
    bar = (beatsInt / 4) + 1;  // 4/4 time signature
    beat = (beatsInt % 4) + 1;
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
