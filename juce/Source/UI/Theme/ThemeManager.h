/*
  ==============================================================================

    ThemeManager.h
    
    Centralized theme management for the application.
    Provides a consistent colour scheme abstraction layer.

  ==============================================================================
*/

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include "ColourScheme.h"

//==============================================================================
/**
    Theme colour scheme structure for components.
*/
struct ThemeColourScheme
{
    juce::Colour background;
    juce::Colour windowBackground;
    juce::Colour panelBackground;
    juce::Colour text;
    juce::Colour textSecondary;
    juce::Colour accent;
    juce::Colour outline;
    juce::Colour success;
    juce::Colour warning;
    juce::Colour error;
};

//==============================================================================
/**
    Theme manager providing colour schemes and visual styling.
    
    Wraps AppColours for a consistent interface.
*/
class ThemeManager
{
public:
    //==========================================================================
    /** Get the current colour scheme. */
    static ThemeColourScheme getCurrentScheme()
    {
        return {
            AppColours::background,
            AppColours::surface,
            AppColours::surfaceAlt,
            AppColours::textPrimary,
            AppColours::textSecondary,
            AppColours::primary,
            AppColours::border,
            AppColours::success,
            AppColours::warning,
            AppColours::error
        };
    }
    
    //==========================================================================
    /** Get colour for a specific purpose. */
    static juce::Colour getBackground() { return AppColours::background; }
    static juce::Colour getSurface() { return AppColours::surface; }
    static juce::Colour getText() { return AppColours::textPrimary; }
    static juce::Colour getTextSecondary() { return AppColours::textSecondary; }
    static juce::Colour getAccent() { return AppColours::primary; }
    static juce::Colour getBorder() { return AppColours::border; }
    
private:
    ThemeManager() = delete;  // Static only
};

