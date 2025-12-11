/*
  ==============================================================================

    SpectrumComponent.cpp
    
    Implementation of the real-time FFT spectrum analyzer.
    
    Phase 7: Waveform & Spectrum Visualization

  ==============================================================================
*/

#include "SpectrumComponent.h"
#include "../Theme/ColourScheme.h"
#include <cmath>

//==============================================================================
SpectrumComponent::SpectrumComponent()
    : forwardFFT(fftOrder),
      window(fftSize, juce::dsp::WindowingFunction<float>::hann)
{
    // Initialize buffers
    fifo.fill(0.0f);
    fftData.fill(0.0f);
    
    spectrumData.resize(numBands, 0.0f);
    rawSpectrumData.resize(fftSize / 2, 0.0f);
    peakHoldData.resize(numBands, 0.0f);
    peakHoldCountdown.resize(numBands, 0);
    
    // Initialize envelope follower state
    envelopeState.resize(numBands, 0.0f);
    
    // Initialize multi-frame averaging buffer
    averagingBuffer.resize(averagingFrames);
    for (auto& frame : averagingBuffer)
        frame.resize(numBands, 0.0f);
    
    // Calculate attack/release coefficients for 60fps display rate
    // Using time constants for professional metering behavior
    calculateBallistics(60.0, defaultAttackMs, defaultReleaseMs);
    
    // Start refresh timer (60 fps)
    startTimerHz(60);
}

SpectrumComponent::~SpectrumComponent()
{
    stopTimer();
}

//==============================================================================
void SpectrumComponent::pushSamples(const float* samples, int numSamples)
{
    // Push samples into FIFO for FFT processing
    for (int i = 0; i < numSamples; ++i)
    {
        if (fifoIndex < fftSize)
        {
            fifo[fifoIndex++] = samples[i];
        }
        
        if (fifoIndex >= fftSize)
        {
            // FIFO is full, signal that FFT can be performed
            nextFFTBlockReady = true;
            fifoIndex = 0;
        }
    }
}

void SpectrumComponent::pushSamples(const float* leftSamples, const float* rightSamples, int numSamples)
{
    // Average stereo to mono for spectrum analysis
    for (int i = 0; i < numSamples; ++i)
    {
        float sample = (leftSamples[i] + rightSamples[i]) * 0.5f;
        
        if (fifoIndex < fftSize)
        {
            fifo[fifoIndex++] = sample;
        }
        
        if (fifoIndex >= fftSize)
        {
            nextFFTBlockReady = true;
            fifoIndex = 0;
        }
    }
}

void SpectrumComponent::clear()
{
    fifo.fill(0.0f);
    fftData.fill(0.0f);
    std::fill(spectrumData.begin(), spectrumData.end(), 0.0f);
    std::fill(rawSpectrumData.begin(), rawSpectrumData.end(), 0.0f);
    std::fill(peakHoldData.begin(), peakHoldData.end(), 0.0f);
    std::fill(peakHoldCountdown.begin(), peakHoldCountdown.end(), 0);
    nextFFTBlockReady = false;
    fifoIndex = 0;
    repaint();
}

//==============================================================================
void SpectrumComponent::setDisplayMode(DisplayMode mode)
{
    displayMode = mode;
    repaint();
}

void SpectrumComponent::setFrequencyScale(FrequencyScale scale)
{
    frequencyScale = scale;
    repaint();
}

void SpectrumComponent::setTheme(const GenreTheme& newTheme)
{
    theme = newTheme;
    repaint();
}

void SpectrumComponent::setSmoothing(float smoothing)
{
    smoothingFactor = juce::jlimit(0.0f, 0.99f, smoothing);
}

void SpectrumComponent::setDecayRate(float rate)
{
    decayRate = juce::jlimit(0.5f, 0.99f, rate);
}

void SpectrumComponent::setPeakHoldEnabled(bool enabled)
{
    peakHoldEnabled = enabled;
    if (!enabled)
    {
        std::fill(peakHoldData.begin(), peakHoldData.end(), 0.0f);
    }
    repaint();
}

void SpectrumComponent::setNumBands(int bands)
{
    numBands = juce::jlimit(16, 256, bands);
    spectrumData.resize(numBands, 0.0f);
    peakHoldData.resize(numBands, 0.0f);
    peakHoldCountdown.resize(numBands, 0);
    envelopeState.resize(numBands, 0.0f);
    
    // Resize averaging buffer
    for (auto& frame : averagingBuffer)
        frame.resize(numBands, 0.0f);
    
    repaint();
}

//==============================================================================
// Production-grade envelope follower ballistics
void SpectrumComponent::calculateBallistics(double displayRate, float attackMs, float releaseMs)
{
    // Convert time constants to per-frame coefficients
    // Using the standard formula: coeff = exp(-1.0 / (time_constant * rate))
    // This gives proper RC-style envelope following behavior
    
    if (attackMs > 0.0f)
        attackCoeff = std::exp(-1000.0f / (attackMs * (float)displayRate));
    else
        attackCoeff = 0.0f;  // Instant attack
    
    if (releaseMs > 0.0f)
        releaseCoeff = std::exp(-1000.0f / (releaseMs * (float)displayRate));
    else
        releaseCoeff = 0.0f;  // Instant release
}

float SpectrumComponent::applyEnvelope(float current, float target, int bandIndex)
{
    // Professional envelope follower with separate attack/release
    // Attack: fast response to rising levels
    // Release: smooth decay on falling levels
    
    float envelope = envelopeState[bandIndex];
    
    if (target > envelope)
    {
        // Attack phase - rising signal, respond quickly
        envelope = attackCoeff * envelope + (1.0f - attackCoeff) * target;
    }
    else
    {
        // Release phase - falling signal, decay smoothly
        envelope = releaseCoeff * envelope + (1.0f - releaseCoeff) * target;
    }
    
    // Store state for next frame
    envelopeState[bandIndex] = envelope;
    
    return envelope;
}

//==============================================================================
void SpectrumComponent::timerCallback()
{
    if (nextFFTBlockReady.load())
    {
        processFFT();
        nextFFTBlockReady = false;
    }
    else
    {
        // No new FFT data - apply natural decay via envelope follower
        // This makes inactive frequencies smoothly return to zero
        for (int i = 0; i < numBands; ++i)
        {
            // Apply release envelope toward zero when no new data
            spectrumData[i] = applyEnvelope(spectrumData[i], 0.0f, i);
        }
    }
    
    // Decay peak hold indicators
    for (int i = 0; i < numBands; ++i)
    {
        if (peakHoldCountdown[i] > 0)
        {
            peakHoldCountdown[i]--;
        }
        else
        {
            // Smooth peak decay
            peakHoldData[i] *= peakDecayRate;
            if (peakHoldData[i] < 0.001f)
                peakHoldData[i] = 0.0f;
        }
    }
    
    repaint();
}

void SpectrumComponent::processFFT()
{
    // Copy FIFO to FFT data buffer
    std::copy(fifo.begin(), fifo.begin() + fftSize, fftData.begin());
    
    // Apply windowing function (Hann window reduces spectral leakage)
    window.multiplyWithWindowingTable(fftData.data(), fftSize);
    
    // Perform FFT - gets magnitude spectrum directly
    forwardFFT.performFrequencyOnlyForwardTransform(fftData.data());
    
    // Store raw spectrum data (first half of FFT output = positive frequencies)
    for (int i = 0; i < fftSize / 2; ++i)
    {
        rawSpectrumData[i] = fftData[i];
    }
    
    // Calculate magnitude for each display band with professional processing
    for (int band = 0; band < numBands; ++band)
    {
        float lowFreq = getFrequencyForBand(band);
        float highFreq = getFrequencyForBand(band + 1);
        
        float magnitude = getMagnitudeForFrequencyRange(lowFreq, highFreq);
        
        // === NOISE FLOOR GATING ===
        // Prevent flickering by gating values below noise floor
        if (magnitude < gateThreshold)
        {
            magnitude = 0.0f;
        }
        
        // Convert to dB scale with wide dynamic range
        float db = juce::Decibels::gainToDecibels(magnitude, noiseFloorDb);
        
        // Normalize to 0-1 range with -60dB as bottom, 0dB as top
        float normalized = juce::jmap(db, -60.0f, 0.0f, 0.0f, 1.0f);
        normalized = juce::jlimit(0.0f, 1.0f, normalized);
        
        // === MULTI-FRAME AVERAGING ===
        // Store in circular averaging buffer
        averagingBuffer[averagingIndex][band] = normalized;
        
        // Calculate average across frames
        float averaged = 0.0f;
        for (int f = 0; f < averagingFrames; ++f)
        {
            averaged += averagingBuffer[f][band];
        }
        averaged /= (float)averagingFrames;
        
        // === ENVELOPE FOLLOWER ===
        // Apply attack/release ballistics for smooth, professional metering
        float enveloped = applyEnvelope(spectrumData[band], averaged, band);
        
        // Final spectrum value with all processing
        spectrumData[band] = enveloped;
        
        // Update peak hold (tracks actual peaks, not smoothed values)
        if (normalized > peakHoldData[band])
        {
            peakHoldData[band] = normalized;
            peakHoldCountdown[band] = peakHoldFrames;
        }
    }
    
    // Advance averaging buffer index
    averagingIndex = (averagingIndex + 1) % averagingFrames;
}

float SpectrumComponent::getFrequencyForBin(int bin) const
{
    return (float)bin * (float)currentSampleRate / (float)fftSize;
}

int SpectrumComponent::getBinForFrequency(float frequency) const
{
    return (int)(frequency * (float)fftSize / (float)currentSampleRate);
}

float SpectrumComponent::getMagnitudeForFrequencyRange(float lowFreq, float highFreq) const
{
    int lowBin = getBinForFrequency(lowFreq);
    int highBin = getBinForFrequency(highFreq);
    
    lowBin = juce::jlimit(0, (int)rawSpectrumData.size() - 1, lowBin);
    highBin = juce::jlimit(lowBin, (int)rawSpectrumData.size() - 1, highBin);
    
    if (lowBin == highBin)
        return rawSpectrumData[lowBin];
    
    // Find max magnitude in range (peak detection)
    float maxMag = 0.0f;
    for (int i = lowBin; i <= highBin; ++i)
    {
        maxMag = juce::jmax(maxMag, rawSpectrumData[i]);
    }
    
    return maxMag;
}

float SpectrumComponent::getFrequencyForBand(int band) const
{
    float minFreq = 20.0f;
    float maxFreq = 20000.0f;
    
    float normalized = (float)band / (float)numBands;
    
    if (frequencyScale == FrequencyScale::Logarithmic)
    {
        // Logarithmic scale - more resolution in low frequencies
        float logMin = std::log10(minFreq);
        float logMax = std::log10(maxFreq);
        return std::pow(10.0f, logMin + normalized * (logMax - logMin));
    }
    else
    {
        // Linear scale
        return minFreq + normalized * (maxFreq - minFreq);
    }
}

//==============================================================================
void SpectrumComponent::paint(juce::Graphics& g)
{
    // Draw background
    drawBackground(g);
    
    // Draw spectrum based on mode
    switch (displayMode)
    {
        case DisplayMode::Bars:
            drawSpectrumBars(g);
            break;
        case DisplayMode::Line:
            drawSpectrumLine(g);
            break;
        case DisplayMode::Filled:
            drawSpectrumFilled(g);
            break;
        case DisplayMode::Glow:
            drawSpectrumGlow(g);
            break;
    }
    
    // Draw peak hold
    if (peakHoldEnabled)
    {
        drawPeakHold(g);
    }
    
    // Draw frequency labels
    drawFrequencyLabels(g);
}

void SpectrumComponent::drawBackground(juce::Graphics& g)
{
    auto bounds = getLocalBounds().toFloat();
    
    // Gradient background
    juce::ColourGradient gradient(
        theme.background,
        0, bounds.getHeight(),
        theme.background.brighter(0.1f),
        0, 0,
        false
    );
    g.setGradientFill(gradient);
    g.fillRoundedRectangle(bounds, 4.0f);
    
    // Grid lines
    g.setColour(theme.gridLines);
    
    // Horizontal dB lines
    for (int db = -48; db <= 0; db += 12)
    {
        float y = juce::jmap((float)db, -60.0f, 0.0f, bounds.getHeight() - 20.0f, 4.0f);
        g.drawHorizontalLine((int)y, 0.0f, bounds.getWidth());
    }
    
    // Border
    g.setColour(theme.gridLines.withAlpha(0.5f));
    g.drawRoundedRectangle(bounds.reduced(0.5f), 4.0f, 1.0f);
}

void SpectrumComponent::drawFrequencyLabels(juce::Graphics& g)
{
    auto bounds = getLocalBounds();
    g.setColour(theme.gridLines.brighter(0.5f));
    g.setFont(10.0f);
    
    // Frequency labels at bottom
    static const float labelFreqs[] = { 50, 100, 200, 500, 1000, 2000, 5000, 10000 };
    
    for (float freq : labelFreqs)
    {
        // Find x position for this frequency
        float normalized;
        if (frequencyScale == FrequencyScale::Logarithmic)
        {
            float logMin = std::log10(20.0f);
            float logMax = std::log10(20000.0f);
            float logFreq = std::log10(freq);
            normalized = (logFreq - logMin) / (logMax - logMin);
        }
        else
        {
            normalized = (freq - 20.0f) / (20000.0f - 20.0f);
        }
        
        int x = (int)(normalized * bounds.getWidth());
        
        juce::String label = freq >= 1000 
            ? juce::String(freq / 1000, 0) + "k"
            : juce::String((int)freq);
        
        g.drawText(label, x - 15, bounds.getHeight() - 16, 30, 14, 
                   juce::Justification::centred);
    }
}

void SpectrumComponent::drawSpectrumBars(juce::Graphics& g)
{
    auto bounds = getLocalBounds().toFloat().reduced(4);
    bounds.removeFromBottom(20); // Space for labels
    
    float barWidth = bounds.getWidth() / (float)numBands;
    float gap = juce::jmax(1.0f, barWidth * 0.1f);
    
    for (int i = 0; i < numBands; ++i)
    {
        float x = bounds.getX() + i * barWidth + gap / 2;
        float barHeight = spectrumData[i] * bounds.getHeight();
        float y = bounds.getBottom() - barHeight;
        
        // Get color for this frequency band
        juce::Colour barColour = getColourForBand(i);
        
        // Draw bar
        g.setColour(barColour);
        g.fillRoundedRectangle(x, y, barWidth - gap, barHeight, 2.0f);
    }
}

void SpectrumComponent::drawSpectrumLine(juce::Graphics& g)
{
    auto bounds = getLocalBounds().toFloat().reduced(4);
    bounds.removeFromBottom(20);
    
    if (spectrumData.empty()) return;
    
    juce::Path path;
    
    for (int i = 0; i < numBands; ++i)
    {
        float x = bounds.getX() + ((float)i / (float)(numBands - 1)) * bounds.getWidth();
        float y = bounds.getBottom() - spectrumData[i] * bounds.getHeight();
        
        if (i == 0)
            path.startNewSubPath(x, y);
        else
            path.lineTo(x, y);
    }
    
    // Draw glow
    for (int i = 3; i >= 1; --i)
    {
        g.setColour(theme.spectrumMid.withAlpha(0.1f / (float)i));
        g.strokePath(path, juce::PathStrokeType(2.0f + i * 2.0f, juce::PathStrokeType::curved));
    }
    
    // Draw main line with gradient
    g.setColour(theme.spectrumMid);
    g.strokePath(path, juce::PathStrokeType(2.0f, juce::PathStrokeType::curved));
}

void SpectrumComponent::drawSpectrumFilled(juce::Graphics& g)
{
    auto bounds = getLocalBounds().toFloat().reduced(4);
    bounds.removeFromBottom(20);
    
    if (spectrumData.empty()) return;
    
    juce::Path path;
    path.startNewSubPath(bounds.getX(), bounds.getBottom());
    
    for (int i = 0; i < numBands; ++i)
    {
        float x = bounds.getX() + ((float)i / (float)(numBands - 1)) * bounds.getWidth();
        float y = bounds.getBottom() - spectrumData[i] * bounds.getHeight();
        path.lineTo(x, y);
    }
    
    path.lineTo(bounds.getRight(), bounds.getBottom());
    path.closeSubPath();
    
    // Gradient fill
    juce::ColourGradient gradient(
        theme.spectrumHigh.withAlpha(0.8f),
        bounds.getCentreX(), bounds.getY(),
        theme.spectrumLow.withAlpha(0.3f),
        bounds.getCentreX(), bounds.getBottom(),
        false
    );
    g.setGradientFill(gradient);
    g.fillPath(path);
    
    // Outline
    juce::Path outline;
    outline.startNewSubPath(bounds.getX(), bounds.getBottom());
    for (int i = 0; i < numBands; ++i)
    {
        float x = bounds.getX() + ((float)i / (float)(numBands - 1)) * bounds.getWidth();
        float y = bounds.getBottom() - spectrumData[i] * bounds.getHeight();
        outline.lineTo(x, y);
    }
    
    g.setColour(theme.spectrumMid);
    g.strokePath(outline, juce::PathStrokeType(1.5f, juce::PathStrokeType::curved));
}

void SpectrumComponent::drawSpectrumGlow(juce::Graphics& g)
{
    auto bounds = getLocalBounds().toFloat().reduced(4);
    bounds.removeFromBottom(20);
    
    float barWidth = bounds.getWidth() / (float)numBands;
    float gap = juce::jmax(1.0f, barWidth * 0.15f);
    
    for (int i = 0; i < numBands; ++i)
    {
        float x = bounds.getX() + i * barWidth + gap / 2;
        float barHeight = spectrumData[i] * bounds.getHeight();
        float y = bounds.getBottom() - barHeight;
        
        juce::Colour barColour = getColourForBand(i);
        
        // Draw glow layers (outer to inner)
        if (spectrumData[i] > 0.1f)
        {
            for (int layer = 3; layer >= 1; --layer)
            {
                float expand = layer * 2.0f;
                float alpha = 0.15f / (float)layer;
                
                g.setColour(barColour.withAlpha(alpha));
                g.fillRoundedRectangle(
                    x - expand, y - expand,
                    barWidth - gap + expand * 2, barHeight + expand * 2,
                    3.0f
                );
            }
        }
        
        // Draw main bar with gradient
        juce::ColourGradient gradient(
            barColour.brighter(0.3f),
            x, y,
            barColour.darker(0.2f),
            x, bounds.getBottom(),
            false
        );
        g.setGradientFill(gradient);
        g.fillRoundedRectangle(x, y, barWidth - gap, barHeight, 2.0f);
        
        // Top highlight
        if (barHeight > 4)
        {
            g.setColour(juce::Colours::white.withAlpha(0.3f));
            g.fillRoundedRectangle(x + 1, y + 1, barWidth - gap - 2, 2.0f, 1.0f);
        }
    }
}

void SpectrumComponent::drawPeakHold(juce::Graphics& g)
{
    auto bounds = getLocalBounds().toFloat().reduced(4);
    bounds.removeFromBottom(20);
    
    float barWidth = bounds.getWidth() / (float)numBands;
    float gap = juce::jmax(1.0f, barWidth * 0.15f);
    
    g.setColour(theme.spectrumPeak);
    
    for (int i = 0; i < numBands; ++i)
    {
        if (peakHoldData[i] > 0.01f)
        {
            float x = bounds.getX() + i * barWidth + gap / 2;
            float y = bounds.getBottom() - peakHoldData[i] * bounds.getHeight();
            
            // Draw peak indicator line
            g.fillRect(x, y - 1, barWidth - gap, 2.0f);
        }
    }
}

juce::Colour SpectrumComponent::getColourForBand(int band) const
{
    float normalized = (float)band / (float)(numBands - 1);
    return theme.getSpectrumColour(normalized);
}

void SpectrumComponent::resized()
{
    // Could adjust numBands based on width for optimal display
}

