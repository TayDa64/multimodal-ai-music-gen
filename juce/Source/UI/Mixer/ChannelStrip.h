#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include <juce_graphics/juce_graphics.h>
#include "LevelMeter.h"

namespace UI
{
    class ChannelStrip : public juce::Component
    {
    public:
        ChannelStrip(const juce::String& trackName);
        ~ChannelStrip() override;

        void paint(juce::Graphics& g) override;
        void resized() override;
        void mouseDown(const juce::MouseEvent& event) override;

        // Accessors for attachments
        juce::Slider& getVolumeSlider() { return volumeSlider; }
        juce::Slider& getPanSlider() { return panSlider; }
        juce::Slider& getWidthSlider() { return widthSlider; }
        juce::ToggleButton& getMuteButton() { return muteButton; }
        juce::ToggleButton& getSoloButton() { return soloButton; }
        
        void updateLevel(float level);
        
        void setName(const juce::String& newName);
        
        void setSelected(bool selected);
        bool isSelected() const { return selected; }
        
        std::function<void()> onSelectionChange;

    private:
        juce::Label nameLabel;
        juce::Slider volumeSlider;
        juce::Slider panSlider;
        juce::Slider widthSlider;
        juce::ToggleButton muteButton;
        juce::ToggleButton soloButton;
        LevelMeter levelMeter;
        
        bool selected = false;

        JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(ChannelStrip)
    };
}
