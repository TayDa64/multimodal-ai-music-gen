/*
  ==============================================================================

    PianoRollComponent.cpp
    
    Implementation of the piano roll visualization.

  ==============================================================================
*/

#include "PianoRollComponent.h"
#include "../Theme/ColourScheme.h"

#include <limits>
#include <numeric>

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
    trackSelector.setColour(juce::ComboBox::backgroundColourId, AppColours::surfaceAlt.withAlpha(0.55f));
    trackSelector.setColour(juce::ComboBox::textColourId, AppColours::textPrimary.withAlpha(0.70f));
    trackSelector.setColour(juce::ComboBox::outlineColourId, AppColours::border.withAlpha(0.45f));
    trackSelector.setColour(juce::ComboBox::arrowColourId, AppColours::textSecondary.withAlpha(0.70f));
    trackSelector.onChange = [this] { 
        soloedTrack = trackSelector.getSelectedId() - 2; // ID 1 = All, ID 2 = Track 0...
        if (soloedTrack < -1) soloedTrack = -1;
        if (soloedTrack >= 0)
            lastAuditionTrackIndex = soloedTrack;
        listeners.call(&PianoRollComponent::Listener::pianoRollSoloTrackChanged, soloedTrack);
        repaint(); 
    };
    
    DBG("PianoRollComponent created");
}

PianoRollComponent::~PianoRollComponent()
{
    if (projectState)
        projectState->removeStateListener(this);
        
    audioEngine.removeListener(this);
    stopTimer();
}

//==============================================================================
void PianoRollComponent::setProjectState(Project::ProjectState* state)
{
    if (projectState)
        projectState->removeStateListener(this);
        
    projectState = state;
    
    if (projectState)
    {
        projectState->addStateListener(this);
        syncNotesFromState();
    }
}

void PianoRollComponent::syncNotesFromState()
{
    if (!projectState)
        return;
    
    notes.clear();
    // Do NOT clear selection here, as it breaks drag operations.
    // Instead, we validate selection at the end.
    
    auto notesNode = projectState->getState().getChildWithName(Project::IDs::NOTES);
    if (!notesNode.isValid())
        return;
    
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
    
    // In embedded mode, auto-zoom to fit the notes for this track ONLY on initial load
    // Don't auto-zoom when user adds/modifies notes (they may have zoomed in to edit)
    if (embeddedMode && !hasInitialZoom)
    {
        zoomToFit();
        hasInitialZoom = true;
    }
    
    repaint();
}

//==============================================================================
void PianoRollComponent::loadMidiFile(const juce::File& midiFile)
{
    DBG("PianoRollComponent::loadMidiFile - projectState=" << juce::String::toHexString((juce::pointer_sized_int)projectState));
    
    // Reset initial zoom flag so we zoom to fit on new file
    hasInitialZoom = false;
    
    // Legacy support - import into project state if available
    if (projectState)
    {
        DBG("  Calling projectState->importMidiFile...");
        projectState->importMidiFile(midiFile);
        DBG("  Import complete, checking notes...");
        auto notesNode = projectState->getState().getChildWithName(Project::IDs::NOTES);
        DBG("  NOTES node has " << notesNode.getNumChildren() << " children after import");
        // syncNotesFromState will be called via listener callback
    }
    else
    {
        DBG("  WARNING: projectState is NULL, using fallback visualization-only mode!");
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

void PianoRollComponent::setScrollX(double scrollSeconds)
{
    scrollX = juce::jmax(0.0, scrollSeconds);
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
    
    float availableWidth = (float)(getWidth() - getEffectiveKeyWidth());
    if (availableWidth > 0)
    {
        float targetPixelsPerSecond = availableWidth / (float)totalDuration;
        hZoom = juce::jlimit(0.1f, 10.0f, targetPixelsPerSecond / 100.0f);
    }
    
    int minNoteFound = 127, maxNoteFound = 0;
    for (const auto& note : notes)
    {
        // When soloed to a track, only consider notes from that track
        if (soloedTrack >= 0 && note.trackIndex != soloedTrack)
            continue;
            
        minNoteFound = juce::jmin(minNoteFound, note.noteNumber);
        maxNoteFound = juce::jmax(maxNoteFound, note.noteNumber);
    }
    
    if (minNoteFound <= maxNoteFound)
    {
        scrollY = (minNoteFound + maxNoteFound) / 2;
        
        // In embedded mode, auto-fit vertical zoom to show all notes
        if (embeddedMode && getHeight() > 0)
        {
            int noteRange = maxNoteFound - minNoteFound + 1;
            noteRange = juce::jmax(noteRange, 12);  // Minimum 1 octave visible
            
            float availableHeight = (float)getHeight();
            float targetNoteHeight = availableHeight / (float)noteRange;
            vZoom = juce::jlimit(0.3f, 4.0f, targetNoteHeight / (float)whiteKeyHeight);
        }
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
    if (soloedTrack >= 0)
        lastAuditionTrackIndex = soloedTrack;
    repaint();
}

void PianoRollComponent::setAuditionTrackIndex(int trackIndex)
{
    if (trackIndex < 0)
        return;

    // Only affects key audition when we're not explicitly soloing a track.
    lastAuditionTrackIndex = trackIndex;
    repaint();
}

void PianoRollComponent::setDrumMode(bool enabled)
{
    if (drumMode == enabled)
        return;
    drumMode = enabled;
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
    drawTimeRuler(g);   // Bar:Beat timeline ruler at top
    drawGridLines(g);
    drawLoopRegion(g);  // Draw loop region behind notes
    drawNotes(g);
    
    if (isSelecting)
        drawSelectionRect(g);
        
    drawPlayhead(g);
    
    // Only draw piano keys when NOT in embedded mode
    if (!embeddedMode)
        drawPianoKeys(g);
    
    if (hoveredNote != nullptr)
        drawNoteTooltip(g);
}

void PianoRollComponent::drawBackground(juce::Graphics& g)
{
    g.fillAll(AppColours::background);
    
    int keyWidth = getEffectiveKeyWidth();
    int rulerHeight = getEffectiveRulerHeight();
    auto noteArea = getLocalBounds().withTrimmedLeft(keyWidth).withTrimmedTop(rulerHeight);
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

void PianoRollComponent::drawTimeRuler(juce::Graphics& g)
{
    int keyWidth = getEffectiveKeyWidth();
    int rulerHeight = getEffectiveRulerHeight();
    
    // Skip drawing ruler in embedded mode - ArrangementView has its own timeline ruler
    if (rulerHeight <= 0)
        return;
    
    auto rulerBounds = getLocalBounds().removeFromTop(rulerHeight);
    
    // Background
    g.setColour(AppColours::surface.darker(0.1f));
    g.fillRect(rulerBounds);
    
    // Border at bottom
    g.setColour(AppColours::border);
    g.drawHorizontalLine(rulerBounds.getBottom() - 1, (float)rulerBounds.getX(), (float)rulerBounds.getRight());
    
    const double secondsPerBeat = getSecondsPerBeat();
    if (secondsPerBeat <= 0.0)
        return;

    const int gridDiv = getGridDivisionsPerBeat();

    // Grid label (e.g. 1/4, 1/8, 1/16) so users can see the current snap resolution.
    const int denom = 4 * juce::jmax(1, gridDiv);
    const juce::String gridLabel = "Grid: 1/" + juce::String(denom);
    {
        g.setColour(AppColours::textSecondary.withAlpha(0.85f));
        g.setFont(11.0f);
        auto labelBounds = rulerBounds.withTrimmedLeft(keyWidth + 6).withTrimmedRight(6);
        g.drawText(gridLabel, labelBounds, juce::Justification::centredRight);
    }

    const float pixelsPerBeat = (float)(secondsPerBeat * (double)(100.0f * hZoom));
    const bool showBeatNumbers = pixelsPerBeat >= 65.0f;
    
    // Calculate visible time range
    double startTime = juce::jmax(0.0, scrollX);
    double endTime = scrollX + getWidth() / (100.0f * hZoom);
    
    // Draw bar/beat/subdivision markers (iterate by integer subdivision index to avoid float drift)
    g.setFont(10.0f);

    const double startBeats = startTime / secondsPerBeat;
    const double endBeats = endTime / secondsPerBeat;
    const int startSub = juce::jmax(0, (int)std::floor(startBeats * (double)gridDiv) - gridDiv * 4);
    const int endSub = (int)std::ceil(endBeats * (double)gridDiv) + gridDiv * 4;

    const int barSubDiv = gridDiv * 4;
    const float pixelsPerSubdivision = (gridDiv > 0) ? (pixelsPerBeat / (float)gridDiv) : pixelsPerBeat;
    const bool showFractionLabels = (pixelsPerSubdivision >= 22.0f);

    // Keep bar/beat/fraction labels from colliding.
    const int labelBandH = juce::jmax(1, rulerHeight / 2);
    const int fractionLabelY = rulerBounds.getY();
    const int beatLabelY = rulerBounds.getY() + labelBandH;

    const juce::Font barFont(13.0f, juce::Font::bold); // ~3px larger than beat numbers
    const juce::Font beatFont(10.0f);
    const juce::Font fracFont(9.0f);

    // Avoid too-dense fraction labels when grid is 1/16+.
    const int minSubLabelStep = (gridDiv >= 4) ? juce::jmax(1, gridDiv / 2) : 1; // cap at 1/8 in 4/4
    const int computedLabelStep = (pixelsPerSubdivision > 0.0f)
        ? juce::jmax(1, (int)std::ceil(20.0f / pixelsPerSubdivision))
        : 1;
    const int subLabelStep = juce::jmin(barSubDiv, juce::jmax(minSubLabelStep, computedLabelStep));

    auto formatBarFraction = [barSubDiv](int posInBar) -> juce::String
    {
        if (posInBar <= 0 || barSubDiv <= 0)
            return {};

        // Reduce to canonical fraction (e.g. 8/16 -> 1/2) so labels remain consistent.
        const int gcd = juce::jmax(1, std::gcd(posInBar, barSubDiv));
        const int num = posInBar / gcd;
        const int den = barSubDiv / gcd;
        return juce::String(num) + "/" + juce::String(den);
    };

    float lastFractionLabelX = -1.0e9f;
    auto canDrawFractionLabelAt = [&lastFractionLabelX](float x) -> bool
    {
        // Simple spacing guard to prevent label overlaps at high zoom.
        constexpr float minLabelSpacingPx = 26.0f;
        if (x - lastFractionLabelX < minLabelSpacingPx)
            return false;
        lastFractionLabelX = x;
        return true;
    };

    for (int subIndex = startSub; subIndex <= endSub; ++subIndex)
    {
        const double time = ((double)subIndex / (double)gridDiv) * secondsPerBeat;
        float x = timeToX(time);
        if (x < keyWidth || x > getWidth())
            continue;

        const bool isBar = (subIndex % (gridDiv * 4)) == 0;
        const bool isBeat = (subIndex % gridDiv) == 0;
        
        if (isBar)
        {
            // Bar marker - tall line with bar number
            g.setColour(AppColours::textPrimary);
            g.drawVerticalLine((int)x, (float)rulerBounds.getY() + 10, (float)rulerBounds.getBottom());
            
            // Bar number
            const int barNumber = subIndex / (gridDiv * 4);
            g.setFont(barFont);
            g.setColour(AppColours::textPrimary.withAlpha(0.95f));

            g.drawText(juce::String(barNumber),
                       (int)x + 3, fractionLabelY, 30, labelBandH,
                       juce::Justification::centredLeft);
        }
        else if (isBeat)
        {
            // Beat marker - short line
            g.setColour(AppColours::textSecondary.withAlpha(0.5f));
            g.drawVerticalLine((int)x, (float)rulerBounds.getBottom() - 6, (float)rulerBounds.getBottom());

            if (showBeatNumbers)
            {
                const int beatIndex = (subIndex / gridDiv) % 4; // 0..3 in 4/4
                const juce::String beatText = juce::String(beatIndex + 1);
                g.setColour(AppColours::textSecondary.withAlpha(0.85f));
                g.setFont(beatFont);
                g.drawText(beatText, (int)x + 2, beatLabelY, 16, rulerHeight - labelBandH,
                           juce::Justification::centredLeft);
            }

            // Optional fraction labels inside the bar for extra clarity (1/4, 1/2, 3/4...).
            const int posInBar = (barSubDiv > 0) ? (subIndex % barSubDiv) : 0;
            // When beat numbers are shown, fractions at beat boundaries are redundant and tend to overlap.
            if (showFractionLabels && !showBeatNumbers && posInBar > 0 && (posInBar % subLabelStep) == 0)
            {
                const auto frac = formatBarFraction(posInBar);
                if (frac.isNotEmpty() && canDrawFractionLabelAt(x))
                {
                    g.setColour(AppColours::textSecondary.withAlpha(0.60f));
                    g.setFont(fracFont);
                    g.drawText(frac, (int)x + 2, fractionLabelY, 34, labelBandH,
                               juce::Justification::centredLeft);
                }
            }
        }
        else
        {
            // Subdivision tick (only visible when zoomed in enough)
            g.setColour(AppColours::textSecondary.withAlpha(0.25f));
            g.drawVerticalLine((int)x, (float)rulerBounds.getBottom() - 3, (float)rulerBounds.getBottom());

            const int posInBar = (barSubDiv > 0) ? (subIndex % barSubDiv) : 0;
            if (showFractionLabels && posInBar > 0 && (posInBar % subLabelStep) == 0)
            {
                const auto frac = formatBarFraction(posInBar);
                if (frac.isNotEmpty() && canDrawFractionLabelAt(x))
                {
                    g.setColour(AppColours::textSecondary.withAlpha(0.50f));
                    g.setFont(fracFont);
                    g.drawText(frac, (int)x + 2, fractionLabelY, 34, labelBandH,
                               juce::Justification::centredLeft);
                }
            }
        }
    }
    
    // Draw current position in bar:beat format at left side
    if (!embeddedMode)
    {
        juce::String timeStr = formatBarBeat(playheadPosition);
        g.setColour(AppColours::accent);
        g.setFont(11.0f);
        auto textBounds = juce::Rectangle<int>(rulerBounds.getX(), rulerBounds.getY(), keyWidth, rulerHeight);
        g.fillRect(textBounds);
        g.setColour(AppColours::textPrimary);
        g.drawText(timeStr, textBounds.reduced(4, 0), juce::Justification::centred);
    }
}

void PianoRollComponent::drawPianoKeys(juce::Graphics& g)
{
    int rulerHeight = getEffectiveRulerHeight();
    auto keyArea = getLocalBounds().removeFromLeft(pianoKeyWidth).withTrimmedTop(rulerHeight);
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
        if (drumMode || noteName == 0 || vZoom >= 1.5f)
        {
            g.setColour(isBlackKey ? juce::Colours::white : juce::Colours::black);
            g.setFont(juce::jmin(10.0f, noteHeight - 2));

            juce::String label;
            if (drumMode)
            {
                // General MIDI drum map (common subset)
                switch (noteNum)
                {
                    case 35: label = "Acoustic Bass Drum"; break;
                    case 36: label = "Kick"; break;
                    case 38: label = "Snare"; break;
                    case 40: label = "Snare (Alt)"; break;
                    case 41: label = "Low Tom"; break;
                    case 43: label = "High Floor Tom"; break;
                    case 45: label = "Low Tom (Alt)"; break;
                    case 47: label = "Mid Tom"; break;
                    case 48: label = "Hi Mid Tom"; break;
                    case 50: label = "High Tom"; break;
                    case 42: label = "Closed Hat"; break;
                    case 44: label = "Pedal Hat"; break;
                    case 46: label = "Open Hat"; break;
                    case 49: label = "Crash"; break;
                    case 51: label = "Ride"; break;
                    case 52: label = "China"; break;
                    case 55: label = "Splash"; break;
                    case 57: label = "Crash 2"; break;
                    case 59: label = "Ride 2"; break;
                    case 37: label = "Rimshot"; break;
                    case 39: label = "Clap"; break;
                    case 54: label = "Tambourine"; break;
                    case 56: label = "Cowbell"; break;
                    case 60: label = "Hi Bongo"; break;
                    case 61: label = "Low Bongo"; break;
                    case 62: label = "Mute Conga"; break;
                    case 63: label = "Open Conga"; break;
                    case 64: label = "Low Conga"; break;
                    default: label = MidiNoteEvent::getNoteName(noteNum); break;
                }
            }
            else
            {
                label = MidiNoteEvent::getNoteName(noteNum);
            }
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
    // In embedded mode, ArrangementView draws the unified grid lines
    // to ensure perfect alignment between timeline ruler and track lanes
    if (embeddedMode)
        return;
    
    int keyWidth = getEffectiveKeyWidth();
    auto noteArea = getLocalBounds().withTrimmedLeft(keyWidth);
    const double secondsPerBeat = getSecondsPerBeat();
    if (secondsPerBeat <= 0.0)
        return;

    float pixelsPerSecond = 100.0f * hZoom;
    const int gridDiv = getGridDivisionsPerBeat();
    
    double startTime = juce::jmax(0.0, scrollX);
    double endTime = scrollX + noteArea.getWidth() / pixelsPerSecond;
    
    g.setColour(AppColours::border.withAlpha(0.3f));

    const double startBeats = startTime / secondsPerBeat;
    const double endBeats = endTime / secondsPerBeat;
    const int startSub = juce::jmax(0, (int)std::floor(startBeats * (double)gridDiv) - gridDiv * 2);
    const int endSub = (int)std::ceil(endBeats * (double)gridDiv) + gridDiv * 2;

    for (int subIndex = startSub; subIndex <= endSub; ++subIndex)
    {
        const double time = ((double)subIndex / (double)gridDiv) * secondsPerBeat;
        float x = timeToX(time);
        if (x >= keyWidth && x < getWidth())
        {
            const bool isBar = (subIndex % (gridDiv * 4)) == 0;
            const bool isBeat = (subIndex % gridDiv) == 0;
            if (isBar)
            {
                g.setColour(AppColours::border.withAlpha(0.6f));
                g.drawVerticalLine((int)x, 0.0f, (float)getHeight());
            }
            else if (isBeat)
            {
                g.setColour(AppColours::border.withAlpha(0.25f));
                g.drawVerticalLine((int)x, 0.0f, (float)getHeight());
            }
            else
            {
                g.setColour(AppColours::border.withAlpha(0.12f));
                g.drawVerticalLine((int)x, 0.0f, (float)getHeight());
            }
        }
    }
}

//==============================================================================
double PianoRollComponent::getSecondsPerBeat() const
{
    if (currentBPM <= 0)
        return 0.0;
    return 60.0 / (double)currentBPM;
}

int PianoRollComponent::getGridDivisionsPerBeat() const
{
    const double secondsPerBeat = getSecondsPerBeat();
    if (secondsPerBeat <= 0.0)
        return 1;

    const float pixelsPerSecond = 100.0f * hZoom;
    const float pixelsPerBeat = (float)(secondsPerBeat * (double)pixelsPerSecond);

    // 1 = quarter notes, 2 = eighth notes, 4 = sixteenth notes
    // Lower thresholds so 1/16 becomes reachable without extreme zoom.
    if (pixelsPerBeat >= 90.0f) return 4;
    if (pixelsPerBeat >= 50.0f)  return 2;
    return 1;
}

double PianoRollComponent::snapBeatsToGrid(double beats) const
{
    const int gridDiv = getGridDivisionsPerBeat();
    if (gridDiv <= 1)
        return std::round(beats);
    return std::round(beats * (double)gridDiv) / (double)gridDiv;
}

void PianoRollComponent::drawLoopRegion(juce::Graphics& g)
{
    if (!hasLoopRegion())
        return;
    
    float startX = timeToX(loopRegionStart);
    float endX = timeToX(loopRegionEnd);
    
    // Clamp to visible area
    int keyWidth = getEffectiveKeyWidth();
    startX = juce::jmax(startX, (float)keyWidth);
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
    
    int keyWidth = getEffectiveKeyWidth();
    
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
        
        if (endX < keyWidth || x > getWidth()) continue;
        if (y + noteHeight < 0 || y > getHeight()) continue;
        
        if (x < keyWidth)
        {
            width -= (keyWidth - x);
            x = (float)keyWidth;
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
    if (x >= getEffectiveKeyWidth() && x <= getWidth())
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
    
    // Build tooltip with note info and bar:beat position
    juce::String text = MidiNoteEvent::getNoteName(hoveredNote->noteNumber);
    text += " | Vel: " + juce::String(hoveredNote->velocity);
    text += " | " + formatBarBeat(hoveredNote->startTime);
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
    // In embedded mode, parent viewport handles scrolling, so don't subtract scrollX
    double effectiveScroll = embeddedMode ? 0.0 : scrollX;
    return (float)getEffectiveKeyWidth() + (float)((timeSeconds - effectiveScroll) * 100.0 * hZoom);
}

double PianoRollComponent::xToTime(float x) const
{
    // In embedded mode, parent viewport handles scrolling, so don't add scrollX
    double effectiveScroll = embeddedMode ? 0.0 : scrollX;
    return effectiveScroll + (x - getEffectiveKeyWidth()) / (100.0 * hZoom);
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

//==============================================================================
// Time formatting helpers
void PianoRollComponent::timeToBarBeat(double timeSeconds, int& bar, int& beat, int& tick) const
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

juce::String PianoRollComponent::formatBarBeat(double timeSeconds) const
{
    int bar, beat, tick;
    timeToBarBeat(timeSeconds, bar, beat, tick);
    
    // Format as "Bar.Beat.Tick" like Cubase/DAWs
    return juce::String(bar) + "." + juce::String(beat) + "." + juce::String(tick).paddedLeft('0', 3);
}

MidiNoteEvent* PianoRollComponent::getNoteAt(juce::Point<float> position)
{
    if (position.x < getEffectiveKeyWidth()) return nullptr;
    float noteHeight = whiteKeyHeight * vZoom;
    
    for (auto& note : notes)
    {
        if (soloedTrack >= 0 && note.trackIndex != soloedTrack) continue;
        if (!isTrackVisible(note.trackIndex)) continue;
        
        float x = timeToX(note.startTime);
        float endX = timeToX(note.endTime);
        float y = noteToY(note.noteNumber);
        
        juce::Rectangle<float> noteRect(x, y, endX - x, noteHeight);
        // Expand hit area slightly (esp. horizontally) so edge resize is easier to grab.
        if (noteRect.expanded(6.0f, 2.0f).contains(position))
            return &note;
    }
    return nullptr;
}

juce::ValueTree PianoRollComponent::resolveNoteStateNode(const MidiNoteEvent& note) const
{
    if (projectState == nullptr)
        return {};

    auto notesNode = projectState->getState().getChildWithName(Project::IDs::NOTES);
    if (!notesNode.isValid())
        return {};

    const double secondsPerBeat = getSecondsPerBeat();
    if (secondsPerBeat <= 0.0)
        return {};

    const double targetStartBeats = note.startTime / secondsPerBeat;
    const double targetLengthBeats = note.getDuration() / secondsPerBeat;

    // First try a tight match.
    constexpr double tolBeats = 1.0e-3;
    for (const auto& child : notesNode)
    {
        if (!child.hasType(Project::IDs::NOTE))
            continue;

        const int childNote = (int)child.getProperty(Project::IDs::noteNumber);
        const int childTrack = (int)child.getProperty(Project::IDs::channel);
        if (childNote != note.noteNumber || childTrack != note.trackIndex)
            continue;

        const double childStart = (double)child.getProperty(Project::IDs::start);
        const double childLength = (double)child.getProperty(Project::IDs::length);

        if (std::abs(childStart - targetStartBeats) <= tolBeats && std::abs(childLength - targetLengthBeats) <= tolBeats)
            return child;
    }

    // Fallback: pick the closest matching note by start/length.
    double bestScore = std::numeric_limits<double>::infinity();
    juce::ValueTree best;
    for (const auto& child : notesNode)
    {
        if (!child.hasType(Project::IDs::NOTE))
            continue;

        const int childNote = (int)child.getProperty(Project::IDs::noteNumber);
        const int childTrack = (int)child.getProperty(Project::IDs::channel);
        if (childNote != note.noteNumber || childTrack != note.trackIndex)
            continue;

        const double childStart = (double)child.getProperty(Project::IDs::start);
        const double childLength = (double)child.getProperty(Project::IDs::length);

        const double score = std::abs(childStart - targetStartBeats) + std::abs(childLength - targetLengthBeats);
        if (score < bestScore)
        {
            bestScore = score;
            best = child;
        }
    }

    // Only accept the fallback if it's reasonably close.
    if (best.isValid() && bestScore <= 0.05)
        return best;

    return {};
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
    {
        const int selectorW = 160;
        const int selectorH = 24;
        const int margin = 8;

        const int rulerHeight = getEffectiveRulerHeight();
        const int keyWidth = getEffectiveKeyWidth();

        const int baseX = keyWidth + margin;
        const int minX = baseX;
        const int maxX = juce::jmax(minX, getWidth() - selectorW - margin);

        int x = baseX;
        if (trackSelectorUserX >= 0)
            x = baseX + trackSelectorUserX;
        x = juce::jlimit(minX, maxX, x);

        const int y = juce::jmax(margin, (rulerHeight - selectorH) / 2);
        trackSelector.setBounds(x, y, selectorW, selectorH);
    }
}

void PianoRollComponent::mouseDown(const juce::MouseEvent& event)
{
    grabKeyboardFocus();
    lastMousePos = event.position;
    dragStartPos = event.position;

    if (!embeddedMode && event.mods.isRightButtonDown())
    {
        const int rulerHeight = getEffectiveRulerHeight();
        if (event.y <= rulerHeight && trackSelector.getBounds().contains(event.position.toInt()))
        {
            isDraggingTrackSelector = true;
            trackSelectorDragStartX = event.x;
            trackSelectorDragStartUserX = trackSelectorUserX;
            if (trackSelectorDragStartUserX < 0)
                trackSelectorDragStartUserX = 0;
            return;
        }
    }
    
    if (event.mods.isLeftButtonDown())
    {
        clickStartTime = juce::Time::currentTimeMillis();

        // Piano keys area: audition the clicked note.
        if (event.x <= getEffectiveKeyWidth())
        {
            const int noteNum = yToNote(event.position.y);
            const int targetTrack = (soloedTrack >= 0) ? soloedTrack : lastAuditionTrackIndex;
            audioEngine.playNote(targetTrack, noteNum, 0.85f);
            return;
        }
        
        auto* note = getNoteAt(event.position);
        
        if (note)
        {
            // Ensure we have a valid state node for editing.
            if (projectState != nullptr && !note->stateNode.isValid())
            {
                auto resolved = resolveNoteStateNode(*note);
                if (resolved.isValid())
                    note->stateNode = resolved;
            }

            // Play the note for feedback
            audioEngine.playNote(note->trackIndex, note->noteNumber, note->velocity / 127.0f);
            lastAuditionTrackIndex = note->trackIndex;

            // Clicked on a note
            if (event.mods.isShiftDown())
            {
                // Toggle selection
                if (note->stateNode.isValid())
                {
                    if (selectedNotes.contains(note->stateNode))
                        selectedNotes.removeFirstMatchingValue(note->stateNode);
                    else
                        selectedNotes.add(note->stateNode);
                }
            }
            else
            {
                // Select only this note (unless already selected)
                if (note->stateNode.isValid())
                {
                    if (!selectedNotes.contains(note->stateNode))
                    {
                        selectedNotes.clear();
                        selectedNotes.add(note->stateNode);
                    }
                }
            }
            
            // Check for resize (right edge)
            const float startX = timeToX(note->startTime);
            const float endX = timeToX(note->endTime);
            const float widthPx = endX - startX;
            const float edgeGrabPx = juce::jlimit(6.0f, 14.0f, widthPx * 0.25f);
            if (event.position.x >= (endX - edgeGrabPx))
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
            
            if (projectState && !selectedNotes.isEmpty())
            {
                projectState->getUndoManager().beginNewTransaction(isResizing ? "Resize Note" : "Move Note");

                // Snapshot note state at drag start so snapped movement/resizing can accumulate
                // (incremental deltas + snapping can otherwise get "stuck" and never cross a grid threshold).
                dragNoteSnapshots.clear();
                dragNoteSnapshots.ensureStorageAllocated(selectedNotes.size());
                for (const auto& node : selectedNotes)
                {
                    if (!node.isValid())
                        continue;
                    DragNoteSnapshot snap;
                    snap.node = node;
                    snap.startBeats = (double)node.getProperty(Project::IDs::start);
                    snap.lengthBeats = (double)node.getProperty(Project::IDs::length);
                    snap.noteNumber = (int)node.getProperty(Project::IDs::noteNumber);
                    dragNoteSnapshots.add(snap);
                }
            }
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
    if (isDraggingTrackSelector)
    {
        const int deltaX = event.x - trackSelectorDragStartX;
        trackSelectorUserX = juce::jmax(0, trackSelectorDragStartUserX + deltaX);
        resized();
        repaint();
        return;
    }

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
    
    const double secondsPerBeat = getSecondsPerBeat();
    if (secondsPerBeat <= 0.0)
        return;

    auto updateCachedNoteFromState = [this, secondsPerBeat](const juce::ValueTree& noteNode)
    {
        if (!noteNode.isValid())
            return;

        const int newNoteNumber = (int)noteNode.getProperty(Project::IDs::noteNumber);
        const int newTrackIndex = (int)noteNode.getProperty(Project::IDs::channel);
        const double startBeats = (double)noteNode.getProperty(Project::IDs::start);
        const double lengthBeats = (double)noteNode.getProperty(Project::IDs::length);

        for (auto& cached : notes)
        {
            if (cached.stateNode == noteNode)
            {
                cached.noteNumber = newNoteNumber;
                cached.channel = newTrackIndex;
                cached.trackIndex = newTrackIndex;
                cached.startTime = startBeats * secondsPerBeat;
                cached.endTime = (startBeats + lengthBeats) * secondsPerBeat;
                break;
            }
        }
    };
    
    if (isMoving)
    {
        const float deltaX = event.position.x - dragStartPos.x;
        const double deltaTimeSeconds = deltaX / (100.0 * hZoom);
        const double deltaBeats = deltaTimeSeconds / secondsPerBeat;
        const int deltaNote = yToNote(event.position.y) - yToNote(dragStartPos.y);

        // Prefer snapshots if available (snap-friendly). Fallback to selectedNotes if not.
        if (!dragNoteSnapshots.isEmpty())
        {
            for (const auto& snap : dragNoteSnapshots)
            {
                auto node = snap.node;
                if (!node.isValid())
                    continue;

                double newStart = snap.startBeats + deltaBeats;
                int newNoteNum = snap.noteNumber + deltaNote;

                newStart = juce::jmax(0.0, newStart);
                if (!event.mods.isAltDown())
                    newStart = snapBeatsToGrid(newStart);

                newNoteNum = juce::jlimit(0, 127, newNoteNum);

                projectState->moveNote(node, newStart, newNoteNum);
                updateCachedNoteFromState(node);
            }
        }
        else
        {
            for (auto& node : selectedNotes)
            {
                if (!node.isValid())
                    continue;
                const double start = (double)node.getProperty(Project::IDs::start);
                const int noteNum = (int)node.getProperty(Project::IDs::noteNumber);

                double newStart = juce::jmax(0.0, start + deltaBeats);
                if (!event.mods.isAltDown())
                    newStart = snapBeatsToGrid(newStart);

                const int newNoteNum = juce::jlimit(0, 127, noteNum + deltaNote);
                projectState->moveNote(node, newStart, newNoteNum);
                updateCachedNoteFromState(node);
            }
        }
        repaint();
    }
    else if (isResizing)
    {
        const float deltaX = event.position.x - dragStartPos.x;
        const double deltaTimeSeconds = deltaX / (100.0 * hZoom);
        const double deltaBeats = deltaTimeSeconds / secondsPerBeat;

        const int gridDiv = getGridDivisionsPerBeat();
        const double minStepBeats = (gridDiv > 0) ? (1.0 / (double)gridDiv) : 0.1;

        if (!dragNoteSnapshots.isEmpty())
        {
            for (const auto& snap : dragNoteSnapshots)
            {
                auto node = snap.node;
                if (!node.isValid())
                    continue;

                double newLen = snap.lengthBeats + deltaBeats;

                if (!event.mods.isAltDown())
                {
                    newLen = snapBeatsToGrid(newLen);
                    newLen = juce::jmax(minStepBeats, newLen);
                }
                else
                {
                    newLen = juce::jmax(0.1, newLen);
                }

                projectState->resizeNote(node, newLen);
                updateCachedNoteFromState(node);
            }
        }
        else
        {
            for (auto& node : selectedNotes)
            {
                if (!node.isValid())
                    continue;

                const double currentLen = (double)node.getProperty(Project::IDs::length);
                double newLen = currentLen + deltaBeats;

                if (!event.mods.isAltDown())
                {
                    newLen = snapBeatsToGrid(newLen);
                    newLen = juce::jmax(minStepBeats, newLen);
                }
                else
                {
                    newLen = juce::jmax(0.1, newLen);
                }

                projectState->resizeNote(node, newLen);
                updateCachedNoteFromState(node);
            }
        }
        repaint();
    }
    else if (isSelecting)
    {
        selectionRect.setBounds(
            juce::jmin((int)dragStartPos.x, event.x),
            juce::jmin((int)dragStartPos.y, event.y),
            std::abs(event.x - (int)dragStartPos.x),
            std::abs(event.y - (int)dragStartPos.y)
        );
        
        // Update selection based on rect - respecting track filter
        selectedNotes.clear();
        for (auto& note : notes)
        {
            // Skip notes from other tracks when in solo/embedded mode
            if (soloedTrack >= 0 && note.trackIndex != soloedTrack) continue;
            if (!isTrackVisible(note.trackIndex)) continue;
            
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
    if (isDraggingTrackSelector)
    {
        isDraggingTrackSelector = false;
        return;
    }

    if (isSelecting)
    {
        isSelecting = false;
        repaint();
    }
    else if (!isMoving && !isResizing && !isDragging)
    {
        // Simple click on empty space -> Seek
        if (event.x > getEffectiveKeyWidth() && selectedNotes.isEmpty())
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
    if (event.x <= getEffectiveKeyWidth()) return;
    
    // Only allow adding notes if a specific track is selected (to know where to put it)
    // Or default to track 0 if "All" is selected?
    // Better: Default to track 0, or the last selected note's track.
    int targetTrack = (soloedTrack >= 0) ? soloedTrack : lastAuditionTrackIndex;
    
    double time = xToTime(event.position.x);
    int noteNum = yToNote(event.position.y);
    
    const double secondsPerBeat = getSecondsPerBeat();
    if (secondsPerBeat <= 0.0)
        return;
    double beat = time / secondsPerBeat;

    // Snap to grid (adaptive, up to 1/16)
    beat = snapBeatsToGrid(beat);
    
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
            // Copy nodes to a local array first, as deletion triggers syncNotesFromState
            // which can invalidate the selectedNotes during iteration
            juce::Array<juce::ValueTree> nodesToDelete;
            for (auto& note : selectedNotes)
            {
                if (note.isValid())
                    nodesToDelete.add(note);
            }
            
            // Clear selection BEFORE deletion to prevent accessing invalid nodes
            selectedNotes.clear();
            
            projectState->getUndoManager().beginNewTransaction("Delete Notes");
            
            // Use batch delete for better performance
            projectState->deleteNotes(nodesToDelete);
            
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
        const float startX = timeToX(note->startTime);
        const float endX = timeToX(note->endTime);
        const float widthPx = endX - startX;
        const float edgeGrabPx = juce::jlimit(6.0f, 14.0f, widthPx * 0.25f);
        if (event.position.x >= (endX - edgeGrabPx))
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
    if (event.mods.isCtrlDown() || event.mods.isCommandDown())
    {
        // Ctrl+scroll = horizontal zoom (time axis) - consistent with ArrangementView
        float zoomFactor = wheel.deltaY > 0 ? 1.15f : 0.87f;
        float newZoom = juce::jlimit(0.1f, 10.0f, hZoom * zoomFactor);
        
        if (embeddedMode)
        {
            // In embedded mode, request parent to handle zoom for synchronization
            listeners.call(&PianoRollComponent::Listener::pianoRollHorizontalZoomRequested, newZoom);
        }
        else
        {
            hZoom = newZoom;
            repaint();
        }
    }
    else if (event.mods.isShiftDown())
    {
        // Shift+scroll = vertical zoom (note height)
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
