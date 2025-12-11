/*
  ==============================================================================

    WaveformComponent.cpp
    
    Implementation of the real-time waveform visualization.
    
    Phase 7: Waveform & Spectrum Visualization

  ==============================================================================
*/

#include "WaveformComponent.h"
#include "../Theme/ColourScheme.h"

//==============================================================================
WaveformComponent::WaveformComponent()
{
    // Initialize buffers
    leftBuffer.fill(0.0f);
    rightBuffer.fill(0.0f);
    displayBufferLeft.resize(displaySamples, 0.0f);
    displayBufferRight.resize(displaySamples, 0.0f);
    
    // Start the display refresh timer (60 fps)
    startTimerHz(60);
}

WaveformComponent::~WaveformComponent()
{
    stopTimer();
}

//==============================================================================
void WaveformComponent::pushSamples(const float* samples, int numSamples)
{
    // Push mono samples to both channels
    pushSamples(samples, samples, numSamples);
}

void WaveformComponent::pushSamples(const float* leftSamples, const float* rightSamples, int numSamples)
{
    // Write samples to ring buffer (lock-free for audio thread)
    int pos = writePosition.load();
    
    for (int i = 0; i < numSamples; ++i)
    {
        leftBuffer[pos] = leftSamples[i];
        rightBuffer[pos] = rightSamples != nullptr ? rightSamples[i] : leftSamples[i];
        
        pos = (pos + 1) % bufferSize;
    }
    
    writePosition.store(pos);
}

void WaveformComponent::clear()
{
    leftBuffer.fill(0.0f);
    rightBuffer.fill(0.0f);
    std::fill(displayBufferLeft.begin(), displayBufferLeft.end(), 0.0f);
    std::fill(displayBufferRight.begin(), displayBufferRight.end(), 0.0f);
    peakLeft = 0.0f;
    peakRight = 0.0f;
    repaint();
}

//==============================================================================
void WaveformComponent::setDisplayMode(DisplayMode mode)
{
    displayMode = mode;
    repaint();
}

void WaveformComponent::setTheme(const GenreTheme& newTheme)
{
    theme = newTheme;
    repaint();
}

void WaveformComponent::setGlowEnabled(bool enabled)
{
    glowEnabled = enabled;
    repaint();
}

void WaveformComponent::setLineThickness(float thickness)
{
    lineThickness = juce::jlimit(1.0f, 8.0f, thickness);
    repaint();
}

void WaveformComponent::setStereoMode(bool stereo)
{
    stereoMode = stereo;
    repaint();
}

//==============================================================================
void WaveformComponent::timerCallback()
{
    processSamplesForDisplay();
    
    // Decay peaks
    peakLeft *= peakDecay;
    peakRight *= peakDecay;
    
    repaint();
}

void WaveformComponent::processSamplesForDisplay()
{
    int readPos = writePosition.load();
    
    // Calculate how many buffer samples per display sample
    float samplesPerPixel = (float)bufferSize / (float)displaySamples;
    
    for (int i = 0; i < displaySamples; ++i)
    {
        // Read position in the ring buffer (going backwards from write position)
        float bufferPos = (float)(readPos - (displaySamples - i) * (int)(samplesPerPixel));
        while (bufferPos < 0) bufferPos += bufferSize;
        
        // Get averaged sample
        displayBufferLeft[i] = getSampleForPosition(
            std::vector<float>(leftBuffer.begin(), leftBuffer.end()), bufferPos);
        displayBufferRight[i] = getSampleForPosition(
            std::vector<float>(rightBuffer.begin(), rightBuffer.end()), bufferPos);
        
        // Update peaks
        float absLeft = std::abs(displayBufferLeft[i]);
        float absRight = std::abs(displayBufferRight[i]);
        if (absLeft > peakLeft) peakLeft = absLeft;
        if (absRight > peakRight) peakRight = absRight;
    }
}

float WaveformComponent::getSampleForPosition(const std::vector<float>& buffer, float position)
{
    // Linear interpolation for smooth display
    int idx1 = (int)position % buffer.size();
    int idx2 = (idx1 + 1) % buffer.size();
    float frac = position - std::floor(position);
    
    return buffer[idx1] * (1.0f - frac) + buffer[idx2] * frac;
}

//==============================================================================
void WaveformComponent::paint(juce::Graphics& g)
{
    auto bounds = getLocalBounds().toFloat();
    
    // Draw background
    drawBackground(g);
    
    // Draw grid lines
    drawGrid(g);
    
    // Draw waveform(s)
    if (stereoMode)
    {
        // Split view for stereo
        auto topHalf = bounds.removeFromTop(bounds.getHeight() / 2);
        auto bottomHalf = bounds;
        
        // Draw separator
        g.setColour(theme.gridLines);
        g.drawHorizontalLine((int)topHalf.getBottom(), 0.0f, (float)getWidth());
        
        // Top = Left channel
        g.saveState();
        g.reduceClipRegion(topHalf.toNearestInt());
        drawWaveformByMode(g, displayBufferLeft, topHalf);
        g.restoreState();
        
        // Bottom = Right channel  
        g.saveState();
        g.reduceClipRegion(bottomHalf.toNearestInt());
        drawWaveformByMode(g, displayBufferRight, bottomHalf);
        g.restoreState();
    }
    else
    {
        // Mono or mixed display
        drawWaveformByMode(g, displayBufferLeft, bounds);
    }
    
    // Draw peak indicators
    drawPeakIndicators(g);
}

void WaveformComponent::drawWaveformByMode(juce::Graphics& g, const std::vector<float>& samples,
                                            juce::Rectangle<float> bounds)
{
    switch (displayMode)
    {
        case DisplayMode::Line:
            drawWaveformLine(g, samples, theme.waveformFill, theme.waveformOutline);
            break;
        case DisplayMode::Filled:
            drawWaveformFilled(g, samples, theme.waveformFill, theme.waveformOutline);
            break;
        case DisplayMode::Mirror:
            drawWaveformMirror(g, samples, theme.waveformFill, theme.waveformOutline);
            break;
        case DisplayMode::Bars:
            drawWaveformBars(g, samples, theme.waveformFill);
            break;
    }
}

void WaveformComponent::drawBackground(juce::Graphics& g)
{
    auto bounds = getLocalBounds().toFloat();
    
    // Gradient background
    juce::ColourGradient gradient(
        theme.background,
        0, 0,
        theme.background.darker(0.3f),
        0, bounds.getHeight(),
        false
    );
    g.setGradientFill(gradient);
    g.fillRoundedRectangle(bounds, 4.0f);
    
    // Subtle border
    g.setColour(theme.gridLines.withAlpha(0.5f));
    g.drawRoundedRectangle(bounds.reduced(0.5f), 4.0f, 1.0f);
}

void WaveformComponent::drawGrid(juce::Graphics& g)
{
    auto bounds = getLocalBounds().toFloat();
    g.setColour(theme.gridLines);
    
    // Center line
    float centerY = bounds.getCentreY();
    g.drawHorizontalLine((int)centerY, bounds.getX(), bounds.getRight());
    
    // Quarter lines (softer)
    g.setColour(theme.gridLines.withAlpha(0.3f));
    g.drawHorizontalLine((int)(centerY - bounds.getHeight() * 0.25f), bounds.getX(), bounds.getRight());
    g.drawHorizontalLine((int)(centerY + bounds.getHeight() * 0.25f), bounds.getX(), bounds.getRight());
    
    // Vertical divisions (every 1/8th)
    for (int i = 1; i < 8; ++i)
    {
        float x = bounds.getX() + (bounds.getWidth() * i / 8.0f);
        g.drawVerticalLine((int)x, bounds.getY(), bounds.getBottom());
    }
}

void WaveformComponent::drawWaveformLine(juce::Graphics& g, const std::vector<float>& samples,
                                          juce::Colour fillColour, juce::Colour outlineColour)
{
    if (samples.empty()) return;
    
    auto bounds = getLocalBounds().toFloat().reduced(2);
    float centerY = bounds.getCentreY();
    float amplitude = bounds.getHeight() * 0.45f;
    
    juce::Path path;
    
    for (size_t i = 0; i < samples.size(); ++i)
    {
        float x = bounds.getX() + (float)i / (float)(samples.size() - 1) * bounds.getWidth();
        float y = centerY - samples[i] * amplitude;
        
        if (i == 0)
            path.startNewSubPath(x, y);
        else
            path.lineTo(x, y);
    }
    
    // Draw glow if enabled
    if (glowEnabled)
    {
        drawGlow(g, path, theme.waveformGlow);
    }
    
    // Draw the line
    g.setColour(outlineColour);
    g.strokePath(path, juce::PathStrokeType(lineThickness, juce::PathStrokeType::curved));
    
    cachedPath = path;
}

void WaveformComponent::drawWaveformFilled(juce::Graphics& g, const std::vector<float>& samples,
                                            juce::Colour fillColour, juce::Colour outlineColour)
{
    if (samples.empty()) return;
    
    auto bounds = getLocalBounds().toFloat().reduced(2);
    float centerY = bounds.getCentreY();
    float amplitude = bounds.getHeight() * 0.45f;
    
    juce::Path path;
    
    // Start at center left
    path.startNewSubPath(bounds.getX(), centerY);
    
    // Draw top edge (waveform)
    for (size_t i = 0; i < samples.size(); ++i)
    {
        float x = bounds.getX() + (float)i / (float)(samples.size() - 1) * bounds.getWidth();
        float y = centerY - samples[i] * amplitude;
        path.lineTo(x, y);
    }
    
    // Close back to center
    path.lineTo(bounds.getRight(), centerY);
    path.closeSubPath();
    
    // Fill with gradient
    juce::ColourGradient gradient(
        fillColour,
        bounds.getCentreX(), centerY - amplitude,
        fillColour.withAlpha(0.2f),
        bounds.getCentreX(), centerY,
        false
    );
    g.setGradientFill(gradient);
    g.fillPath(path);
    
    // Draw glow
    if (glowEnabled)
    {
        juce::Path outlinePath;
        outlinePath.startNewSubPath(bounds.getX(), centerY);
        for (size_t i = 0; i < samples.size(); ++i)
        {
            float x = bounds.getX() + (float)i / (float)(samples.size() - 1) * bounds.getWidth();
            float y = centerY - samples[i] * amplitude;
            outlinePath.lineTo(x, y);
        }
        drawGlow(g, outlinePath, theme.waveformGlow);
    }
    
    // Draw outline
    g.setColour(outlineColour);
    juce::Path strokePath;
    strokePath.startNewSubPath(bounds.getX(), centerY);
    for (size_t i = 0; i < samples.size(); ++i)
    {
        float x = bounds.getX() + (float)i / (float)(samples.size() - 1) * bounds.getWidth();
        float y = centerY - samples[i] * amplitude;
        strokePath.lineTo(x, y);
    }
    g.strokePath(strokePath, juce::PathStrokeType(lineThickness * 0.5f, juce::PathStrokeType::curved));
    
    cachedPath = strokePath;
}

void WaveformComponent::drawWaveformMirror(juce::Graphics& g, const std::vector<float>& samples,
                                            juce::Colour fillColour, juce::Colour outlineColour)
{
    if (samples.empty()) return;
    
    auto bounds = getLocalBounds().toFloat().reduced(2);
    float centerY = bounds.getCentreY();
    float amplitude = bounds.getHeight() * 0.45f;
    
    juce::Path path;
    
    // Draw mirrored (absolute value, reflected)
    path.startNewSubPath(bounds.getX(), centerY);
    
    // Top half
    for (size_t i = 0; i < samples.size(); ++i)
    {
        float x = bounds.getX() + (float)i / (float)(samples.size() - 1) * bounds.getWidth();
        float y = centerY - std::abs(samples[i]) * amplitude;
        path.lineTo(x, y);
    }
    
    // Back across bottom
    for (int i = (int)samples.size() - 1; i >= 0; --i)
    {
        float x = bounds.getX() + (float)i / (float)(samples.size() - 1) * bounds.getWidth();
        float y = centerY + std::abs(samples[i]) * amplitude;
        path.lineTo(x, y);
    }
    
    path.closeSubPath();
    
    // Fill with vertical gradient
    juce::ColourGradient gradient(
        fillColour,
        bounds.getCentreX(), centerY - amplitude,
        fillColour.withAlpha(0.1f),
        bounds.getCentreX(), centerY,
        false
    );
    g.setGradientFill(gradient);
    g.fillPath(path);
    
    // Draw glow on top edge
    if (glowEnabled)
    {
        juce::Path topPath;
        topPath.startNewSubPath(bounds.getX(), centerY);
        for (size_t i = 0; i < samples.size(); ++i)
        {
            float x = bounds.getX() + (float)i / (float)(samples.size() - 1) * bounds.getWidth();
            float y = centerY - std::abs(samples[i]) * amplitude;
            topPath.lineTo(x, y);
        }
        drawGlow(g, topPath, theme.waveformGlow);
    }
    
    // Outline
    g.setColour(outlineColour);
    g.strokePath(path, juce::PathStrokeType(lineThickness * 0.5f));
    
    cachedPath = path;
}

void WaveformComponent::drawWaveformBars(juce::Graphics& g, const std::vector<float>& samples,
                                          juce::Colour fillColour)
{
    if (samples.empty()) return;
    
    auto bounds = getLocalBounds().toFloat().reduced(2);
    float centerY = bounds.getCentreY();
    float amplitude = bounds.getHeight() * 0.45f;
    
    int numBars = 64;
    int samplesPerBar = (int)samples.size() / numBars;
    float barWidth = bounds.getWidth() / (float)numBars;
    float gap = 2.0f;
    
    for (int i = 0; i < numBars; ++i)
    {
        // Calculate average/max for this segment
        float maxVal = 0.0f;
        for (int j = 0; j < samplesPerBar; ++j)
        {
            int idx = i * samplesPerBar + j;
            if (idx < (int)samples.size())
                maxVal = juce::jmax(maxVal, std::abs(samples[idx]));
        }
        
        float barHeight = maxVal * amplitude * 2;
        float x = bounds.getX() + i * barWidth + gap / 2;
        float y = centerY - barHeight / 2;
        
        // Color based on intensity
        float intensity = maxVal;
        juce::Colour barColour = fillColour.withMultipliedBrightness(0.5f + intensity * 0.5f);
        
        // Draw bar with rounded corners
        g.setColour(barColour);
        g.fillRoundedRectangle(x, y, barWidth - gap, barHeight, 2.0f);
        
        // Glow on top
        if (glowEnabled && maxVal > 0.3f)
        {
            g.setColour(theme.waveformGlow.withAlpha(maxVal * 0.5f));
            g.fillRoundedRectangle(x - 1, y - 1, barWidth - gap + 2, barHeight + 2, 3.0f);
        }
    }
}

void WaveformComponent::drawGlow(juce::Graphics& g, const juce::Path& path, juce::Colour glowColour)
{
    // Draw multiple strokes with decreasing opacity for glow effect
    for (int i = 4; i >= 1; --i)
    {
        float alpha = 0.15f / (float)i;
        float width = lineThickness + i * 3.0f;
        
        g.setColour(glowColour.withAlpha(alpha));
        g.strokePath(path, juce::PathStrokeType(width, juce::PathStrokeType::curved));
    }
}

void WaveformComponent::drawPeakIndicators(juce::Graphics& g)
{
    auto bounds = getLocalBounds().toFloat();
    
    // Peak level indicators on the sides
    float indicatorWidth = 4.0f;
    float margin = 4.0f;
    
    // Left peak
    float leftHeight = peakLeft * (bounds.getHeight() - margin * 2);
    juce::Rectangle<float> leftIndicator(
        margin, bounds.getCentreY() - leftHeight / 2,
        indicatorWidth, leftHeight
    );
    
    // Right peak
    float rightHeight = peakRight * (bounds.getHeight() - margin * 2);
    juce::Rectangle<float> rightIndicator(
        bounds.getWidth() - margin - indicatorWidth,
        bounds.getCentreY() - rightHeight / 2,
        indicatorWidth, rightHeight
    );
    
    // Draw peak bars with gradient
    auto drawPeakBar = [&](juce::Rectangle<float> rect, float peak) {
        if (peak < 0.01f) return;
        
        juce::Colour colour = peak > 0.9f ? juce::Colours::red
                            : peak > 0.7f ? juce::Colours::orange
                            : theme.waveformFill;
        
        g.setColour(colour.withAlpha(0.8f));
        g.fillRoundedRectangle(rect, 2.0f);
    };
    
    drawPeakBar(leftIndicator, peakLeft);
    drawPeakBar(rightIndicator, peakRight);
}

void WaveformComponent::resized()
{
    // Adjust display resolution based on width
    displaySamples = juce::jmax(128, getWidth());
    displayBufferLeft.resize(displaySamples, 0.0f);
    displayBufferRight.resize(displaySamples, 0.0f);
}

