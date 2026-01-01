#include "LevelMeter.h"

namespace UI
{
    LevelMeter::LevelMeter()
    {
        startTimerHz(60); // 60 FPS refresh
    }

    LevelMeter::~LevelMeter()
    {
        stopTimer();
    }

    void LevelMeter::setLevel(float level)
    {
        // Instant attack
        if (level > currentLevel)
            currentLevel = level;
        
        if (level > currentPeak)
            currentPeak = level;
    }

    void LevelMeter::timerCallback()
    {
        // Decay
        currentLevel *= 0.9f; // Simple exponential decay
        currentPeak -= 0.01f; // Linear decay for peak hold
        
        if (currentLevel < 0.0f) currentLevel = 0.0f;
        if (currentPeak < 0.0f) currentPeak = 0.0f;

        repaint();
    }

    void LevelMeter::paint(juce::Graphics& g)
    {
        auto bounds = getLocalBounds().toFloat();
        
        // Background
        g.setColour(juce::Colours::black.withAlpha(0.5f));
        g.fillRect(bounds);

        // Meter
        // Convert linear to dB-like scale for visualization (or just linear for now)
        // Let's use a simple log-like mapping or just linear for simplicity first
        // Usually meters are logarithmic.
        
        // Map 0..1 to 0..height
        float normalizedLevel = std::min(currentLevel, 1.0f);
        float meterHeight = bounds.getHeight() * normalizedLevel;
        
        g.setColour(juce::Colours::green);
        if (normalizedLevel > 0.8f) g.setColour(juce::Colours::orange);
        if (normalizedLevel > 0.95f) g.setColour(juce::Colours::red);

        g.fillRect(bounds.removeFromBottom(meterHeight));

        // Peak hold
        float peakY = bounds.getHeight() * (1.0f - std::min(currentPeak, 1.0f));
        g.setColour(juce::Colours::white);
        g.fillRect(0.0f, peakY, bounds.getWidth(), 2.0f);
    }

    void LevelMeter::resized()
    {
    }
}
