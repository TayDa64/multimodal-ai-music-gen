/*
  ==============================================================================

    AppLookAndFeel.cpp
    
    Implementation of custom look and feel.

  ==============================================================================
*/

#include "AppLookAndFeel.h"
#include "ColourScheme.h"

//==============================================================================
AppLookAndFeel::AppLookAndFeel()
{
    // Set colour scheme
    setColour(juce::ResizableWindow::backgroundColourId, AppColours::background);
    setColour(juce::DocumentWindow::textColourId, AppColours::textPrimary);
    
    // Text button
    setColour(juce::TextButton::buttonColourId, AppColours::buttonBg);
    setColour(juce::TextButton::buttonOnColourId, AppColours::primary);
    setColour(juce::TextButton::textColourOffId, AppColours::textPrimary);
    setColour(juce::TextButton::textColourOnId, AppColours::textPrimary);
    
    // Text editor
    setColour(juce::TextEditor::backgroundColourId, AppColours::inputBg);
    setColour(juce::TextEditor::textColourId, AppColours::textPrimary);
    setColour(juce::TextEditor::highlightColourId, AppColours::primary.withAlpha(0.4f));
    setColour(juce::TextEditor::highlightedTextColourId, AppColours::textPrimary);
    setColour(juce::TextEditor::outlineColourId, AppColours::inputBorder);
    setColour(juce::TextEditor::focusedOutlineColourId, AppColours::primary);
    setColour(juce::CaretComponent::caretColourId, AppColours::primary);
    
    // Label
    setColour(juce::Label::textColourId, AppColours::textPrimary);
    setColour(juce::Label::backgroundColourId, juce::Colours::transparentBlack);
    
    // Slider
    setColour(juce::Slider::backgroundColourId, AppColours::surfaceAlt);
    setColour(juce::Slider::thumbColourId, AppColours::primary);
    setColour(juce::Slider::trackColourId, AppColours::primary);
    setColour(juce::Slider::textBoxTextColourId, AppColours::textPrimary);
    setColour(juce::Slider::textBoxBackgroundColourId, AppColours::inputBg);
    setColour(juce::Slider::textBoxOutlineColourId, AppColours::inputBorder);
    
    // Progress bar
    setColour(juce::ProgressBar::backgroundColourId, AppColours::surfaceAlt);
    setColour(juce::ProgressBar::foregroundColourId, AppColours::primary);
    
    // Popup menu
    setColour(juce::PopupMenu::backgroundColourId, AppColours::surface);
    setColour(juce::PopupMenu::textColourId, AppColours::textPrimary);
    setColour(juce::PopupMenu::highlightedBackgroundColourId, AppColours::primary);
    setColour(juce::PopupMenu::highlightedTextColourId, AppColours::textPrimary);
    
    // Combo box
    setColour(juce::ComboBox::backgroundColourId, AppColours::inputBg);
    setColour(juce::ComboBox::textColourId, AppColours::textPrimary);
    setColour(juce::ComboBox::outlineColourId, AppColours::inputBorder);
    setColour(juce::ComboBox::arrowColourId, AppColours::textSecondary);
    
    // Scroll bar
    setColour(juce::ScrollBar::thumbColourId, AppColours::textSecondary.withAlpha(0.4f));
    setColour(juce::ScrollBar::backgroundColourId, juce::Colours::transparentBlack);
    
    // Alert window
    setColour(juce::AlertWindow::backgroundColourId, AppColours::surface);
    setColour(juce::AlertWindow::textColourId, AppColours::textPrimary);
    setColour(juce::AlertWindow::outlineColourId, AppColours::border);
}

//==============================================================================
void AppLookAndFeel::drawButtonBackground(juce::Graphics& g, juce::Button& button,
                                         const juce::Colour& backgroundColour,
                                         bool shouldDrawButtonAsHighlighted,
                                         bool shouldDrawButtonAsDown)
{
    auto bounds = button.getLocalBounds().toFloat().reduced(0.5f, 0.5f);
    auto cornerSize = 4.0f;
    
    juce::Colour baseColour = backgroundColour;
    
    if (shouldDrawButtonAsDown)
        baseColour = AppColours::buttonPressed;
    else if (shouldDrawButtonAsHighlighted)
        baseColour = AppColours::buttonHover;
    
    // Background
    g.setColour(baseColour);
    g.fillRoundedRectangle(bounds, cornerSize);
    
    // Border
    g.setColour(AppColours::border);
    g.drawRoundedRectangle(bounds, cornerSize, 1.0f);
}

void AppLookAndFeel::drawButtonText(juce::Graphics& g, juce::TextButton& button,
                                   bool shouldDrawButtonAsHighlighted,
                                   bool shouldDrawButtonAsDown)
{
    auto font = getTextButtonFont(button, button.getHeight());
    g.setFont(font);
    
    auto textColour = button.findColour(button.getToggleState() 
        ? juce::TextButton::textColourOnId 
        : juce::TextButton::textColourOffId);
    
    if (!button.isEnabled())
        textColour = AppColours::textDisabled;
    
    g.setColour(textColour);
    
    auto bounds = button.getLocalBounds().reduced(4, 0);
    g.drawText(button.getButtonText(), bounds, juce::Justification::centred);
}

//==============================================================================
void AppLookAndFeel::fillTextEditorBackground(juce::Graphics& g, int width, int height,
                                             juce::TextEditor& editor)
{
    auto bounds = juce::Rectangle<float>(0, 0, (float)width, (float)height);
    g.setColour(editor.findColour(juce::TextEditor::backgroundColourId));
    g.fillRoundedRectangle(bounds, 4.0f);
}

void AppLookAndFeel::drawTextEditorOutline(juce::Graphics& g, int width, int height,
                                          juce::TextEditor& editor)
{
    auto bounds = juce::Rectangle<float>(0.5f, 0.5f, width - 1.0f, height - 1.0f);
    
    auto outlineColour = editor.hasKeyboardFocus(true)
        ? editor.findColour(juce::TextEditor::focusedOutlineColourId)
        : editor.findColour(juce::TextEditor::outlineColourId);
    
    g.setColour(outlineColour);
    g.drawRoundedRectangle(bounds, 4.0f, 1.0f);
}

//==============================================================================
void AppLookAndFeel::drawLinearSlider(juce::Graphics& g, int x, int y, int width, int height,
                                     float sliderPos, float minSliderPos, float maxSliderPos,
                                     const juce::Slider::SliderStyle style, juce::Slider& slider)
{
    auto trackWidth = juce::jmin(6.0f, slider.isHorizontal() ? (float)height * 0.25f : (float)width * 0.25f);
    
    juce::Point<float> startPoint(slider.isHorizontal() ? (float)x : (float)x + (float)width * 0.5f,
                                 slider.isHorizontal() ? (float)y + (float)height * 0.5f : (float)(height + y));
    
    juce::Point<float> endPoint(slider.isHorizontal() ? (float)(width + x) : startPoint.x,
                               slider.isHorizontal() ? startPoint.y : (float)y);
    
    // Background track
    juce::Path backgroundTrack;
    backgroundTrack.startNewSubPath(startPoint);
    backgroundTrack.lineTo(endPoint);
    g.setColour(AppColours::surfaceAlt);
    g.strokePath(backgroundTrack, { trackWidth, juce::PathStrokeType::curved, juce::PathStrokeType::rounded });
    
    // Value track
    juce::Path valueTrack;
    juce::Point<float> thumbPoint(slider.isHorizontal() ? sliderPos : ((float)x + (float)width * 0.5f),
                                 slider.isHorizontal() ? ((float)y + (float)height * 0.5f) : sliderPos);
    
    valueTrack.startNewSubPath(startPoint);
    valueTrack.lineTo(thumbPoint);
    g.setColour(AppColours::primary);
    g.strokePath(valueTrack, { trackWidth, juce::PathStrokeType::curved, juce::PathStrokeType::rounded });
    
    // Thumb
    auto thumbWidth = slider.isHorizontal() ? trackWidth * 2.0f : (float)width;
    auto thumbHeight = slider.isHorizontal() ? (float)height : trackWidth * 2.0f;
    
    g.setColour(AppColours::primary);
    g.fillEllipse(juce::Rectangle<float>(thumbWidth, thumbWidth).withCentre(thumbPoint));
    
    g.setColour(AppColours::textPrimary);
    g.drawEllipse(juce::Rectangle<float>(thumbWidth, thumbWidth).withCentre(thumbPoint), 1.0f);
}

void AppLookAndFeel::drawRotarySlider(juce::Graphics& g, int x, int y, int width, int height,
                                     float sliderPosProportional, float rotaryStartAngle,
                                     float rotaryEndAngle, juce::Slider& slider)
{
    auto radius = (float)juce::jmin(width / 2, height / 2) - 4.0f;
    auto centreX = (float)x + (float)width * 0.5f;
    auto centreY = (float)y + (float)height * 0.5f;
    auto rx = centreX - radius;
    auto ry = centreY - radius;
    auto rw = radius * 2.0f;
    auto angle = rotaryStartAngle + sliderPosProportional * (rotaryEndAngle - rotaryStartAngle);
    
    // Background
    g.setColour(AppColours::surfaceAlt);
    g.fillEllipse(rx, ry, rw, rw);
    
    // Arc
    juce::Path arc;
    arc.addCentredArc(centreX, centreY, radius - 2.0f, radius - 2.0f, 0.0f,
                     rotaryStartAngle, angle, true);
    
    g.setColour(AppColours::primary);
    g.strokePath(arc, juce::PathStrokeType(3.0f, juce::PathStrokeType::curved, juce::PathStrokeType::rounded));
    
    // Pointer
    juce::Path pointer;
    auto pointerLength = radius * 0.6f;
    auto pointerThickness = 3.0f;
    pointer.addRectangle(-pointerThickness * 0.5f, -radius + 4.0f, pointerThickness, pointerLength);
    pointer.applyTransform(juce::AffineTransform::rotation(angle).translated(centreX, centreY));
    
    g.setColour(AppColours::textPrimary);
    g.fillPath(pointer);
}

//==============================================================================
void AppLookAndFeel::drawProgressBar(juce::Graphics& g, juce::ProgressBar& bar,
                                    int width, int height, double progress,
                                    const juce::String& textToShow)
{
    auto background = bar.findColour(juce::ProgressBar::backgroundColourId);
    auto foreground = bar.findColour(juce::ProgressBar::foregroundColourId);
    
    auto bounds = bar.getLocalBounds().toFloat();
    auto cornerSize = 4.0f;
    
    // Background
    g.setColour(background);
    g.fillRoundedRectangle(bounds, cornerSize);
    
    // Progress
    if (progress >= 0.0f && progress <= 1.0f)
    {
        auto progressBounds = bounds.withWidth(bounds.getWidth() * (float)progress);
        g.setColour(foreground);
        g.fillRoundedRectangle(progressBounds, cornerSize);
    }
    else
    {
        // Indeterminate - animate
        auto pos = (float)std::fmod(juce::Time::getMillisecondCounter() / 1000.0, 1.0);
        auto barWidth = bounds.getWidth() * 0.3f;
        auto barX = bounds.getX() + pos * (bounds.getWidth() + barWidth) - barWidth;
        
        g.setColour(foreground);
        g.fillRoundedRectangle(barX, bounds.getY(), barWidth, bounds.getHeight(), cornerSize);
    }
    
    // Text
    if (textToShow.isNotEmpty())
    {
        g.setColour(AppColours::textPrimary);
        g.setFont(height * 0.6f);
        g.drawText(textToShow, bounds, juce::Justification::centred, false);
    }
}

//==============================================================================
void AppLookAndFeel::drawLabel(juce::Graphics& g, juce::Label& label)
{
    g.fillAll(label.findColour(juce::Label::backgroundColourId));
    
    if (!label.isBeingEdited())
    {
        auto textArea = getLabelBorderSize(label).subtractedFrom(label.getLocalBounds());
        
        g.setColour(label.findColour(juce::Label::textColourId));
        g.setFont(getLabelFont(label));
        
        g.drawFittedText(label.getText(), textArea, label.getJustificationType(),
                        juce::jmax(1, (int)(textArea.getHeight() / label.getFont().getHeight())),
                        label.getMinimumHorizontalScale());
    }
}

//==============================================================================
void AppLookAndFeel::drawPopupMenuBackground(juce::Graphics& g, int width, int height)
{
    g.fillAll(AppColours::surface);
    g.setColour(AppColours::border);
    g.drawRect(0, 0, width, height, 1);
}

void AppLookAndFeel::drawPopupMenuItem(juce::Graphics& g, const juce::Rectangle<int>& area,
                                      bool isSeparator, bool isActive, bool isHighlighted,
                                      bool isTicked, bool hasSubMenu,
                                      const juce::String& text, const juce::String& shortcutKeyText,
                                      const juce::Drawable* icon, const juce::Colour* textColour)
{
    if (isSeparator)
    {
        auto r = area.reduced(5, 0);
        r.removeFromTop(r.getHeight() / 2 - 1);
        
        g.setColour(AppColours::separator);
        g.fillRect(r.removeFromTop(1));
    }
    else
    {
        auto textArea = area.reduced(8, 0);
        
        if (isHighlighted && isActive)
        {
            g.setColour(AppColours::primary);
            g.fillRect(area);
        }
        
        g.setColour(isActive ? (isHighlighted ? AppColours::textPrimary : AppColours::textPrimary)
                            : AppColours::textDisabled);
        
        auto font = getPopupMenuFont();
        g.setFont(font);
        
        if (hasSubMenu)
        {
            auto arrowH = 0.6f * font.getAscent();
            auto x = (float)area.getRight() - 8.0f - arrowH;
            auto y = (float)area.getCentreY() - arrowH * 0.5f;
            
            juce::Path path;
            path.startNewSubPath(x, y);
            path.lineTo(x + arrowH * 0.6f, y + arrowH * 0.5f);
            path.lineTo(x, y + arrowH);
            
            g.strokePath(path, juce::PathStrokeType(2.0f));
        }
        
        if (isTicked)
        {
            auto tickWidth = area.getHeight() * 0.7f;
            auto tickArea = area.withWidth((int)tickWidth);
            g.drawText(juce::String::charToString(0x2713), tickArea, 
                      juce::Justification::centred);
        }
        
        g.drawFittedText(text, textArea, juce::Justification::centredLeft, 1);
        
        if (shortcutKeyText.isNotEmpty())
        {
            g.setColour(AppColours::textSecondary);
            g.drawText(shortcutKeyText, textArea, juce::Justification::centredRight);
        }
    }
}
