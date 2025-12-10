/*
  ==============================================================================

    ColourScheme.h
    
    Application colour palette and theme definitions.

  ==============================================================================
*/

#pragma once

#include <JuceHeader.h>

//==============================================================================
/**
    Application colour scheme.
    
    Dark theme inspired by professional audio software.
*/
namespace ColourScheme
{
    // Background colours
    static const juce::Colour background      { 0xFF1E1E1E };  // Main background
    static const juce::Colour surface         { 0xFF252526 };  // Panel backgrounds
    static const juce::Colour surfaceAlt      { 0xFF2D2D30 };  // Alternate surfaces
    static const juce::Colour surfaceHighlight{ 0xFF3E3E42 };  // Hovered elements
    
    // Accent colours
    static const juce::Colour primary         { 0xFF007ACC };  // Primary accent (blue)
    static const juce::Colour primaryDark     { 0xFF005A9E };  // Darker variant
    static const juce::Colour primaryLight    { 0xFF1E90FF };  // Lighter variant
    
    static const juce::Colour secondary       { 0xFF9B59B6 };  // Secondary (purple)
    static const juce::Colour accent          { 0xFFE67E22 };  // Accent (orange)
    
    // Text colours
    static const juce::Colour textPrimary     { 0xFFCCCCCC };  // Primary text
    static const juce::Colour textSecondary   { 0xFF858585 };  // Secondary text
    static const juce::Colour textDisabled    { 0xFF5A5A5A };  // Disabled text
    
    // State colours
    static const juce::Colour success         { 0xFF4CAF50 };  // Success/green
    static const juce::Colour warning         { 0xFFFFC107 };  // Warning/yellow
    static const juce::Colour error           { 0xFFF44336 };  // Error/red
    static const juce::Colour info            { 0xFF2196F3 };  // Info/blue
    
    // Border and separator
    static const juce::Colour border          { 0xFF3F3F46 };  // Borders
    static const juce::Colour separator       { 0xFF2D2D30 };  // Separators
    
    // Interactive elements
    static const juce::Colour buttonBg        { 0xFF3E3E42 };  // Button background
    static const juce::Colour buttonHover     { 0xFF505050 };  // Button hover
    static const juce::Colour buttonPressed   { 0xFF1E1E1E };  // Button pressed
    
    // Input fields
    static const juce::Colour inputBg         { 0xFF3C3C3C };  // Input background
    static const juce::Colour inputBorder     { 0xFF5A5A5A };  // Input border
    static const juce::Colour inputFocus      { 0xFF007ACC };  // Input focus border
    
    // Playback colours
    static const juce::Colour playhead        { 0xFFFFFFFF };  // Playhead line
    static const juce::Colour waveformFg      { 0xFF007ACC };  // Waveform foreground
    static const juce::Colour waveformBg      { 0xFF1A1A2E };  // Waveform background
    
    // Piano roll colours
    static const juce::Colour noteDefault     { 0xFF4FC3F7 };  // Default note colour
    static const juce::Colour noteDrums       { 0xFFEF5350 };  // Drum notes
    static const juce::Colour noteBass        { 0xFF66BB6A };  // Bass notes
    static const juce::Colour noteMelody      { 0xFFFFB74D };  // Melody notes
    static const juce::Colour noteChord       { 0xFFAB47BC };  // Chord notes
    
    // Genre-specific themes (for future use)
    namespace GFunk
    {
        static const juce::Colour primary     { 0xFF9B59B6 };  // Purple
        static const juce::Colour secondary   { 0xFF2ECC71 };  // Green
        static const juce::Colour accent      { 0xFFF1C40F };  // Gold
    }
    
    namespace Trap
    {
        static const juce::Colour primary     { 0xFFE74C3C };  // Red
        static const juce::Colour secondary   { 0xFF1A1A1A };  // Black
        static const juce::Colour accent      { 0xFFFFFFFF };  // White
    }
    
    namespace LoFi
    {
        static const juce::Colour primary     { 0xFFE67E22 };  // Orange
        static const juce::Colour secondary   { 0xFF8B4513 };  // Brown
        static const juce::Colour accent      { 0xFFFFF8DC };  // Cream
    }
    
    namespace BoomBap
    {
        static const juce::Colour primary     { 0xFFDAA520 };  // Gold
        static const juce::Colour secondary   { 0xFF8B4513 };  // Brown
        static const juce::Colour accent      { 0xFF1A1A1A };  // Black
    }
}
