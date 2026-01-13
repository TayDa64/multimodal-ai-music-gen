/*
  ==============================================================================

    ControlsWindow.cpp

  ==============================================================================
*/

#include "ControlsWindow.h"

ControlsWindow::ControlsWindow()
    : juce::DocumentWindow(
        "Controls",
        juce::Colours::black,
        juce::DocumentWindow::allButtons)
{
    setUsingNativeTitleBar(true);
    setResizable(true, false);

    auto* panel = new ControlsPanel();
    setContentOwned(panel, true);

    centreWithSize(520, 420);
    setVisible(false);
}

void ControlsWindow::closeButtonPressed()
{
    setVisible(false);
}

ControlsPanel* ControlsWindow::getControlsPanel() const
{
    return dynamic_cast<ControlsPanel*>(getContentComponent());
}
