#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include <juce_graphics/juce_graphics.h>
#include <juce_events/juce_events.h>

namespace UI
{
    class LevelMeter : public juce::Component,
                       public juce::Timer
    {
    public:
        LevelMeter();
        ~LevelMeter() override;

        void paint(juce::Graphics& g) override;
        void resized() override;
        void timerCallback() override;

        /**
         * Update the current level.
         * @param level Linear amplitude (0.0 to 1.0+)
         */
        void setLevel(float level);

    private:
        float currentLevel = 0.0f;
        float currentPeak = 0.0f;
        
        // Ballistics
        float decayRate = 0.05f; // per frame

        JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(LevelMeter)
    };
}
