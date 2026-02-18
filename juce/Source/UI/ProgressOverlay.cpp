/*
  ==============================================================================

    ProgressOverlay.cpp
    
    Implementation of progress overlay.

  ==============================================================================
*/

#include "ProgressOverlay.h"
#include "Theme/ColourScheme.h"

//==============================================================================
ProgressOverlay::ProgressOverlay(AppState& state)
    : appState(state)
{
    setVisible(false);
    setAlwaysOnTop(true);
    
    // Title
    titleLabel.setText("Generating Music", juce::dontSendNotification);
    titleLabel.setFont(juce::Font(24.0f, juce::Font::bold));
    titleLabel.setJustificationType(juce::Justification::centred);
    addAndMakeVisible(titleLabel);
    
    // Step label
    stepLabel.setText("Initializing...", juce::dontSendNotification);
    stepLabel.setFont(juce::Font(14.0f));
    stepLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    stepLabel.setJustificationType(juce::Justification::centred);
    addAndMakeVisible(stepLabel);

    // Detail label (secondary progress text)
    detailLabel.setText("", juce::dontSendNotification);
    detailLabel.setFont(juce::Font(12.0f));
    detailLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    detailLabel.setJustificationType(juce::Justification::centred);
    addAndMakeVisible(detailLabel);
    
    // Percent label
    percentLabel.setText("0%", juce::dontSendNotification);
    percentLabel.setFont(juce::Font(48.0f, juce::Font::bold));
    percentLabel.setColour(juce::Label::textColourId, AppColours::primary);
    percentLabel.setJustificationType(juce::Justification::centred);
    addAndMakeVisible(percentLabel);
    
    // Cancel button - more prominent
    cancelButton.setColour(juce::TextButton::buttonColourId, AppColours::error);
    cancelButton.setColour(juce::TextButton::textColourOffId, juce::Colours::white);
    cancelButton.onClick = [this] {
        // Immediately start hiding and notify listeners
        stepLabel.setText("Cancelling...", juce::dontSendNotification);
        cancelButton.setEnabled(false);
        listeners.call(&Listener::cancelRequested);
        
        // Hide after a brief delay
        juce::Timer::callAfterDelay(500, [this] {
            hide();
        });
    };
    addAndMakeVisible(cancelButton);
    
    appState.addListener(this);
}

ProgressOverlay::~ProgressOverlay()
{
    stopTimer();
    appState.removeListener(this);
}

//==============================================================================
void ProgressOverlay::paint(juce::Graphics& g)
{
    // Semi-transparent background
    g.setColour(AppColours::background.withAlpha(fadeAlpha * 0.9f));
    g.fillAll();
    
    auto bounds = getLocalBounds();
    auto centerX = bounds.getCentreX();
    auto centerY = bounds.getCentreY();
    
    // Card background
    auto cardBounds = juce::Rectangle<float>(300, 280).withCentre({ (float)centerX, (float)centerY });
    g.setColour(AppColours::surface.withAlpha(fadeAlpha));
    g.fillRoundedRectangle(cardBounds, 12.0f);
    
    g.setColour(AppColours::border.withAlpha(fadeAlpha));
    g.drawRoundedRectangle(cardBounds, 12.0f, 1.0f);
    
    // Progress ring
    auto ringBounds = juce::Rectangle<float>(100, 100).withCentre({ (float)centerX, (float)centerY - 40 });
    auto ringCenter = ringBounds.getCentre();
    auto ringRadius = ringBounds.getWidth() * 0.45f;
    
    // Background ring
    g.setColour(AppColours::surfaceAlt.withAlpha(fadeAlpha));
    g.drawEllipse(ringBounds.reduced(5), 6.0f);
    
    // Progress arc
    juce::Path progressArc;
    auto startAngle = -juce::MathConstants<float>::halfPi;
    auto endAngle = startAngle + (float)(currentProgress * juce::MathConstants<float>::twoPi);
    
    progressArc.addCentredArc(ringCenter.x, ringCenter.y, ringRadius, ringRadius,
                             0, startAngle, endAngle, true);
    
    g.setColour(AppColours::primary.withAlpha(fadeAlpha));
    g.strokePath(progressArc, juce::PathStrokeType(6.0f, juce::PathStrokeType::curved,
                                                    juce::PathStrokeType::rounded));
    
    // Spinner for indeterminate states
    if (currentProgress < 0.01)
    {
        juce::Path spinnerArc;
        auto spinStart = spinnerAngle;
        auto spinEnd = spinnerAngle + juce::MathConstants<float>::halfPi;
        
        spinnerArc.addCentredArc(ringCenter.x, ringCenter.y, ringRadius, ringRadius,
                                0, spinStart, spinEnd, true);
        
        g.setColour(AppColours::primary.withAlpha(fadeAlpha * 0.5f));
        g.strokePath(spinnerArc, juce::PathStrokeType(6.0f, juce::PathStrokeType::curved,
                                                       juce::PathStrokeType::rounded));
    }
}

void ProgressOverlay::resized()
{
    auto bounds = getLocalBounds();
    auto centerX = bounds.getCentreX();
    auto centerY = bounds.getCentreY();
    
    // Card content area
    auto cardBounds = juce::Rectangle<int>(300, 280).withCentre({ centerX, centerY });
    auto contentArea = cardBounds.reduced(20);
    
    // Title at top of card
    titleLabel.setBounds(contentArea.removeFromTop(30).withY(cardBounds.getY() + 15));
    
    // Percent label in center (overlaid on ring)
    percentLabel.setBounds(juce::Rectangle<int>(100, 60).withCentre({ centerX, centerY - 40 }));
    
    // Step label below ring
    stepLabel.setBounds(juce::Rectangle<int>(260, 22).withCentre({ centerX, centerY + 32 }));
    detailLabel.setBounds(juce::Rectangle<int>(260, 18).withCentre({ centerX, centerY + 56 }));
    
    // Cancel button at bottom
    cancelButton.setBounds(juce::Rectangle<int>(100, 32).withCentre({ centerX, cardBounds.getBottom() - 35 }));
}

//==============================================================================
void ProgressOverlay::show()
{
    currentProgress = 0.0;
    currentStep = "Initializing...";
    currentDetail = "";
    lastProgressSeconds = 0.0;
    stepLabel.setText(currentStep, juce::dontSendNotification);
    stepLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    detailLabel.setText("", juce::dontSendNotification);
    percentLabel.setText("0%", juce::dontSendNotification);
    cancelButton.setEnabled(true);
    startTimeSeconds = juce::Time::getCurrentTime().toMilliseconds() / 1000.0;
    
    fadeAlpha = 0.0f;
    fadingIn = true;
    fadingOut = false;
    
    setVisible(true);
    toFront(true);
    startTimerHz(60);
}

void ProgressOverlay::hide()
{
    fadingIn = false;
    fadingOut = true;
    // Re-enable cancel button for next time
    cancelButton.setEnabled(true);
}

//==============================================================================
void ProgressOverlay::onGenerationStarted()
{
    juce::MessageManager::callAsync([this] {
        show();
    });
}

void ProgressOverlay::onGenerationProgress(const GenerationProgress& progress)
{
    juce::MessageManager::callAsync([this, progress] {
        currentProgress = progress.progress;
        currentStep = progress.stepName.isNotEmpty() ? progress.stepName : "Working...";
        currentDetail = progress.message;
        lastProgressSeconds = juce::Time::getCurrentTime().toMilliseconds() / 1000.0;
        
        stepLabel.setText(currentStep, juce::dontSendNotification);
        detailLabel.setText(currentDetail, juce::dontSendNotification);
        const int pct = (int)(currentProgress * 100.0);
        percentLabel.setText(juce::String(pct) + "%", juce::dontSendNotification);
        repaint();
    });
}

void ProgressOverlay::onGenerationCompleted(const juce::File& /*outputFile*/)
{
    juce::MessageManager::callAsync([this] {
        currentProgress = 1.0;
        stepLabel.setText("Complete!", juce::dontSendNotification);
        detailLabel.setText("", juce::dontSendNotification);
        percentLabel.setText("100%", juce::dontSendNotification);
        
        // Delay hide for visual feedback
        juce::Timer::callAfterDelay(500, [this] {
            hide();
        });
    });
}

void ProgressOverlay::onGenerationError(const juce::String& error)
{
    juce::MessageManager::callAsync([this, error] {
        stepLabel.setText("Error: " + error, juce::dontSendNotification);
        detailLabel.setText("", juce::dontSendNotification);
        stepLabel.setColour(juce::Label::textColourId, AppColours::error);
        
        // Delay hide for user to see error
        juce::Timer::callAfterDelay(2000, [this] {
            hide();
            stepLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
        });
    });
}

void ProgressOverlay::onConnectionStatusChanged(bool /*connected*/)
{
    // Not used in overlay
}

//==============================================================================
void ProgressOverlay::timerCallback()
{
    // Spinner animation
    spinnerAngle += 0.1f;
    if (spinnerAngle > juce::MathConstants<float>::twoPi)
        spinnerAngle -= juce::MathConstants<float>::twoPi;
    
    // Fade animation
    if (fadingIn)
    {
        fadeAlpha += 0.1f;
        if (fadeAlpha >= 1.0f)
        {
            fadeAlpha = 1.0f;
            fadingIn = false;
        }
    }
    else if (fadingOut)
    {
        fadeAlpha -= 0.1f;
        if (fadeAlpha <= 0.0f)
        {
            fadeAlpha = 0.0f;
            fadingOut = false;
            setVisible(false);
            stopTimer();
        }
    }

    if (isVisible() && !fadingOut)
    {
        const auto nowSeconds = juce::Time::getCurrentTime().toMilliseconds() / 1000.0;
        const auto totalElapsed = (startTimeSeconds > 0.0) ? (nowSeconds - startTimeSeconds) : 0.0;
        const auto sinceProgress = (lastProgressSeconds > 0.0) ? (nowSeconds - lastProgressSeconds) : totalElapsed;

        if (currentStep.containsIgnoreCase("render") && sinceProgress > 5.0)
        {
            const int mins = (int)(totalElapsed / 60.0);
            const int secs = (int)totalElapsed % 60;
            juce::String elapsed = juce::String::formatted("%d:%02d", mins, secs);
            detailLabel.setText(currentDetail + " (elapsed " + elapsed + ")", juce::dontSendNotification);
        }
    }

    repaint();
}

//==============================================================================
void ProgressOverlay::addListener(Listener* listener)
{
    listeners.add(listener);
}

void ProgressOverlay::removeListener(Listener* listener)
{
    listeners.remove(listener);
}
