/*
  ==============================================================================

    ColourScheme.h
    
    Application colour palette and theme definitions.

  ==============================================================================
*/

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>

//==============================================================================
/**
    Application colour scheme.
    
    Dark theme inspired by professional audio software.
    Using inline to prevent static initialization order issues.
*/
namespace AppColours
{
    // Background colours
    inline const juce::Colour background      { 0xFF1E1E1E };  // Main background
    inline const juce::Colour surface         { 0xFF252526 };  // Panel backgrounds
    inline const juce::Colour surfaceAlt      { 0xFF2D2D30 };  // Alternate surfaces
    inline const juce::Colour surfaceHighlight{ 0xFF3E3E42 };  // Hovered elements
    inline const juce::Colour surfaceRaised   { 0xFF303036 };  // Elevated/card surfaces
    inline const juce::Colour surfaceSunken   { 0xFF1A1A1F };  // Recessed list/waveform wells
    
    // Accent colours
    inline const juce::Colour primary         { 0xFF007ACC };  // Primary accent (blue)
    inline const juce::Colour primaryDark     { 0xFF005A9E };  // Darker variant
    inline const juce::Colour primaryLight    { 0xFF1E90FF };  // Lighter variant
    
    inline const juce::Colour secondary       { 0xFF9B59B6 };  // Secondary (purple)
    inline const juce::Colour accent          { 0xFFE67E22 };  // Accent (orange)
    inline const juce::Colour mpcAccent       { 0xFF00D4AA };  // MPC-inspired central cyan/green accent
    inline const juce::Colour mpcAccentStrong { 0xFF18F0C8 };  // Brighter accent for selected control edges
    inline const juce::Colour mpcAmber        { 0xFFFFB74D };  // Warm pad/control highlight
    
    // Text colours
    inline const juce::Colour textPrimary     { 0xFFCCCCCC };  // Primary text
    inline const juce::Colour textSecondary   { 0xFF858585 };  // Secondary text
    inline const juce::Colour textDisabled    { 0xFF5A5A5A };  // Disabled text
    
    // State colours
    inline const juce::Colour success         { 0xFF4CAF50 };  // Success/green
    inline const juce::Colour warning         { 0xFFFFC107 };  // Warning/yellow
    inline const juce::Colour error           { 0xFFF44336 };  // Error/red
    inline const juce::Colour info            { 0xFF2196F3 };  // Info/blue
    
    // Border and separator
    inline const juce::Colour border          { 0xFF3F3F46 };  // Borders
    inline const juce::Colour separator       { 0xFF2D2D30 };  // Separators
    inline const juce::Colour borderSubtle    { 0xFF34343A };  // Low-contrast borders
    inline const juce::Colour focusRing       { 0xFF4FC3F7 };  // Keyboard/control focus ring
    
    // Interactive elements
    inline const juce::Colour buttonBg        { 0xFF3E3E42 };  // Button background
    inline const juce::Colour buttonHover     { 0xFF505050 };  // Button hover
    inline const juce::Colour buttonPressed   { 0xFF1E1E1E };  // Button pressed
    inline const juce::Colour mpcControlBg    { 0xFF16171B };  // Compact bordered MPC control well
    inline const juce::Colour mpcControlRaised{ 0xFF24262C };  // Compact raised control surface
    inline const juce::Colour mpcControlBorder{ 0xFF4A4D55 };  // High-contrast compact control border
    inline const juce::Colour rowHover        { 0xFF34343C };  // List/card hover state
    inline const juce::Colour rowSelected     { 0xFF263B54 };  // Selected list/card state
    inline const juce::Colour rowSelectedEdge { 0xFF5DADE2 };  // Selected row outline
    inline const juce::Colour badgeBg         { 0x332196F3 };  // Compact metadata badges
    inline const juce::Colour badgeBorder     { 0x664FC3F7 };  // Compact metadata badge outline
    
    // Input fields
    inline const juce::Colour inputBg         { 0xFF3C3C3C };  // Input background
    inline const juce::Colour inputBorder     { 0xFF5A5A5A };  // Input border
    inline const juce::Colour inputFocus      { 0xFF007ACC };  // Input focus border
    
    // Playback colours
    inline const juce::Colour playhead        { 0xFFFFFFFF };  // Playhead line
    inline const juce::Colour waveformFg      { 0xFF007ACC };  // Waveform foreground
    inline const juce::Colour waveformBg      { 0xFF1A1A2E };  // Waveform background

    // Instrument/category accents
    inline const juce::Colour categoryDrums    { 0xFFFF6B6B };
    inline const juce::Colour categoryBass     { 0xFF5DADE2 };
    inline const juce::Colour categoryGuitar   { 0xFFFFB74D };
    inline const juce::Colour categoryKeys     { 0xFFFFD166 };
    inline const juce::Colour categorySynths   { 0xFFB388FF };
    inline const juce::Colour categoryStrings  { 0xFF66BB6A };
    inline const juce::Colour categoryFx       { 0xFFF48FB1 };
    inline const juce::Colour categoryEthiopian{ 0xFF2ECC71 };
    inline const juce::Colour categoryDefault  { 0xFF8A8F98 };
    
    // Piano roll colours
    inline const juce::Colour noteDefault     { 0xFF4FC3F7 };  // Default note colour
    inline const juce::Colour noteDrums       { 0xFFEF5350 };  // Drum notes
    inline const juce::Colour noteBass        { 0xFF66BB6A };  // Bass notes
    inline const juce::Colour noteMelody      { 0xFFFFB74D };  // Melody notes
    inline const juce::Colour noteChord       { 0xFFAB47BC };  // Chord notes
    
    // Genre-specific themes (for future use)
    namespace GFunk
    {
        inline const juce::Colour primary     { 0xFF9B59B6 };  // Purple
        inline const juce::Colour secondary   { 0xFF2ECC71 };  // Green
        inline const juce::Colour accent      { 0xFFF1C40F };  // Gold
    }
    
    namespace Trap
    {
        inline const juce::Colour primary     { 0xFFE74C3C };  // Red
        inline const juce::Colour secondary   { 0xFF1A1A1A };  // Black
        inline const juce::Colour accent      { 0xFFFFFFFF };  // White
    }
    
    namespace LoFi
    {
        inline const juce::Colour primary     { 0xFFE67E22 };  // Orange
        inline const juce::Colour secondary   { 0xFF8B4513 };  // Brown
        inline const juce::Colour accent      { 0xFFFFF8DC };  // Cream
    }
    
    namespace BoomBap
    {
        inline const juce::Colour primary     { 0xFFDAA520 };  // Gold
        inline const juce::Colour secondary   { 0xFF8B4513 };  // Brown
        inline const juce::Colour accent      { 0xFF1A1A1A };  // Black
    }

    namespace Rock
    {
        inline const juce::Colour primary     { 0xFFFF7043 };  // Amplifier orange
        inline const juce::Colour secondary   { 0xFF37474F };  // Charcoal blue-grey
        inline const juce::Colour accent      { 0xFFFFCA28 };  // Stage amber
    }
}
