/*
  ==============================================================================

    TimelineComponent.cpp
    
    Implementation of the visual timeline component.

  ==============================================================================
*/

#include "TimelineComponent.h"
#include "Theme/ColourScheme.h"

//==============================================================================
TimelineComponent::TimelineComponent(AppState& state, mmg::AudioEngine& engine)
    : appState(state),
      audioEngine(engine)
{
    audioEngine.addListener(this);
    currentBPM = appState.getBPM();
    startTimerHz(30);  // Update at 30fps
}

TimelineComponent::~TimelineComponent()
{
    audioEngine.removeListener(this);
    stopTimer();
}

//==============================================================================
void TimelineComponent::setSections(const juce::Array<TimelineSection>& newSections)
{
    sections = newSections;
    
    // Calculate total duration from sections
    if (!sections.isEmpty())
    {
        totalDuration = 0.0;
        for (const auto& section : sections)
            totalDuration = juce::jmax(totalDuration, section.endTime);
    }
    
    repaint();
}

void TimelineComponent::clearSections()
{
    sections.clear();
    repaint();
}

void TimelineComponent::setTotalDuration(double durationSeconds)
{
    totalDuration = juce::jmax(1.0, durationSeconds);
    repaint();
}

void TimelineComponent::setBPM(int bpm)
{
    currentBPM = juce::jlimit(30, 300, bpm);
    repaint();
}

//==============================================================================
void TimelineComponent::paint(juce::Graphics& g)
{
    drawBackground(g);
    drawSections(g);
    drawBarMarkers(g);
    drawBeatMarkers(g);
    drawTimeLabels(g);
    drawPlayhead(g);
}

void TimelineComponent::resized()
{
    // Nothing special needed, paint uses getLocalBounds()
}

//==============================================================================
void TimelineComponent::drawBackground(juce::Graphics& g)
{
    auto bounds = getLocalBounds();
    
    // Main background
    g.setColour(AppColours::surface);
    g.fillRect(bounds);
    
    // Border
    g.setColour(AppColours::border);
    g.drawRect(bounds, 1);
}

void TimelineComponent::drawSections(juce::Graphics& g)
{
    if (sections.isEmpty())
        return;
    
    auto bounds = getLocalBounds();
    auto sectionArea = bounds.removeFromTop(headerHeight + sectionHeight);
    sectionArea.removeFromTop(headerHeight);
    
    for (const auto& section : sections)
    {
        float startX = (float)positionToX(section.startTime);
        float endX = (float)positionToX(section.endTime);
        float width = endX - startX;
        
        if (width > 0)
        {
            // Section background
            juce::Rectangle<float> sectionRect(startX, (float)sectionArea.getY(), 
                                                width, (float)sectionArea.getHeight());
            
            juce::Colour sectionColour = section.colour.isTransparent() 
                ? getSectionColour(section.name) 
                : section.colour;
            
            g.setColour(sectionColour.withAlpha(0.6f));
            g.fillRect(sectionRect);
            
            // Section border
            g.setColour(sectionColour.darker(0.3f));
            g.drawRect(sectionRect, 1.0f);
            
            // Section label
            if (width > 30)
            {
                g.setColour(AppColours::textPrimary);
                g.setFont(11.0f);
                g.drawText(section.name, sectionRect.reduced(4, 2), 
                          juce::Justification::centredLeft, true);
            }
        }
    }
}

void TimelineComponent::drawBarMarkers(juce::Graphics& g)
{
    if (currentBPM <= 0 || totalDuration <= 0)
        return;
    
    auto bounds = getLocalBounds();
    float markerAreaTop = (float)(headerHeight + sectionHeight);
    float markerAreaBottom = (float)bounds.getHeight();
    
    // Calculate seconds per bar (4 beats per bar)
    double secondsPerBeat = 60.0 / currentBPM;
    double secondsPerBar = secondsPerBeat * 4.0;
    
    g.setColour(AppColours::textSecondary.withAlpha(0.5f));
    g.setFont(10.0f);
    
    int barNumber = 1;
    for (double time = 0.0; time < totalDuration; time += secondsPerBar)
    {
        float x = (float)positionToX(time);
        
        // Bar line (taller, more prominent)
        g.setColour(AppColours::border.brighter(0.2f));
        g.drawLine(x, markerAreaTop, x, markerAreaBottom, 1.5f);
        
        // Bar number label
        g.setColour(AppColours::textSecondary);
        g.drawText(juce::String(barNumber), 
                  (int)x + 2, (int)markerAreaTop, 20, 12,
                  juce::Justification::left);
        
        barNumber++;
    }
}

void TimelineComponent::drawBeatMarkers(juce::Graphics& g)
{
    if (currentBPM <= 0 || totalDuration <= 0)
        return;
    
    auto bounds = getLocalBounds();
    float markerAreaTop = (float)(headerHeight + sectionHeight);
    float markerAreaBottom = (float)bounds.getHeight();
    
    // Calculate seconds per beat
    double secondsPerBeat = 60.0 / currentBPM;
    double secondsPerBar = secondsPerBeat * 4.0;
    
    g.setColour(AppColours::border.withAlpha(0.3f));
    
    for (double time = 0.0; time < totalDuration; time += secondsPerBeat)
    {
        // Skip bar lines (drawn separately)
        double barPosition = std::fmod(time, secondsPerBar);
        if (barPosition < 0.001)
            continue;
        
        float x = (float)positionToX(time);
        
        // Beat line (shorter, subtle)
        g.drawLine(x, markerAreaTop + 12, x, markerAreaBottom - 4, 0.5f);
    }
}

void TimelineComponent::drawTimeLabels(juce::Graphics& g)
{
    auto bounds = getLocalBounds();
    auto headerArea = bounds.removeFromTop(headerHeight);
    
    g.setColour(AppColours::surfaceAlt);
    g.fillRect(headerArea);
    
    g.setColour(AppColours::textSecondary);
    g.setFont(10.0f);
    
    // Draw time labels every 5 seconds
    double interval = totalDuration > 120.0 ? 10.0 : 5.0;
    
    for (double time = 0.0; time <= totalDuration; time += interval)
    {
        float x = (float)positionToX(time);
        
        int totalSecs = (int)time;
        juce::String timeStr = juce::String(totalSecs / 60) + ":" + 
                               juce::String(totalSecs % 60).paddedLeft('0', 2);
        
        g.drawText(timeStr, (int)x - 15, headerArea.getY(), 30, headerArea.getHeight(),
                  juce::Justification::centred);
    }
}

void TimelineComponent::drawPlayhead(juce::Graphics& g)
{
    if (totalDuration <= 0)
        return;
    
    float x = (float)positionToX(currentPosition);
    auto bounds = getLocalBounds();
    
    // Playhead line
    g.setColour(AppColours::primary);
    g.drawLine(x, 0.0f, x, (float)bounds.getHeight(), 2.0f);
    
    // Playhead triangle at top
    juce::Path triangle;
    triangle.addTriangle(x - 6, 0.0f, x + 6, 0.0f, x, 8.0f);
    g.fillPath(triangle);
}

//==============================================================================
double TimelineComponent::positionToX(double timeSeconds) const
{
    if (totalDuration <= 0)
        return 0.0;
    
    double normalizedPos = timeSeconds / totalDuration;
    return normalizedPos * getWidth();
}

double TimelineComponent::xToPosition(float x) const
{
    if (getWidth() <= 0)
        return 0.0;
    
    double normalizedX = (double)x / getWidth();
    return juce::jlimit(0.0, totalDuration, normalizedX * totalDuration);
}

void TimelineComponent::seekToPosition(float x)
{
    double newPosition = xToPosition(x);
    currentPosition = newPosition;
    
    // Update audio engine position
    audioEngine.setPlaybackPosition(newPosition);
    
    // Notify listeners
    listeners.call(&Listener::timelineSeekRequested, newPosition);
    
    repaint();
}

//==============================================================================
void TimelineComponent::mouseDown(const juce::MouseEvent& event)
{
    seekToPosition((float)event.x);
}

void TimelineComponent::mouseDrag(const juce::MouseEvent& event)
{
    seekToPosition((float)juce::jlimit(0, getWidth(), event.x));
}

//==============================================================================
void TimelineComponent::transportStateChanged(mmg::AudioEngine::TransportState /*newState*/)
{
    // State change handled by timerCallback for position updates
}

void TimelineComponent::playbackPositionChanged(double positionSeconds)
{
    currentPosition = positionSeconds;
    
    juce::MessageManager::callAsync([this]()
    {
        repaint();
    });
}

void TimelineComponent::timerCallback()
{
    if (audioEngine.isPlaying())
    {
        currentPosition = audioEngine.getPlaybackPosition();
        
        // Update total duration from audio engine if available
        double engineDuration = audioEngine.getTotalDuration();
        if (engineDuration > 0)
            totalDuration = engineDuration;
        
        repaint();
    }
}

//==============================================================================
juce::Colour TimelineComponent::getSectionColour(const juce::String& sectionName) const
{
    juce::String lower = sectionName.toLowerCase();
    
    if (lower.contains("intro"))
        return juce::Colour(0xFF4CAF50);  // Green
    else if (lower.contains("verse"))
        return juce::Colour(0xFF2196F3);  // Blue
    else if (lower.contains("chorus") || lower.contains("hook"))
        return juce::Colour(0xFFE91E63);  // Pink
    else if (lower.contains("bridge"))
        return juce::Colour(0xFFFF9800);  // Orange
    else if (lower.contains("outro") || lower.contains("end"))
        return juce::Colour(0xFF9C27B0);  // Purple
    else if (lower.contains("drop"))
        return juce::Colour(0xFFF44336);  // Red
    else if (lower.contains("build"))
        return juce::Colour(0xFFFFEB3B);  // Yellow
    else
        return juce::Colour(0xFF607D8B);  // Blue-grey (default)
}

//==============================================================================
void TimelineComponent::addListener(Listener* listener)
{
    listeners.add(listener);
}

void TimelineComponent::removeListener(Listener* listener)
{
    listeners.remove(listener);
}
