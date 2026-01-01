/*
  ==============================================================================

    Command.h
    
    Base class for undoable commands in the application.
    Wraps juce::UndoableAction.

  ==============================================================================
*/

#pragma once

#include <juce_core/juce_core.h>
#include <juce_data_structures/juce_data_structures.h>

namespace Project
{
    class Command : public juce::UndoableAction
    {
    public:
        Command(const juce::String& name) : commandName(name) {}
        ~Command() override = default;

        bool perform() override = 0;
        bool undo() override = 0;
        
        int getSizeInUnits() override { return 10; } // Approximate memory usage

    protected:
        juce::String commandName;
    };
}
