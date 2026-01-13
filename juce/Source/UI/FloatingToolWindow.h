/*
  ==============================================================================

    FloatingToolWindow.h

    Simple reusable floating window that hides on close.
    Used for tool panels (Instruments, Expansions, etc.) without transferring
    ownership of the content component.

  ==============================================================================
*/

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>

class FloatingToolWindow : public juce::DocumentWindow
{
public:
    FloatingToolWindow(const juce::String& title,
                       juce::Colour backgroundColour,
                       juce::Component* content);

    void closeButtonPressed() override;
};
