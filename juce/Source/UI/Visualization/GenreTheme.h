/*
  ==============================================================================

    GenreTheme.h
    
    Genre-aware color themes for audio visualization.
    Provides cohesive color schemes that match the musical genre being played.
    
    Phase 7: Waveform & Spectrum Visualization

  ==============================================================================
*/

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>

//==============================================================================
/**
    Genre-specific color theme for visualizations.
    
    Each genre has a carefully curated palette that evokes the
    aesthetic of that musical style.
*/
struct GenreTheme
{
    juce::String name;
    
    // Primary colors
    juce::Colour primary;           // Main theme color
    juce::Colour secondary;         // Supporting color
    juce::Colour accent;            // Highlight/pop color
    
    // Waveform colors
    juce::Colour waveformFill;      // Waveform body fill
    juce::Colour waveformOutline;   // Waveform edge/outline
    juce::Colour waveformGlow;      // Glow effect color
    
    // Spectrum colors (gradient from low to high frequencies)
    juce::Colour spectrumLow;       // Bass frequencies (20-250Hz)
    juce::Colour spectrumMid;       // Mid frequencies (250Hz-4kHz)
    juce::Colour spectrumHigh;      // High frequencies (4kHz-20kHz)
    juce::Colour spectrumPeak;      // Peak indicators
    
    // Background
    juce::Colour background;        // Visualization background
    juce::Colour gridLines;         // Grid/reference lines
    
    //==========================================================================
    // Factory methods for predefined themes
    //==========================================================================
    
    /** Default theme - Professional blue/cyan */
    static GenreTheme defaultTheme()
    {
        return {
            "Default",
            // Primary palette
            juce::Colour(0xFF007ACC),   // primary - Blue
            juce::Colour(0xFF00D4FF),   // secondary - Cyan
            juce::Colour(0xFFFFFFFF),   // accent - White
            // Waveform
            juce::Colour(0xFF007ACC),   // waveformFill
            juce::Colour(0xFF00D4FF),   // waveformOutline
            juce::Colour(0x40007ACC),   // waveformGlow
            // Spectrum gradient
            juce::Colour(0xFF00D4FF),   // spectrumLow - Cyan
            juce::Colour(0xFF007ACC),   // spectrumMid - Blue
            juce::Colour(0xFF9B59B6),   // spectrumHigh - Purple
            juce::Colour(0xFFFFFFFF),   // spectrumPeak - White
            // Background
            juce::Colour(0xFF1A1A2E),   // background
            juce::Colour(0x30FFFFFF),   // gridLines
        };
    }
    
    /** G-Funk theme - Purple/Green/Gold (West Coast vibes) */
    static GenreTheme gFunk()
    {
        return {
            "G-Funk",
            // Primary palette
            juce::Colour(0xFF9B59B6),   // primary - Purple
            juce::Colour(0xFF2ECC71),   // secondary - Green
            juce::Colour(0xFFF1C40F),   // accent - Gold
            // Waveform
            juce::Colour(0xFF9B59B6),   // waveformFill - Purple
            juce::Colour(0xFF2ECC71),   // waveformOutline - Green
            juce::Colour(0x409B59B6),   // waveformGlow
            // Spectrum gradient (sunset palette)
            juce::Colour(0xFF2ECC71),   // spectrumLow - Green (bass)
            juce::Colour(0xFF9B59B6),   // spectrumMid - Purple (mids)
            juce::Colour(0xFFF1C40F),   // spectrumHigh - Gold (highs)
            juce::Colour(0xFFFFFFFF),   // spectrumPeak
            // Background
            juce::Colour(0xFF1A0A2E),   // background - Deep purple-black
            juce::Colour(0x309B59B6),   // gridLines
        };
    }
    
    /** Trap theme - Red/Black/White (Dark aggressive) */
    static GenreTheme trap()
    {
        return {
            "Trap",
            // Primary palette
            juce::Colour(0xFFE74C3C),   // primary - Red
            juce::Colour(0xFF1A1A1A),   // secondary - Black
            juce::Colour(0xFFFFFFFF),   // accent - White
            // Waveform
            juce::Colour(0xFFE74C3C),   // waveformFill - Red
            juce::Colour(0xFFFF6B6B),   // waveformOutline - Light red
            juce::Colour(0x60E74C3C),   // waveformGlow
            // Spectrum gradient (fire palette)
            juce::Colour(0xFFE74C3C),   // spectrumLow - Red (808s hit hard)
            juce::Colour(0xFFFF8C00),   // spectrumMid - Orange
            juce::Colour(0xFFFFFFFF),   // spectrumHigh - White
            juce::Colour(0xFFFFFF00),   // spectrumPeak - Yellow
            // Background
            juce::Colour(0xFF0D0D0D),   // background - Near black
            juce::Colour(0x20E74C3C),   // gridLines - Subtle red
        };
    }
    
    /** Lo-Fi theme - Orange/Brown/Cream (Warm vintage) */
    static GenreTheme lofi()
    {
        return {
            "Lo-Fi",
            // Primary palette
            juce::Colour(0xFFE67E22),   // primary - Orange
            juce::Colour(0xFF8B4513),   // secondary - Brown
            juce::Colour(0xFFFFF8DC),   // accent - Cream
            // Waveform
            juce::Colour(0xFFE67E22),   // waveformFill - Warm orange
            juce::Colour(0xFFFFF8DC),   // waveformOutline - Cream
            juce::Colour(0x40E67E22),   // waveformGlow
            // Spectrum gradient (warm vinyl palette)
            juce::Colour(0xFF8B4513),   // spectrumLow - Brown (warm bass)
            juce::Colour(0xFFE67E22),   // spectrumMid - Orange
            juce::Colour(0xFFFFF8DC),   // spectrumHigh - Cream
            juce::Colour(0xFFFFE4B5),   // spectrumPeak - Moccasin
            // Background
            juce::Colour(0xFF2D1F14),   // background - Dark brown
            juce::Colour(0x30E67E22),   // gridLines
        };
    }
    
    /** Boom Bap theme - Gold/Brown/Black (Classic hip-hop) */
    static GenreTheme boomBap()
    {
        return {
            "Boom Bap",
            // Primary palette
            juce::Colour(0xFFDAA520),   // primary - Goldenrod
            juce::Colour(0xFF8B4513),   // secondary - Saddle brown
            juce::Colour(0xFF1A1A1A),   // accent - Black
            // Waveform
            juce::Colour(0xFFDAA520),   // waveformFill - Gold
            juce::Colour(0xFFFFD700),   // waveformOutline - Bright gold
            juce::Colour(0x40DAA520),   // waveformGlow
            // Spectrum gradient (golden palette)
            juce::Colour(0xFF8B4513),   // spectrumLow - Brown (punchy kicks)
            juce::Colour(0xFFDAA520),   // spectrumMid - Gold
            juce::Colour(0xFFFFD700),   // spectrumHigh - Bright gold
            juce::Colour(0xFFFFFFFF),   // spectrumPeak
            // Background
            juce::Colour(0xFF1A1408),   // background - Dark gold-brown
            juce::Colour(0x30DAA520),   // gridLines
        };
    }
    
    /** Drill theme - Dark blue/Black/White (UK/Chicago Drill) */
    static GenreTheme drill()
    {
        return {
            "Drill",
            // Primary palette
            juce::Colour(0xFF1E3A5F),   // primary - Dark blue
            juce::Colour(0xFF0D0D0D),   // secondary - Black
            juce::Colour(0xFFE8E8E8),   // accent - Off-white
            // Waveform
            juce::Colour(0xFF3498DB),   // waveformFill - Blue
            juce::Colour(0xFFE8E8E8),   // waveformOutline - Light
            juce::Colour(0x403498DB),   // waveformGlow
            // Spectrum gradient (cold steel palette)
            juce::Colour(0xFF1E3A5F),   // spectrumLow - Dark blue (808 slides)
            juce::Colour(0xFF3498DB),   // spectrumMid - Blue
            juce::Colour(0xFFE8E8E8),   // spectrumHigh - Light
            juce::Colour(0xFFFFFFFF),   // spectrumPeak
            // Background
            juce::Colour(0xFF0A0A12),   // background - Near black with blue
            juce::Colour(0x201E3A5F),   // gridLines
        };
    }
    
    /** House theme - Cyan/Magenta/Yellow (Dance/Club) */
    static GenreTheme house()
    {
        return {
            "House",
            // Primary palette
            juce::Colour(0xFF00FFFF),   // primary - Cyan
            juce::Colour(0xFFFF00FF),   // secondary - Magenta
            juce::Colour(0xFFFFFF00),   // accent - Yellow
            // Waveform
            juce::Colour(0xFF00FFFF),   // waveformFill - Cyan
            juce::Colour(0xFFFF00FF),   // waveformOutline - Magenta
            juce::Colour(0x4000FFFF),   // waveformGlow
            // Spectrum gradient (club lights)
            juce::Colour(0xFFFF00FF),   // spectrumLow - Magenta (4-on-floor)
            juce::Colour(0xFF00FFFF),   // spectrumMid - Cyan
            juce::Colour(0xFFFFFF00),   // spectrumHigh - Yellow
            juce::Colour(0xFFFFFFFF),   // spectrumPeak
            // Background
            juce::Colour(0xFF0A0A1E),   // background - Dark blue-black
            juce::Colour(0x2000FFFF),   // gridLines
        };
    }
    
    //==========================================================================
    /** Get theme by genre name (case-insensitive partial match) */
    static GenreTheme getThemeForGenre(const juce::String& genreName)
    {
        auto lower = genreName.toLowerCase();
        
        if (lower.contains("g-funk") || lower.contains("gfunk") || lower.contains("west coast"))
            return gFunk();
        if (lower.contains("trap"))
            return trap();
        if (lower.contains("lo-fi") || lower.contains("lofi") || lower.contains("chill"))
            return lofi();
        if (lower.contains("boom") || lower.contains("bap") || lower.contains("90s") || lower.contains("classic"))
            return boomBap();
        if (lower.contains("drill"))
            return drill();
        if (lower.contains("house") || lower.contains("edm") || lower.contains("dance") || lower.contains("club"))
            return house();
        
        return defaultTheme();
    }
    
    //==========================================================================
    /** Interpolate between two themes for smooth transitions */
    static GenreTheme interpolate(const GenreTheme& a, const GenreTheme& b, float t)
    {
        auto lerp = [t](juce::Colour c1, juce::Colour c2) {
            return c1.interpolatedWith(c2, t);
        };
        
        return {
            t < 0.5f ? a.name : b.name,
            lerp(a.primary, b.primary),
            lerp(a.secondary, b.secondary),
            lerp(a.accent, b.accent),
            lerp(a.waveformFill, b.waveformFill),
            lerp(a.waveformOutline, b.waveformOutline),
            lerp(a.waveformGlow, b.waveformGlow),
            lerp(a.spectrumLow, b.spectrumLow),
            lerp(a.spectrumMid, b.spectrumMid),
            lerp(a.spectrumHigh, b.spectrumHigh),
            lerp(a.spectrumPeak, b.spectrumPeak),
            lerp(a.background, b.background),
            lerp(a.gridLines, b.gridLines)
        };
    }
    
    //==========================================================================
    /** Get color for a frequency (0.0 = bass, 1.0 = treble) */
    juce::Colour getSpectrumColour(float normalizedFrequency) const
    {
        if (normalizedFrequency < 0.33f)
        {
            // Low to mid
            float t = normalizedFrequency / 0.33f;
            return spectrumLow.interpolatedWith(spectrumMid, t);
        }
        else if (normalizedFrequency < 0.66f)
        {
            // Mid to high
            float t = (normalizedFrequency - 0.33f) / 0.33f;
            return spectrumMid.interpolatedWith(spectrumHigh, t);
        }
        else
        {
            // High to peak-ish
            float t = (normalizedFrequency - 0.66f) / 0.34f;
            return spectrumHigh.interpolatedWith(spectrumPeak.withAlpha(0.8f), t * 0.3f);
        }
    }
};

//==============================================================================
/**
    Manages genre theme with smooth transitions.
*/
class GenreThemeManager
{
public:
    GenreThemeManager() : currentTheme(GenreTheme::defaultTheme()) {}
    
    /** Set theme immediately */
    void setTheme(const GenreTheme& theme)
    {
        currentTheme = theme;
        targetTheme = theme;
        transitionProgress = 1.0f;
    }
    
    /** Set theme with smooth transition */
    void transitionTo(const GenreTheme& theme, float durationSeconds = 0.5f)
    {
        if (transitionProgress >= 1.0f)
            startTheme = currentTheme;
        
        targetTheme = theme;
        transitionProgress = 0.0f;
        transitionSpeed = 1.0f / (durationSeconds * 60.0f); // Assuming 60fps updates
    }
    
    /** Update transition (call each frame) */
    void update()
    {
        if (transitionProgress < 1.0f)
        {
            transitionProgress = juce::jmin(1.0f, transitionProgress + transitionSpeed);
            currentTheme = GenreTheme::interpolate(startTheme, targetTheme, transitionProgress);
        }
    }
    
    /** Get current (possibly interpolated) theme */
    const GenreTheme& getTheme() const { return currentTheme; }
    
    /** Check if transitioning */
    bool isTransitioning() const { return transitionProgress < 1.0f; }

private:
    GenreTheme currentTheme;
    GenreTheme startTheme;
    GenreTheme targetTheme;
    float transitionProgress = 1.0f;
    float transitionSpeed = 0.0f;
};

