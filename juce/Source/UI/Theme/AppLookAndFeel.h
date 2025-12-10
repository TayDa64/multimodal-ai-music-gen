/*
  ==============================================================================

    AppLookAndFeel.h
    
    Custom look and feel for the application.

  ==============================================================================
*/

#pragma once

#include <JuceHeader.h>

//==============================================================================
/**
    Custom look and feel for the AI Music Generator.
    
    Provides a dark, professional aesthetic suitable for audio applications.
*/
class AppLookAndFeel : public juce::LookAndFeel_V4
{
public:
    //==============================================================================
    AppLookAndFeel();
    ~AppLookAndFeel() override = default;
    
    //==============================================================================
    // Buttons
    void drawButtonBackground(juce::Graphics& g, juce::Button& button,
                             const juce::Colour& backgroundColour,
                             bool shouldDrawButtonAsHighlighted,
                             bool shouldDrawButtonAsDown) override;
    
    void drawButtonText(juce::Graphics& g, juce::TextButton& button,
                       bool shouldDrawButtonAsHighlighted,
                       bool shouldDrawButtonAsDown) override;
    
    //==============================================================================
    // Text editor
    void fillTextEditorBackground(juce::Graphics& g, int width, int height,
                                 juce::TextEditor& editor) override;
    
    void drawTextEditorOutline(juce::Graphics& g, int width, int height,
                              juce::TextEditor& editor) override;
    
    //==============================================================================
    // Sliders
    void drawLinearSlider(juce::Graphics& g, int x, int y, int width, int height,
                         float sliderPos, float minSliderPos, float maxSliderPos,
                         const juce::Slider::SliderStyle style,
                         juce::Slider& slider) override;
    
    void drawRotarySlider(juce::Graphics& g, int x, int y, int width, int height,
                         float sliderPosProportional, float rotaryStartAngle,
                         float rotaryEndAngle, juce::Slider& slider) override;
    
    //==============================================================================
    // Progress bar
    void drawProgressBar(juce::Graphics& g, juce::ProgressBar& bar,
                        int width, int height, double progress,
                        const juce::String& textToShow) override;
    
    //==============================================================================
    // Labels
    void drawLabel(juce::Graphics& g, juce::Label& label) override;
    
    //==============================================================================
    // Popup menu
    void drawPopupMenuBackground(juce::Graphics& g, int width, int height) override;
    
    void drawPopupMenuItem(juce::Graphics& g, const juce::Rectangle<int>& area,
                          bool isSeparator, bool isActive, bool isHighlighted,
                          bool isTicked, bool hasSubMenu,
                          const juce::String& text, const juce::String& shortcutKeyText,
                          const juce::Drawable* icon, const juce::Colour* textColour) override;

private:
    //==============================================================================
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(AppLookAndFeel)
};
