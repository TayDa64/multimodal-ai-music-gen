#include "ChannelStrip.h"

namespace UI
{
    ChannelStrip::ChannelStrip(const juce::String& trackName)
    {
        // Name
        nameLabel.setText(trackName, juce::dontSendNotification);
        nameLabel.setJustificationType(juce::Justification::centred);
        nameLabel.setColour(juce::Label::textColourId, juce::Colours::white);
        nameLabel.setFont(12.0f);
        addAndMakeVisible(nameLabel);

        // Volume
        volumeSlider.setSliderStyle(juce::Slider::LinearVertical);
        volumeSlider.setTextBoxStyle(juce::Slider::NoTextBox, false, 0, 0);
        volumeSlider.setRange(0.0, 1.0); // Linear gain for now
        volumeSlider.setValue(0.8);
        volumeSlider.setColour(juce::Slider::thumbColourId, juce::Colours::white);
        volumeSlider.setColour(juce::Slider::trackColourId, juce::Colours::grey);
        volumeSlider.setColour(juce::Slider::backgroundColourId, juce::Colours::darkgrey);
        addAndMakeVisible(volumeSlider);

        // Pan
        panSlider.setSliderStyle(juce::Slider::RotaryHorizontalVerticalDrag);
        panSlider.setTextBoxStyle(juce::Slider::NoTextBox, false, 0, 0);
        panSlider.setRange(-1.0, 1.0);
        panSlider.setValue(0.0);
        panSlider.setColour(juce::Slider::rotarySliderFillColourId, juce::Colours::cyan);
        panSlider.setColour(juce::Slider::thumbColourId, juce::Colours::white);
        addAndMakeVisible(panSlider);

        // Mute/Solo
        muteButton.setButtonText("M");
        muteButton.setColour(juce::TextButton::buttonColourId, juce::Colours::darkgrey);
        muteButton.setColour(juce::TextButton::buttonOnColourId, juce::Colours::red);
        muteButton.setColour(juce::TextButton::textColourOnId, juce::Colours::white);
        
        soloButton.setButtonText("S");
        soloButton.setColour(juce::TextButton::buttonColourId, juce::Colours::darkgrey);
        soloButton.setColour(juce::TextButton::buttonOnColourId, juce::Colours::yellow);
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
        g.fillAll(juce::Colours::darkgrey.darker(0.2f));
        
        // Selection highlight
        if (selected)
        {
            g.setColour(juce::Colours::cyan.withAlpha(0.1f));
            g.fillRect(bounds);
            g.setColour(juce::Colours::cyan);
            g.drawRect(bounds, 2);
        }
        else
        {
            g.setColour(juce::Colours::black);
            g.drawRect(bounds, 1);
        }
        
        // Separator lines
        g.setColour(juce::Colours::black.withAlpha(0.5f));
        // Line below pan
        g.drawHorizontalLine(45, 5.0f, (float)getWidth() - 5.0f);
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
