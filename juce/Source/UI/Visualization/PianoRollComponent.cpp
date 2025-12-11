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
    
    DBG("PianoRollComponent created");
}

PianoRollComponent::~PianoRollComponent()
{
    audioEngine.removeListener(this);
    stopTimer();
}

//==============================================================================
void PianoRollComponent::loadMidiFile(const juce::File& midiFile)
{
    DBG("PianoRollComponent::loadMidiFile: " << midiFile.getFullPathName());
    
    juce::FileInputStream stream(midiFile);
    if (stream.openedOk())
    {
        juce::MidiFile midi;
        if (midi.readFrom(stream))
        {
            DBG("MIDI file loaded successfully, parsing...");
            setMidiData(midi);
            DBG("Loaded " << notes.size() << " notes from MIDI file");
        }
        else
        {
            DBG("ERROR: Failed to parse MIDI file");
        }
    }
    else
    {
        DBG("ERROR: Failed to open MIDI file stream");
    }
}

void PianoRollComponent::setMidiData(const juce::MidiFile& midiFile)
{
    notes.clear();
    
    // Get time format
    short timeFormat = midiFile.getTimeFormat();
    DBG("setMidiData: timeFormat=" << timeFormat);
    
    // Create a copy to convert timestamps
    juce::MidiFile midiCopy = midiFile;
    midiCopy.convertTimestampTicksToSeconds();
    
    // Track the maximum end time
    totalDuration = 0.0;
    
    // Process each track
    int numTracks = midiCopy.getNumTracks();
    DBG("setMidiData: numTracks=" << numTracks);
    
    for (int trackIndex = 0; trackIndex < numTracks; ++trackIndex)
    {
        const juce::MidiMessageSequence* track = midiCopy.getTrack(trackIndex);
        if (track == nullptr) continue;
        
        // Map to track note-on events to their corresponding note-offs
        std::map<int, std::vector<std::pair<double, int>>> activeNotes; // noteNum -> [(startTime, velocity)]
        
        for (int i = 0; i < track->getNumEvents(); ++i)
        {
            auto* event = track->getEventPointer(i);
            if (event == nullptr) continue;
            
            const auto& msg = event->message;
            double time = msg.getTimeStamp();
            
            if (msg.isNoteOn() && msg.getVelocity() > 0)
            {
                int noteNum = msg.getNoteNumber();
                int velocity = msg.getVelocity();
                activeNotes[noteNum].push_back({ time, velocity });
            }
            else if (msg.isNoteOff() || (msg.isNoteOn() && msg.getVelocity() == 0))
            {
                int noteNum = msg.getNoteNumber();
                auto& noteStarts = activeNotes[noteNum];
                
                if (!noteStarts.empty())
                {
                    auto [startTime, velocity] = noteStarts.front();
                    noteStarts.erase(noteStarts.begin());
                    
                    MidiNoteEvent note;
                    note.noteNumber = noteNum;
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
        
        // Handle any notes that didn't get a note-off
        for (auto& [noteNum, noteStarts] : activeNotes)
        {
            for (auto& [startTime, velocity] : noteStarts)
            {
                MidiNoteEvent note;
                note.noteNumber = noteNum;
                note.velocity = velocity;
                note.startTime = startTime;
                note.endTime = totalDuration;  // Extend to end
                note.channel = 0;
                note.trackIndex = trackIndex;
                notes.add(note);
            }
        }
    }
    
    // Ensure minimum duration
    totalDuration = juce::jmax(totalDuration, 1.0);
    
    // Assign colors to tracks
    assignTrackColors(numTracks);
    
    // Auto-zoom to fit
    zoomToFit();
    
    repaint();
}

void PianoRollComponent::clearNotes()
{
    notes.clear();
    trackColors.clear();
    trackVisible.clear();
    totalDuration = 60.0;
    repaint();
}

void PianoRollComponent::setBPM(int bpm)
{
    currentBPM = juce::jlimit(30, 300, bpm);
    repaint();
}

//==============================================================================
void PianoRollComponent::setHorizontalZoom(float zoom)
{
    hZoom = juce::jlimit(0.1f, 10.0f, zoom);
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
    
    // Calculate horizontal zoom to fit duration
    float availableWidth = (float)(getWidth() - pianoKeyWidth);
    if (availableWidth > 0)
    {
        // Target: 100 pixels per second at zoom 1.0
        float targetPixelsPerSecond = availableWidth / (float)totalDuration;
        hZoom = juce::jlimit(0.1f, 10.0f, targetPixelsPerSecond / 100.0f);
    }
    
    // Find note range
    int minNoteFound = 127, maxNoteFound = 0;
    for (const auto& note : notes)
    {
        minNoteFound = juce::jmin(minNoteFound, note.noteNumber);
        maxNoteFound = juce::jmax(maxNoteFound, note.noteNumber);
    }
    
    // Center on the note range
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

juce::Colour PianoRollComponent::getTrackColour(int trackIndex) const
{
    if (trackIndex >= 0 && trackIndex < trackColors.size())
        return trackColors[trackIndex];
    return AppColours::primary;
}

void PianoRollComponent::assignTrackColors(int numTracks)
{
    trackColors.clear();
    trackVisible.clear();
    
    // Predefined palette for common track types
    juce::Array<juce::Colour> palette = {
        juce::Colour(0xFFE91E63),  // Pink - drums
        juce::Colour(0xFF2196F3),  // Blue - bass
        juce::Colour(0xFF4CAF50),  // Green - chords
        juce::Colour(0xFFFF9800),  // Orange - melody
        juce::Colour(0xFF9C27B0),  // Purple - lead
        juce::Colour(0xFF00BCD4),  // Cyan - pads
        juce::Colour(0xFFFFEB3B),  // Yellow - fx
        juce::Colour(0xFFF44336),  // Red - percussion
    };
    
    for (int i = 0; i < numTracks; ++i)
    {
        trackColors.add(palette[i % palette.size()]);
        trackVisible.add(true);
    }
}

//==============================================================================
void PianoRollComponent::paint(juce::Graphics& g)
{
    drawBackground(g);
    drawGridLines(g);
    drawNotes(g);
    drawPlayhead(g);
    drawPianoKeys(g);
    
    if (hoveredNote != nullptr)
        drawNoteTooltip(g);
}

void PianoRollComponent::drawBackground(juce::Graphics& g)
{
    g.fillAll(AppColours::background);
    
    // Draw alternating row colors for white/black keys
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
    
    // Background
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
        
        // Key background
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
        
        // Note label (only on C notes or if zoomed in)
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
    
    // Border
    g.setColour(AppColours::border);
    g.drawVerticalLine(pianoKeyWidth - 1, 0.0f, (float)getHeight());
}

void PianoRollComponent::drawGridLines(juce::Graphics& g)
{
    auto noteArea = getLocalBounds().withTrimmedLeft(pianoKeyWidth);
    
    if (currentBPM <= 0) return;
    
    double secondsPerBeat = 60.0 / currentBPM;
    double secondsPerBar = secondsPerBeat * 4.0;
    
    // Calculate visible time range
    double startTime = juce::jmax(0.0, scrollX);
    double endTime = scrollX + noteArea.getWidth() / (100.0f * hZoom);
    
    // Draw beat lines
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

void PianoRollComponent::drawNotes(juce::Graphics& g)
{
    float noteHeight = whiteKeyHeight * vZoom;
    
    for (const auto& note : notes)
    {
        // Check track visibility
        if (soloedTrack >= 0 && note.trackIndex != soloedTrack)
            continue;
        if (!isTrackVisible(note.trackIndex))
            continue;
        
        float x = timeToX(note.startTime);
        float endX = timeToX(note.endTime);
        float y = noteToY(note.noteNumber);
        float width = juce::jmax(2.0f, endX - x);
        
        // Skip if off-screen
        if (endX < pianoKeyWidth || x > getWidth())
            continue;
        if (y + noteHeight < 0 || y > getHeight())
            continue;
        
        // Clamp to visible area
        if (x < pianoKeyWidth)
        {
            width -= (pianoKeyWidth - x);
            x = pianoKeyWidth;
        }
        
        // Get track color
        juce::Colour noteColour = getTrackColour(note.trackIndex);
        
        // Adjust brightness by velocity
        float velocityBrightness = 0.5f + (note.velocity / 127.0f) * 0.5f;
        noteColour = noteColour.withMultipliedBrightness(velocityBrightness);
        
        // Highlight hovered note
        if (&note == hoveredNote)
            noteColour = noteColour.brighter(0.3f);
        
        // Draw note
        juce::Rectangle<float> noteRect(x, y + 1, width, noteHeight - 2);
        
        g.setColour(noteColour);
        g.fillRoundedRectangle(noteRect, 2.0f);
        
        g.setColour(noteColour.darker(0.3f));
        g.drawRoundedRectangle(noteRect, 2.0f, 1.0f);
    }
}

void PianoRollComponent::drawPlayhead(juce::Graphics& g)
{
    float x = timeToX(playheadPosition);
    
    if (x >= pianoKeyWidth && x <= getWidth())
    {
        g.setColour(AppColours::primary);
        g.drawVerticalLine((int)x, 0.0f, (float)getHeight());
        
        // Triangle at top
        juce::Path triangle;
        triangle.addTriangle(x - 5, 0.0f, x + 5, 0.0f, x, 8.0f);
        g.fillPath(triangle);
    }
}

void PianoRollComponent::drawNoteTooltip(juce::Graphics& g)
{
    if (hoveredNote == nullptr)
    {
        // No hovered note - check if we have any notes to show debug
        if (notes.isEmpty())
        {
            // Draw "No notes loaded" message if empty
            g.setColour(AppColours::textSecondary.withAlpha(0.5f));
            g.setFont(14.0f);
            g.drawText("Load a MIDI file to see notes", getLocalBounds(), juce::Justification::centred);
        }
        return;
    }
    
    juce::String text = MidiNoteEvent::getNoteName(hoveredNote->noteNumber);
    text += " | Vel: " + juce::String(hoveredNote->velocity);
    text += " | " + juce::String(hoveredNote->getDuration() * 1000.0, 0) + "ms";
    
    g.setFont(12.0f);
    int textWidth = (int)g.getCurrentFont().getStringWidthFloat(text) + 12;
    int textHeight = 20;
    
    int x = (int)lastMousePos.x + 10;
    int y = (int)lastMousePos.y - textHeight - 5;
    
    // Keep on screen
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
    // 100 pixels per second at zoom 1.0
    return pianoKeyWidth + (float)((timeSeconds - scrollX) * 100.0 * hZoom);
}

double PianoRollComponent::xToTime(float x) const
{
    return scrollX + (x - pianoKeyWidth) / (100.0 * hZoom);
}

float PianoRollComponent::noteToY(int noteNumber) const
{
    float noteHeight = whiteKeyHeight * vZoom;
    // Higher notes at top
    int noteOffset = scrollY - noteNumber;
    return getHeight() / 2.0f + noteOffset * noteHeight;
}

int PianoRollComponent::yToNote(float y) const
{
    float noteHeight = whiteKeyHeight * vZoom;
    int noteOffset = (int)((getHeight() / 2.0f - y) / noteHeight);
    return scrollY + noteOffset;
}

const MidiNoteEvent* PianoRollComponent::getNoteAt(juce::Point<float> position) const
{
    if (position.x < pianoKeyWidth) return nullptr;
    
    float noteHeight = whiteKeyHeight * vZoom;
    
    for (const auto& note : notes)
    {
        // Check visibility
        if (soloedTrack >= 0 && note.trackIndex != soloedTrack)
            continue;
        if (!isTrackVisible(note.trackIndex))
            continue;
        
        float x = timeToX(note.startTime);
        float endX = timeToX(note.endTime);
        float y = noteToY(note.noteNumber);
        
        juce::Rectangle<float> noteRect(x, y, endX - x, noteHeight);
        
        if (noteRect.contains(position))
            return &note;
    }
    
    return nullptr;
}

//==============================================================================
void PianoRollComponent::resized()
{
    // Nothing special needed
}

void PianoRollComponent::mouseDown(const juce::MouseEvent& event)
{
    DBG("PianoRoll mouseDown at " << event.position.toString());
    
    // Grab focus for keyboard shortcuts
    grabKeyboardFocus();
    
    if (event.mods.isLeftButtonDown())
    {
        isDragging = true;
        lastMousePos = event.position;
        
        // Seek to position if clicking in note area (Ctrl/Cmd + click)
        if (event.x > pianoKeyWidth && (event.mods.isCommandDown() || event.mods.isCtrlDown()))
        {
            double time = xToTime(event.position.x);
            audioEngine.setPlaybackPosition(time);
            listeners.call(&Listener::pianoRollSeekRequested, time);
        }
    }
    else if (event.mods.isMiddleButtonDown())
    {
        // Middle-click also starts drag
        isDragging = true;
        lastMousePos = event.position;
    }
}

void PianoRollComponent::mouseDrag(const juce::MouseEvent& event)
{
    if (isDragging)
    {
        float deltaX = event.position.x - lastMousePos.x;
        float deltaY = event.position.y - lastMousePos.y;
        
        // Scroll
        scrollX -= deltaX / (100.0f * hZoom);
        scrollX = juce::jmax(0.0, scrollX);
        
        float noteHeight = whiteKeyHeight * vZoom;
        scrollY += (int)(deltaY / noteHeight);
        scrollY = juce::jlimit(minNote, maxNote, scrollY);
        
        lastMousePos = event.position;
        repaint();
    }
}

void PianoRollComponent::mouseMove(const juce::MouseEvent& event)
{
    lastMousePos = event.position;
    
    auto* note = getNoteAt(event.position);
    if (note != hoveredNote)
    {
        hoveredNote = note;
        if (note != nullptr)
        {
            DBG("Hovering note: " << MidiNoteEvent::getNoteName(note->noteNumber) << " vel=" << note->velocity);
        }
        listeners.call(&Listener::pianoRollNoteHovered, note);
        repaint();
    }
}

void PianoRollComponent::mouseWheelMove(const juce::MouseEvent& event, const juce::MouseWheelDetails& wheel)
{
    DBG("PianoRoll mouseWheel deltaY=" << wheel.deltaY << " shift=" << event.mods.isShiftDown() << " ctrl=" << event.mods.isCtrlDown());
    
    if (event.mods.isShiftDown())
    {
        // Horizontal zoom with Shift + wheel
        float zoomFactor = wheel.deltaY > 0 ? 1.15f : 0.87f;
        float newZoom = juce::jlimit(0.1f, 10.0f, hZoom * zoomFactor);
        DBG("  H-zoom: " << hZoom << " -> " << newZoom);
        hZoom = newZoom;
        repaint();
    }
    else if (event.mods.isCtrlDown() || event.mods.isCommandDown())
    {
        // Vertical zoom with Ctrl/Cmd + wheel
        float zoomFactor = wheel.deltaY > 0 ? 1.15f : 0.87f;
        float newZoom = juce::jlimit(0.5f, 4.0f, vZoom * zoomFactor);
        DBG("  V-zoom: " << vZoom << " -> " << newZoom);
        vZoom = newZoom;
        repaint();
    }
    else
    {
        // Scroll vertically with wheel (horizontal with deltaX if available)
        if (std::abs(wheel.deltaX) > 0.001f)
        {
            scrollX -= wheel.deltaX * 2.0;
            scrollX = juce::jmax(0.0, scrollX);
        }
        
        // Vertical scroll - higher deltaY = scroll up (see higher notes)
        int scrollAmount = (int)(wheel.deltaY * 8);
        scrollY = juce::jlimit(minNote, maxNote, scrollY - scrollAmount);
        
        DBG("  Scroll: scrollX=" << scrollX << " scrollY=" << scrollY);
        repaint();
    }
}

void PianoRollComponent::mouseUp(const juce::MouseEvent& /*event*/)
{
    isDragging = false;
}

void PianoRollComponent::mouseExit(const juce::MouseEvent& /*event*/)
{
    if (hoveredNote != nullptr)
    {
        hoveredNote = nullptr;
        listeners.call(&Listener::pianoRollNoteHovered, nullptr);
        repaint();
    }
    isDragging = false;
}

//==============================================================================
void PianoRollComponent::transportStateChanged(mmg::AudioEngine::TransportState /*newState*/)
{
    // Handled by timer
}

void PianoRollComponent::playbackPositionChanged(double positionSeconds)
{
    playheadPosition = positionSeconds;
    
    juce::MessageManager::callAsync([this]()
    {
        repaint();
    });
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
void PianoRollComponent::addListener(Listener* listener)
{
    listeners.add(listener);
}

void PianoRollComponent::removeListener(Listener* listener)
{
    listeners.remove(listener);
}
