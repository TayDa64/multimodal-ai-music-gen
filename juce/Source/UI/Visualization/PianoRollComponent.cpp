/*
  ==============================================================================

    PianoRollComponent.cpp
    
    Implementation of the piano roll visualization.

  ==============================================================================
*/

#include "PianoRollComponent.h"
#include "../Theme/ColourScheme.h"

//==============================================================================
PianoRollComponent::PianoRollComponent(mmg::AudioEngine& engine)
    : audioEngine(engine)
{
    // Enable mouse interaction
    setInterceptsMouseClicks(true, true);
    setWantsKeyboardFocus(true);
    
    audioEngine.addListener(this);
    startTimerHz(30);  // Update at 30fps
    
    // Set default scroll to middle C area
    scrollY = 60;
    
    // Setup Track Selector
    addAndMakeVisible(trackSelector);
    trackSelector.onChange = [this] { 
        soloedTrack = trackSelector.getSelectedId() - 2; // ID 1 = All, ID 2 = Track 0...
        if (soloedTrack < -1) soloedTrack = -1;
        repaint(); 
    };
    
    DBG("PianoRollComponent created");
}

PianoRollComponent::~PianoRollComponent()
{
    if (projectState)
        projectState->getState().removeListener(this);
        
    audioEngine.removeListener(this);
    stopTimer();
}

//==============================================================================
void PianoRollComponent::setProjectState(Project::ProjectState* state)
{
    if (projectState)
        projectState->getState().removeListener(this);
        
    projectState = state;
    
    if (projectState)
    {
        projectState->getState().addListener(this);
        syncNotesFromState();
    }
}

void PianoRollComponent::syncNotesFromState()
{
    if (!projectState) return;
    
    notes.clear();
    // Do NOT clear selection here, as it breaks drag operations.
    // Instead, we validate selection at the end.
    
    auto notesNode = projectState->getState().getChildWithName(Project::IDs::NOTES);
    if (!notesNode.isValid()) return;
    
    double secondsPerBeat = 60.0 / currentBPM;
    
    int maxTrackIndex = 0;
    
    // Also count tracks from mixer node to ensure all tracks show in dropdown
    auto mixerNode = projectState->getMixerNode();
    if (mixerNode.isValid())
    {
        for (const auto& child : mixerNode)
        {
            if (child.hasType(Project::IDs::TRACK))
            {
                int idx = child.getProperty(Project::IDs::index);
                maxTrackIndex = juce::jmax(maxTrackIndex, idx);
            }
        }
    }
    
    for (const auto& child : notesNode)
    {
        if (child.hasType(Project::IDs::NOTE))
        {
            MidiNoteEvent note;
            note.noteNumber = child.getProperty(Project::IDs::noteNumber);
            note.velocity = child.getProperty(Project::IDs::velocity);
            note.channel = child.getProperty(Project::IDs::channel); // This is actually track index in our model
            
            double startBeats = child.getProperty(Project::IDs::start);
            double lengthBeats = child.getProperty(Project::IDs::length);
            
            note.startTime = startBeats * secondsPerBeat;
            note.endTime = (startBeats + lengthBeats) * secondsPerBeat;
            note.trackIndex = note.channel; // Use channel as track index
            note.stateNode = child;
            
            notes.add(note);
            totalDuration = juce::jmax(totalDuration, note.endTime);
            maxTrackIndex = juce::jmax(maxTrackIndex, note.trackIndex);
        }
    }
    
    // Validate selection - remove nodes that no longer exist
    for (int i = selectedNotes.size() - 1; i >= 0; --i)
    {
        if (!selectedNotes[i].isValid() || !selectedNotes[i].getParent().isValid())
            selectedNotes.remove(i);
    }
    
    assignTrackColors(maxTrackIndex + 1);
    
    // Ensure minimum duration for playable area
    totalDuration = juce::jmax(totalDuration, minimumDuration);
    
    updateTrackList();
    repaint();
}

//==============================================================================
void PianoRollComponent::loadMidiFile(const juce::File& midiFile)
{
    // Legacy support - import into project state if available
    if (projectState)
    {
        projectState->importMidiFile(midiFile);
        // syncNotesFromState will be called via listener callback
    }
    else
    {
        // Fallback to visualization-only mode
        juce::FileInputStream stream(midiFile);
        if (stream.openedOk())
        {
            juce::MidiFile midi;
            if (midi.readFrom(stream))
            {
                setMidiData(midi);
            }
        }
    }
}

void PianoRollComponent::setMidiData(const juce::MidiFile& midiFile)
{
    // This is the legacy visualization-only path
    notes.clear();
    juce::MidiFile midiCopy = midiFile;
    midiCopy.convertTimestampTicksToSeconds();
    
    totalDuration = 0.0;
    int numTracks = midiCopy.getNumTracks();
    
    for (int trackIndex = 0; trackIndex < numTracks; ++trackIndex)
    {
        const juce::MidiMessageSequence* track = midiCopy.getTrack(trackIndex);
        if (track == nullptr) continue;
        
        std::map<int, std::vector<std::pair<double, int>>> activeNotes;
        
        for (int i = 0; i < track->getNumEvents(); ++i)
        {
            auto* event = track->getEventPointer(i);
            const auto& msg = event->message;
            double time = msg.getTimeStamp();
            
            if (msg.isNoteOn() && msg.getVelocity() > 0)
            {
                activeNotes[msg.getNoteNumber()].push_back({ time, msg.getVelocity() });
            }
            else if (msg.isNoteOff() || (msg.isNoteOn() && msg.getVelocity() == 0))
            {
                auto& noteStarts = activeNotes[msg.getNoteNumber()];
                if (!noteStarts.empty())
                {
                    auto [startTime, velocity] = noteStarts.front();
                    noteStarts.erase(noteStarts.begin());
                    
                    MidiNoteEvent note;
                    note.noteNumber = msg.getNoteNumber();
                    note.velocity = velocity;
                    note.startTime = startTime;
                    note.endTime = time;
                    note.channel = msg.getChannel();
                    note.trackIndex = trackIndex;
                    
                    notes.add(note);
                    totalDuration = juce::jmax(totalDuration, time);
                }
            }
        }
    }
    
    totalDuration = juce::jmax(totalDuration, 1.0);
    assignTrackColors(numTracks);
    zoomToFit();
    repaint();
}

void PianoRollComponent::clearNotes()
{
    if (projectState)
        projectState->clearNotes();
    else
        notes.clear();
        
    repaint();
}

void PianoRollComponent::setBPM(int bpm)
{
    currentBPM = juce::jlimit(30, 300, bpm);
    // Re-sync to update seconds based on new BPM
    syncNotesFromState(); 
    repaint();
}

//==============================================================================
void PianoRollComponent::setLoopRegion(double startSeconds, double endSeconds)
{
    if (startSeconds >= 0 && endSeconds > startSeconds)
    {
        loopRegionStart = startSeconds;
        loopRegionEnd = endSeconds;
        repaint();
    }
}

void PianoRollComponent::clearLoopRegion()
{
    loopRegionStart = -1.0;
    loopRegionEnd = -1.0;
    repaint();
}

//==============================================================================
void PianoRollComponent::setHorizontalZoom(float zoom)
{
    hZoom = juce::jlimit(0.1f, 10.0f, zoom);
    repaint();
}

void PianoRollComponent::setMinimumDuration(double seconds)
{
    minimumDuration = seconds;
    totalDuration = juce::jmax(totalDuration, minimumDuration);
    repaint();
}

void PianoRollComponent::setVerticalZoom(float zoom)
{
    vZoom = juce::jlimit(0.5f, 4.0f, zoom);
    repaint();
}

void PianoRollComponent::zoomToFit()
{
    if (notes.isEmpty() || totalDuration <= 0)
        return;
    
    float availableWidth = (float)(getWidth() - pianoKeyWidth);
    if (availableWidth > 0)
    {
        float targetPixelsPerSecond = availableWidth / (float)totalDuration;
        hZoom = juce::jlimit(0.1f, 10.0f, targetPixelsPerSecond / 100.0f);
    }
    
    int minNoteFound = 127, maxNoteFound = 0;
    for (const auto& note : notes)
    {
        minNoteFound = juce::jmin(minNoteFound, note.noteNumber);
        maxNoteFound = juce::jmax(maxNoteFound, note.noteNumber);
    }
    
    if (minNoteFound <= maxNoteFound)
    {
        scrollY = (minNoteFound + maxNoteFound) / 2;
    }
    
    scrollX = 0.0;
}

//==============================================================================
void PianoRollComponent::setTrackVisible(int trackIndex, bool visible)
{
    if (trackIndex >= 0 && trackIndex < trackVisible.size())
    {
        trackVisible.set(trackIndex, visible);
        repaint();
    }
}

bool PianoRollComponent::isTrackVisible(int trackIndex) const
{
    if (trackIndex >= 0 && trackIndex < trackVisible.size())
        return trackVisible[trackIndex];
    return true;
}

void PianoRollComponent::soloTrack(int trackIndex)
{
    soloedTrack = trackIndex;
    repaint();
}

void PianoRollComponent::setTrackCount(int count)
{
    // Force reassign track colors to ensure dropdown shows all tracks
    if (count > 0)
    {
        assignTrackColors(count);
        updateTrackList();
    }
}

juce::Colour PianoRollComponent::getTrackColour(int trackIndex) const
{
    if (trackIndex >= 0 && trackIndex < trackColors.size())
        return trackColors[trackIndex];
    return AppColours::primary;
}

void PianoRollComponent::assignTrackColors(int numTracks)
{
    // Always update to match requested count
    if (numTracks == trackColors.size()) return;
    
    trackColors.clear();
    trackVisible.clear();
    
    juce::Array<juce::Colour> palette = {
        juce::Colour(0xFFE91E63), juce::Colour(0xFF2196F3), juce::Colour(0xFF4CAF50),
        juce::Colour(0xFFFF9800), juce::Colour(0xFF9C27B0), juce::Colour(0xFF00BCD4),
        juce::Colour(0xFFFFEB3B), juce::Colour(0xFFF44336),
    };
    
    for (int i = 0; i < numTracks; ++i)
    {
        trackColors.add(palette[i % palette.size()]);
        trackVisible.add(true);
    }
}

void PianoRollComponent::updateTrackList()
{
    // Don't rebuild if menu is open or count matches
    if (trackSelector.isPopupActive()) return;
    
    int numTracks = trackColors.size();
    if (trackSelector.getNumItems() == numTracks + 1) return;
    
    trackSelector.clear();
    trackSelector.addItem("All Tracks", 1);
    
    auto mixerNode = projectState ? projectState->getMixerNode() : juce::ValueTree();
    
    for (int i = 0; i < numTracks; ++i)
    {
        juce::String name = "Track " + juce::String(i + 1);
        
        // Try to find name in mixer node
        if (mixerNode.isValid())
        {
            for (const auto& child : mixerNode)
            {
                if (child.hasType(Project::IDs::TRACK) && (int)child.getProperty(Project::IDs::index) == i)
                {
                    juce::String trackName = child.getProperty(Project::IDs::name);
                    if (trackName.isNotEmpty())
                        name = trackName;
                    break;
                }
            }
        }
        
        trackSelector.addItem(name, i + 2);
    }
    
    // Restore selection
    if (soloedTrack == -1)
        trackSelector.setSelectedId(1, juce::dontSendNotification);
    else
        trackSelector.setSelectedId(soloedTrack + 2, juce::dontSendNotification);
}

//==============================================================================
void PianoRollComponent::paint(juce::Graphics& g)
{
    drawBackground(g);
    drawGridLines(g);
    drawLoopRegion(g);  // Draw loop region behind notes
    drawNotes(g);
    
    if (isSelecting)
        drawSelectionRect(g);
        
    drawPlayhead(g);
    drawPianoKeys(g);
    
    if (hoveredNote != nullptr)
        drawNoteTooltip(g);
}

void PianoRollComponent::drawBackground(juce::Graphics& g)
{
    g.fillAll(AppColours::background);
    
    auto noteArea = getLocalBounds().withTrimmedLeft(pianoKeyWidth);
    float noteHeight = whiteKeyHeight * vZoom;
    int visibleNotes = (int)(getHeight() / noteHeight) + 2;
    int startNote = scrollY - visibleNotes / 2;
    
    for (int i = 0; i < visibleNotes; ++i)
    {
        int noteNum = startNote + i;
        if (noteNum < minNote || noteNum > maxNote) continue;
        
        float y = noteToY(noteNum);
        bool isBlackKey = juce::MidiMessage::isMidiNoteBlack(noteNum);
        
        g.setColour(isBlackKey ? AppColours::surface.darker(0.1f) : AppColours::surface);
        g.fillRect(noteArea.getX(), (int)y, noteArea.getWidth(), (int)noteHeight);
    }
}

void PianoRollComponent::drawPianoKeys(juce::Graphics& g)
{
    auto keyArea = getLocalBounds().removeFromLeft(pianoKeyWidth);
    g.setColour(AppColours::surfaceAlt);
    g.fillRect(keyArea);
    
    float noteHeight = whiteKeyHeight * vZoom;
    int visibleNotes = (int)(getHeight() / noteHeight) + 2;
    int startNote = scrollY - visibleNotes / 2;
    
    for (int i = 0; i < visibleNotes; ++i)
    {
        int noteNum = startNote + i;
        if (noteNum < minNote || noteNum > maxNote) continue;
        
        float y = noteToY(noteNum);
        bool isBlackKey = juce::MidiMessage::isMidiNoteBlack(noteNum);
        
        if (isBlackKey)
        {
            g.setColour(juce::Colours::black);
            g.fillRect(0, (int)y, blackKeyWidth, (int)noteHeight);
        }
        else
        {
            g.setColour(juce::Colours::white);
            g.fillRect(0, (int)y, pianoKeyWidth - 1, (int)noteHeight);
            g.setColour(AppColours::border);
            g.drawHorizontalLine((int)(y + noteHeight - 1), 0.0f, (float)pianoKeyWidth);
        }
        
        int noteName = noteNum % 12;
        if (noteName == 0 || vZoom >= 1.5f)
        {
            g.setColour(isBlackKey ? juce::Colours::white : juce::Colours::black);
            g.setFont(juce::jmin(10.0f, noteHeight - 2));
            
            juce::String label = MidiNoteEvent::getNoteName(noteNum);
            int labelX = isBlackKey ? blackKeyWidth + 2 : 2;
            g.drawText(label, labelX, (int)y, pianoKeyWidth - labelX - 2, (int)noteHeight,
                      juce::Justification::centredLeft);
        }
    }
    g.setColour(AppColours::border);
    g.drawVerticalLine(pianoKeyWidth - 1, 0.0f, (float)getHeight());
}

void PianoRollComponent::drawGridLines(juce::Graphics& g)
{
    auto noteArea = getLocalBounds().withTrimmedLeft(pianoKeyWidth);
    if (currentBPM <= 0) return;
    
    double secondsPerBeat = 60.0 / currentBPM;
    double secondsPerBar = secondsPerBeat * 4.0;
    
    double startTime = juce::jmax(0.0, scrollX);
    double endTime = scrollX + noteArea.getWidth() / (100.0f * hZoom);
    
    g.setColour(AppColours::border.withAlpha(0.3f));
    for (double time = 0.0; time <= totalDuration; time += secondsPerBeat)
    {
        if (time < startTime - secondsPerBeat || time > endTime + secondsPerBeat)
            continue;
        
        float x = timeToX(time);
        if (x >= pianoKeyWidth && x < getWidth())
        {
            bool isBar = std::fmod(time, secondsPerBar) < 0.001;
            if (isBar)
            {
                g.setColour(AppColours::border.withAlpha(0.6f));
                g.drawVerticalLine((int)x, 0.0f, (float)getHeight());
            }
            else
            {
                g.setColour(AppColours::border.withAlpha(0.2f));
                g.drawVerticalLine((int)x, 0.0f, (float)getHeight());
            }
        }
    }
}

void PianoRollComponent::drawLoopRegion(juce::Graphics& g)
{
    if (!hasLoopRegion())
        return;
    
    float startX = timeToX(loopRegionStart);
    float endX = timeToX(loopRegionEnd);
    
    // Clamp to visible area
    startX = juce::jmax(startX, (float)pianoKeyWidth);
    endX = juce::jmin(endX, (float)getWidth());
    
    if (endX <= startX)
        return;
    
    // Draw loop region background (semi-transparent cyan)
    juce::Colour loopColour = juce::Colour(0xFF00BCD4);  // Cyan
    g.setColour(loopColour.withAlpha(0.1f));
    g.fillRect(startX, 0.0f, endX - startX, (float)getHeight());
    
    // Draw loop region borders
    g.setColour(loopColour.withAlpha(0.6f));
    g.drawLine(startX, 0.0f, startX, (float)getHeight(), 2.0f);
    g.drawLine(endX, 0.0f, endX, (float)getHeight(), 2.0f);
    
    // Draw loop brackets at top
    const float bracketHeight = 8.0f;
    const float bracketWidth = 5.0f;
    
    g.setColour(loopColour.withAlpha(0.8f));
    
    // Start bracket [
    g.drawLine(startX, 0.0f, startX, bracketHeight, 2.0f);
    g.drawLine(startX, 0.0f, startX + bracketWidth, 0.0f, 2.0f);
    g.drawLine(startX, bracketHeight, startX + bracketWidth, bracketHeight, 2.0f);
    
    // End bracket ]
    g.drawLine(endX, 0.0f, endX, bracketHeight, 2.0f);
    g.drawLine(endX, 0.0f, endX - bracketWidth, 0.0f, 2.0f);
    g.drawLine(endX, bracketHeight, endX - bracketWidth, bracketHeight, 2.0f);
}

void PianoRollComponent::drawNotes(juce::Graphics& g)
{
    float noteHeight = whiteKeyHeight * vZoom;
    
    for (const auto& note : notes)
    {
        // Filter by track
        if (soloedTrack >= 0 && note.trackIndex != soloedTrack) 
        {
            // Optional: Draw ghost notes?
            // For now, just skip to reduce clutter as requested
            continue; 
        }
        
        if (!isTrackVisible(note.trackIndex)) continue;
        
        float x = timeToX(note.startTime);
        float endX = timeToX(note.endTime);
        float y = noteToY(note.noteNumber);
        float width = juce::jmax(2.0f, endX - x);
        
        if (endX < pianoKeyWidth || x > getWidth()) continue;
        if (y + noteHeight < 0 || y > getHeight()) continue;
        
        if (x < pianoKeyWidth)
        {
            width -= (pianoKeyWidth - x);
            x = pianoKeyWidth;
        }
        
        juce::Colour noteColour = getTrackColour(note.trackIndex);
        float velocityBrightness = 0.5f + (note.velocity / 127.0f) * 0.5f;
        noteColour = noteColour.withMultipliedBrightness(velocityBrightness);
        
        // Selection highlight
        bool isSelected = selectedNotes.contains(note.stateNode);
        if (isSelected)
            noteColour = juce::Colours::white;
        else if (&note == hoveredNote)
            noteColour = noteColour.brighter(0.3f);
        
        juce::Rectangle<float> noteRect(x, y + 1, width, noteHeight - 2);
        
        // Draw note release tail (decay visualization)
        if (showReleaseTails && !isSelected)
        {
            // Calculate release tail length (proportional to velocity)
            double releaseTime = defaultReleaseTime * (note.velocity / 127.0f);
            float releaseEndX = timeToX(note.endTime + releaseTime);
            float releaseWidth = releaseEndX - endX;
            
            if (releaseWidth > 0 && releaseEndX <= getWidth())
            {
                // Draw gradient tail showing decay
                juce::ColourGradient gradient(
                    noteColour.withAlpha(0.6f), endX, y + noteHeight / 2,
                    noteColour.withAlpha(0.0f), releaseEndX, y + noteHeight / 2,
                    false
                );
                g.setGradientFill(gradient);
                g.fillRoundedRectangle(endX, y + 2, releaseWidth, noteHeight - 4, 2.0f);
            }
        }
        
        // Draw main note body
        g.setColour(noteColour);
        g.fillRoundedRectangle(noteRect, 2.0f);
        
        g.setColour(noteColour.darker(0.3f));
        g.drawRoundedRectangle(noteRect, 2.0f, 1.0f);
        
        // Draw velocity indicator (small bar at note start)
        float velocityHeight = (noteHeight - 4) * (note.velocity / 127.0f);
        g.setColour(noteColour.brighter(0.4f));
        g.fillRect(x + 1, y + 2 + (noteHeight - 4 - velocityHeight), 2.0f, velocityHeight);
    }
}

void PianoRollComponent::drawSelectionRect(juce::Graphics& g)
{
    g.setColour(juce::Colours::white.withAlpha(0.2f));
    g.fillRect(selectionRect);
    g.setColour(juce::Colours::white.withAlpha(0.5f));
    g.drawRect(selectionRect);
}

void PianoRollComponent::drawPlayhead(juce::Graphics& g)
{
    float x = timeToX(playheadPosition);
    if (x >= pianoKeyWidth && x <= getWidth())
    {
        g.setColour(AppColours::primary);
        g.drawVerticalLine((int)x, 0.0f, (float)getHeight());
        juce::Path triangle;
        triangle.addTriangle(x - 5, 0.0f, x + 5, 0.0f, x, 8.0f);
        g.fillPath(triangle);
    }
}

void PianoRollComponent::drawNoteTooltip(juce::Graphics& g)
{
    if (hoveredNote == nullptr) return;
    
    juce::String text = MidiNoteEvent::getNoteName(hoveredNote->noteNumber);
    text += " | Vel: " + juce::String(hoveredNote->velocity);
    text += " | " + juce::String(hoveredNote->getDuration() * 1000.0, 0) + "ms";
    
    g.setFont(12.0f);
    int textWidth = (int)g.getCurrentFont().getStringWidthFloat(text) + 12;
    int textHeight = 20;
    
    int x = (int)lastMousePos.x + 10;
    int y = (int)lastMousePos.y - textHeight - 5;
    
    if (x + textWidth > getWidth()) x = getWidth() - textWidth - 5;
    if (y < 0) y = (int)lastMousePos.y + 15;
    
    g.setColour(AppColours::surface);
    g.fillRoundedRectangle((float)x, (float)y, (float)textWidth, (float)textHeight, 4.0f);
    g.setColour(AppColours::border);
    g.drawRoundedRectangle((float)x, (float)y, (float)textWidth, (float)textHeight, 4.0f, 1.0f);
    g.setColour(AppColours::textPrimary);
    g.drawText(text, x + 6, y, textWidth - 12, textHeight, juce::Justification::centredLeft);
}

//==============================================================================
float PianoRollComponent::timeToX(double timeSeconds) const
{
    return pianoKeyWidth + (float)((timeSeconds - scrollX) * 100.0 * hZoom);
}

double PianoRollComponent::xToTime(float x) const
{
    return scrollX + (x - pianoKeyWidth) / (100.0 * hZoom);
}

float PianoRollComponent::noteToY(int noteNumber) const
{
    float noteHeight = whiteKeyHeight * vZoom;
    int noteOffset = scrollY - noteNumber;
    return getHeight() / 2.0f + noteOffset * noteHeight;
}

int PianoRollComponent::yToNote(float y) const
{
    float noteHeight = whiteKeyHeight * vZoom;
    int noteOffset = (int)((getHeight() / 2.0f - y) / noteHeight);
    return scrollY + noteOffset;
}

MidiNoteEvent* PianoRollComponent::getNoteAt(juce::Point<float> position)
{
    if (position.x < pianoKeyWidth) return nullptr;
    float noteHeight = whiteKeyHeight * vZoom;
    
    for (auto& note : notes)
    {
        if (soloedTrack >= 0 && note.trackIndex != soloedTrack) continue;
        if (!isTrackVisible(note.trackIndex)) continue;
        
        float x = timeToX(note.startTime);
        float endX = timeToX(note.endTime);
        float y = noteToY(note.noteNumber);
        
        juce::Rectangle<float> noteRect(x, y, endX - x, noteHeight);
        // Expand hit area slightly for easier grabbing
        if (noteRect.expanded(0, 1).contains(position))
            return &note;
    }
    return nullptr;
}

//==============================================================================
void PianoRollComponent::setEmbeddedMode(bool embedded)
{
    embeddedMode = embedded;
    trackSelector.setVisible(!embedded);
    repaint();
}

void PianoRollComponent::resized() 
{
    if (!embeddedMode)
        trackSelector.setBounds(getWidth() - 150 - 10, 10, 150, 24);
}

void PianoRollComponent::mouseDown(const juce::MouseEvent& event)
{
    grabKeyboardFocus();
    lastMousePos = event.position;
    dragStartPos = event.position;
    
    if (event.mods.isLeftButtonDown())
    {
        clickStartTime = juce::Time::currentTimeMillis();
        
        if (event.x <= pianoKeyWidth) return; // Piano keys
        
        auto* note = getNoteAt(event.position);
        
        if (note)
        {
            // Play the note for feedback
            audioEngine.playNote(note->trackIndex, note->noteNumber, note->velocity / 127.0f);

            // Clicked on a note
            if (event.mods.isShiftDown())
            {
                // Toggle selection
                if (selectedNotes.contains(note->stateNode))
                    selectedNotes.removeFirstMatchingValue(note->stateNode);
                else
                    selectedNotes.add(note->stateNode);
            }
            else
            {
                // Select only this note (unless already selected)
                if (!selectedNotes.contains(note->stateNode))
                {
                    selectedNotes.clear();
                    selectedNotes.add(note->stateNode);
                }
            }
            
            // Check for resize (right edge)
            float endX = timeToX(note->endTime);
            if (std::abs(event.position.x - endX) < 5.0f)
            {
                isResizing = true;
                isMoving = false;
            }
            else
            {
                isMoving = true;
                isResizing = false;
            }
            
            dragStartNoteStart = note->startTime;
            dragStartNoteNum = note->noteNumber;
            
            if (projectState)
                projectState->getUndoManager().beginNewTransaction(isResizing ? "Resize Note" : "Move Note");
        }
        else
        {
            // Clicked on empty space
            if (!event.mods.isShiftDown())
                selectedNotes.clear();
                
            isSelecting = true;
            selectionRect.setPosition(event.position.toInt());
            selectionRect.setSize(0, 0);
            
            // Seek if simple click (handled in mouseUp to distinguish from drag)
        }
        
        repaint();
    }
    else if (event.mods.isMiddleButtonDown())
    {
        isDragging = true; // Pan
    }
}

void PianoRollComponent::mouseDrag(const juce::MouseEvent& event)
{
    if (isDragging) // Pan
    {
        float deltaX = event.position.x - lastMousePos.x;
        float deltaY = event.position.y - lastMousePos.y;
        scrollX = juce::jmax(0.0, scrollX - deltaX / (100.0f * hZoom));
        float noteHeight = whiteKeyHeight * vZoom;
        scrollY = juce::jlimit(minNote, maxNote, scrollY + (int)(deltaY / noteHeight));
        lastMousePos = event.position;
        repaint();
        return;
    }
    
    if (!projectState) return;
    
    double secondsPerBeat = 60.0 / currentBPM;
    
    if (isMoving)
    {
        float deltaX = event.position.x - dragStartPos.x;
        float deltaY = event.position.y - dragStartPos.y;
        
        double deltaTime = deltaX / (100.0 * hZoom);
        int deltaNote = (int)(-deltaY / (whiteKeyHeight * vZoom));
        
        for (auto& noteNode : selectedNotes)
        {
            // Find original note data to apply delta
            // This is tricky because we're modifying live.
            // Better: Calculate new absolute position for the dragged note, and apply delta to others.
            // For simplicity, let's just update the model directly.
            // But we need to avoid drift.
            
            // Actually, we should update the ValueTree, which triggers sync, which updates UI.
            // But that might be slow for dragging.
            // Let's update ValueTree.
            
            // We need the original state.
            // For now, let's just use the current state + delta, but reset dragStartPos to avoid accumulation error?
            // No, standard way:
            
            double currentStart = noteNode.getProperty(Project::IDs::start);
            int currentNote = noteNode.getProperty(Project::IDs::noteNumber);
            
            double newStart = currentStart + (deltaTime / secondsPerBeat);
            int newNoteNum = currentNote + deltaNote;
            
            // Prevent notes from being dragged before beat 0
            newStart = juce::jmax(0.0, newStart);
            
            // Clamp note number to valid MIDI range
            newNoteNum = juce::jlimit(0, 127, newNoteNum);
            
            // Snap to grid?
            // if (!event.mods.isAltDown()) ...
            
            projectState->moveNote(noteNode, newStart, newNoteNum);
        }
        
        dragStartPos = event.position; // Reset for incremental updates
    }
    else if (isResizing)
    {
        float deltaX = event.position.x - dragStartPos.x;
        double deltaTime = deltaX / (100.0 * hZoom);
        
        for (auto& noteNode : selectedNotes)
        {
            double currentLen = noteNode.getProperty(Project::IDs::length);
            double newLen = juce::jmax(0.1, currentLen + (deltaTime / secondsPerBeat));
            projectState->resizeNote(noteNode, newLen);
        }
        
        dragStartPos = event.position;
    }
    else if (isSelecting)
    {
        selectionRect.setBounds(
            juce::jmin((int)dragStartPos.x, event.x),
            juce::jmin((int)dragStartPos.y, event.y),
            std::abs(event.x - (int)dragStartPos.x),
            std::abs(event.y - (int)dragStartPos.y)
        );
        
        // Update selection based on rect
        selectedNotes.clear();
        for (auto& note : notes)
        {
            float x = timeToX(note.startTime);
            float endX = timeToX(note.endTime);
            float y = noteToY(note.noteNumber);
            float h = whiteKeyHeight * vZoom;
            
            juce::Rectangle<float> noteRect(x, y, endX - x, h);
            if (selectionRect.toFloat().intersects(noteRect))
            {
                selectedNotes.add(note.stateNode);
            }
        }
        repaint();
    }
}

void PianoRollComponent::mouseUp(const juce::MouseEvent& event)
{
    if (isSelecting)
    {
        isSelecting = false;
        repaint();
    }
    else if (!isMoving && !isResizing && !isDragging)
    {
        // Simple click on empty space -> Seek
        if (event.x > pianoKeyWidth && selectedNotes.isEmpty())
        {
            double time = xToTime(event.position.x);
            audioEngine.setPlaybackPosition(time);
            listeners.call(&PianoRollComponent::Listener::pianoRollSeekRequested, time);
        }
    }
    
    isMoving = false;
    isResizing = false;
    isDragging = false;
}

void PianoRollComponent::mouseDoubleClick(const juce::MouseEvent& event)
{
    if (!projectState) return;
    if (event.x <= pianoKeyWidth) return;
    
    // Only allow adding notes if a specific track is selected (to know where to put it)
    // Or default to track 0 if "All" is selected?
    // Better: Default to track 0, or the last selected note's track.
    int targetTrack = (soloedTrack >= 0) ? soloedTrack : 0;
    
    double time = xToTime(event.position.x);
    int noteNum = yToNote(event.position.y);
    
    double secondsPerBeat = 60.0 / currentBPM;
    double beat = time / secondsPerBeat;
    
    // Snap to grid (quarter note)
    beat = std::round(beat * 4.0) / 4.0;
    
    projectState->getUndoManager().beginNewTransaction("Add Note");
    projectState->addNote(noteNum, beat, 1.0, 100, targetTrack);
    
    // Play the new note
    audioEngine.playNote(targetTrack, noteNum, 100.0f / 127.0f);
}

bool PianoRollComponent::keyPressed(const juce::KeyPress& key)
{
    if (key.isKeyCode(juce::KeyPress::deleteKey) || key.isKeyCode(juce::KeyPress::backspaceKey))
    {
        if (!selectedNotes.isEmpty() && projectState)
        {
            projectState->getUndoManager().beginNewTransaction("Delete Notes");
            for (auto& note : selectedNotes)
            {
                projectState->deleteNote(note);
            }
            selectedNotes.clear();
            return true;
        }
    }
    return false;
}

void PianoRollComponent::mouseMove(const juce::MouseEvent& event)
{
    lastMousePos = event.position;
    auto* note = getNoteAt(event.position);
    
    if (note != hoveredNote)
    {
        hoveredNote = note;
        listeners.call(&PianoRollComponent::Listener::pianoRollNoteHovered, note);
        repaint();
    }
    
    // Cursor updates
    if (note)
    {
        float endX = timeToX(note->endTime);
        if (std::abs(event.position.x - endX) < 5.0f)
            setMouseCursor(juce::MouseCursor::LeftRightResizeCursor);
        else
            setMouseCursor(juce::MouseCursor::NormalCursor);
    }
    else
    {
        setMouseCursor(juce::MouseCursor::NormalCursor);
    }
}

void PianoRollComponent::mouseWheelMove(const juce::MouseEvent& event, const juce::MouseWheelDetails& wheel)
{
    if (event.mods.isShiftDown())
    {
        float zoomFactor = wheel.deltaY > 0 ? 1.15f : 0.87f;
        hZoom = juce::jlimit(0.1f, 10.0f, hZoom * zoomFactor);
        repaint();
    }
    else if (event.mods.isCtrlDown() || event.mods.isCommandDown())
    {
        float zoomFactor = wheel.deltaY > 0 ? 1.15f : 0.87f;
        vZoom = juce::jlimit(0.5f, 4.0f, vZoom * zoomFactor);
        repaint();
    }
    else
    {
        if (std::abs(wheel.deltaX) > 0.001f)
            scrollX = juce::jmax(0.0, scrollX - wheel.deltaX * 2.0);
        
        int scrollAmount = (int)(wheel.deltaY * 8);
        scrollY = juce::jlimit(minNote, maxNote, scrollY - scrollAmount);
        repaint();
    }
}

void PianoRollComponent::mouseExit(const juce::MouseEvent& /*event*/)
{
    if (hoveredNote != nullptr)
    {
        hoveredNote = nullptr;
        listeners.call(&PianoRollComponent::Listener::pianoRollNoteHovered, nullptr);
        repaint();
    }
}

//==============================================================================
void PianoRollComponent::transportStateChanged(mmg::AudioEngine::TransportState /*newState*/) {}

void PianoRollComponent::playbackPositionChanged(double positionSeconds)
{
    playheadPosition = positionSeconds;
    juce::MessageManager::callAsync([this]() { repaint(); });
}

void PianoRollComponent::timerCallback()
{
    if (audioEngine.isPlaying())
    {
        playheadPosition = audioEngine.getPlaybackPosition();
        repaint();
    }
}

//==============================================================================
void PianoRollComponent::addListener(Listener* listener) { listeners.add(listener); }
void PianoRollComponent::removeListener(Listener* listener) { listeners.remove(listener); }

//==============================================================================
// ProjectState::Listener overrides
void PianoRollComponent::valueTreePropertyChanged(juce::ValueTree& tree, const juce::Identifier& property)
{
    if (tree.hasType(Project::IDs::NOTE))
        syncNotesFromState();
}

void PianoRollComponent::valueTreeChildAdded(juce::ValueTree& parent, juce::ValueTree& child)
{
    if (child.hasType(Project::IDs::NOTE))
        syncNotesFromState();
}

void PianoRollComponent::valueTreeChildRemoved(juce::ValueTree& parent, juce::ValueTree& child, int index)
{
    if (child.hasType(Project::IDs::NOTE))
        syncNotesFromState();
}

void PianoRollComponent::valueTreeChildOrderChanged(juce::ValueTree&, int, int) {}
void PianoRollComponent::valueTreeParentChanged(juce::ValueTree&) {}
