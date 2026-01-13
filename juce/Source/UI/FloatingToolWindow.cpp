/*
  ==============================================================================

    FloatingToolWindow.cpp

  ==============================================================================
*/

#include "FloatingToolWindow.h"

FloatingToolWindow::FloatingToolWindow(const juce::String& title,
                                       juce::Colour backgroundColour,
                                       juce::Component* content)
    : juce::DocumentWindow(title, backgroundColour, juce::DocumentWindow::allButtons)
{
    setUsingNativeTitleBar(true);
    setResizable(true, false);

    // Content is owned elsewhere (e.g., MainComponent unique_ptr), so do NOT take ownership.
    setContentNonOwned(content, false);

    setVisible(false);
}

void FloatingToolWindow::closeButtonPressed()
{
    // Graceful exit: hide the tool window, keep app running.
    setVisible(false);
}
