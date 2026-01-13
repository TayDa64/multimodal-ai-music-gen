/*
  ==============================================================================

    ControlsWindow.h

    Floating window wrapper for ControlsPanel.

  ==============================================================================
*/

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include "ControlsPanel.h"

class ControlsWindow : public juce::DocumentWindow
{
public:
    explicit ControlsWindow();

    void closeButtonPressed() override;

    ControlsPanel* getControlsPanel() const;
};
