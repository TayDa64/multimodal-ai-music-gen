#include "ChannelStrip.h"
#include "../Theme/ColourScheme.h"

namespace UI
{
    ChannelStrip::ChannelStrip(const juce::String& trackName)
    {
        // Name
        nameLabel.setText(trackName, juce::dontSendNotification);
        nameLabel.setJustificationType(juce::Justification::centred);
        nameLabel.setColour(juce::Label::textColourId, AppColours::textPrimary);
        nameLabel.setFont(12.0f);
        addAndMakeVisible(nameLabel);

        // Volume
        volumeSlider.setSliderStyle(juce::Slider::LinearVertical);
        volumeSlider.setTextBoxStyle(juce::Slider::NoTextBox, false, 0, 0);
        volumeSlider.setRange(0.0, 1.0); // Linear gain for now
        volumeSlider.setValue(0.8);
        volumeSlider.setColour(juce::Slider::thumbColourId, AppColours::textPrimary);
        volumeSlider.setColour(juce::Slider::trackColourId, AppColours::primary.withAlpha(0.8f));
        volumeSlider.setColour(juce::Slider::backgroundColourId, AppColours::surface.darker(0.25f));
        addAndMakeVisible(volumeSlider);

        // Pan
        panSlider.setSliderStyle(juce::Slider::RotaryHorizontalVerticalDrag);
        panSlider.setTextBoxStyle(juce::Slider::NoTextBox, false, 0, 0);
        panSlider.setRange(-1.0, 1.0);
        panSlider.setValue(0.0);
        panSlider.setColour(juce::Slider::rotarySliderFillColourId, AppColours::accent);
        panSlider.setColour(juce::Slider::thumbColourId, AppColours::textPrimary);
        addAndMakeVisible(panSlider);

        // Width (stereo width control)
        widthSlider.setSliderStyle(juce::Slider::RotaryHorizontalVerticalDrag);
        widthSlider.setTextBoxStyle(juce::Slider::NoTextBox, false, 0, 0);
        widthSlider.setRange(0.0, 2.0);  // 0=mono, 1=normal, 2=extra wide
        widthSlider.setValue(1.0);       // Default: no change
        widthSlider.setColour(juce::Slider::rotarySliderFillColourId, AppColours::primary);
        widthSlider.setColour(juce::Slider::thumbColourId, AppColours::textPrimary);
        widthSlider.setTooltip("Stereo Width: 0% (mono) to 200% (extra wide)");
        addAndMakeVisible(widthSlider);

        // Mute/Solo
        muteButton.setButtonText("M");
        muteButton.setColour(juce::TextButton::buttonColourId, AppColours::surface.brighter(0.05f));
        muteButton.setColour(juce::TextButton::buttonOnColourId, AppColours::error);
        muteButton.setColour(juce::TextButton::textColourOnId, AppColours::textPrimary);
        
        soloButton.setButtonText("S");
        soloButton.setColour(juce::TextButton::buttonColourId, AppColours::surface.brighter(0.05f));
        soloButton.setColour(juce::TextButton::buttonOnColourId, AppColours::warning);
        soloButton.setColour(juce::TextButton::textColourOnId, juce::Colours::black);

        addAndMakeVisible(muteButton);
        addAndMakeVisible(soloButton);

        // Meter
        addAndMakeVisible(levelMeter);
    }

    ChannelStrip::~ChannelStrip()
    {
    }

    void ChannelStrip::paint(juce::Graphics& g)
    {
        auto bounds = getLocalBounds();
        
        // Background
        g.fillAll(AppColours::surface.darker(0.2f));
        
        // Selection highlight
        if (selected)
        {
            g.setColour(AppColours::accent.withAlpha(0.12f));
            g.fillRect(bounds);
            g.setColour(AppColours::accent);
            g.drawRect(bounds, 2);
        }
        else
        {
            g.setColour(AppColours::border);
            g.drawRect(bounds, 1);
        }
        
        // Separator lines
        g.setColour(AppColours::border.withAlpha(0.6f));
        // Line below width
        g.drawHorizontalLine(89, 5.0f, (float)getWidth() - 5.0f);
        // Line above name
        g.drawHorizontalLine(getHeight() - 25, 5.0f, (float)getWidth() - 5.0f);
    }

    void ChannelStrip::resized()
    {
        auto area = getLocalBounds().reduced(4);

        // Name at bottom
        nameLabel.setBounds(area.removeFromBottom(20));
        area.removeFromBottom(4); // Gap

        // Pan at top
        auto panArea = area.removeFromTop(40);
        panSlider.setBounds(panArea.withSizeKeepingCentre(36, 36));
        
        area.removeFromTop(4); // Gap

        // Width below pan
        auto widthArea = area.removeFromTop(40);
        widthSlider.setBounds(widthArea.withSizeKeepingCentre(36, 36));
        
        area.removeFromTop(4); // Gap

        // Mute/Solo
        auto buttonArea = area.removeFromTop(20);
        int buttonWidth = buttonArea.getWidth() / 2;
        muteButton.setBounds(buttonArea.removeFromLeft(buttonWidth).reduced(2, 0));
        soloButton.setBounds(buttonArea.reduced(2, 0));
        
        area.removeFromTop(8); // Gap

        // Meter and Fader
        // Meter on the right, 10px wide
        auto meterArea = area.removeFromRight(12);
        levelMeter.setBounds(meterArea.reduced(2, 0));
        
        area.removeFromRight(4); // Gap
        
        // Fader centered in remaining space
        // Restrict width to make it look like a fader, not a huge block
        volumeSlider.setBounds(area.withSizeKeepingCentre(juce::jmin(40, area.getWidth()), area.getHeight()));
    }

    void ChannelStrip::mouseDown(const juce::MouseEvent& event)
    {
        if (onSelectionChange)
            onSelectionChange();
    }

    void ChannelStrip::setSelected(bool isSelected)
    {
        if (selected != isSelected)
        {
            selected = isSelected;
            repaint();
        }
    }

    void ChannelStrip::updateLevel(float level)
    {
        levelMeter.setLevel(level);
    }

    void ChannelStrip::setName(const juce::String& newName)
    {
        nameLabel.setText(newName, juce::dontSendNotification);
    }
}
