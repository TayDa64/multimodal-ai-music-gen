/*
  ==============================================================================

    LayoutConstants.h
    
    Centralized layout constants and helpers for responsive UI design.
    All UI components should use these values instead of hardcoded magic numbers.

  ==============================================================================
*/

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>

namespace Layout
{
    //==============================================================================
    // Minimum Window Size
    //==============================================================================
    
    constexpr int minWindowWidth = 1024;
    constexpr int minWindowHeight = 600;
    constexpr int defaultWindowWidth = 1280;
    constexpr int defaultWindowHeight = 800;
    
    //==============================================================================
    // Spacing & Padding (use scaled values for DPI awareness)
    //==============================================================================
    
    // Base padding values (will be scaled by getScaledPadding)
    constexpr int paddingXS = 2;
    constexpr int paddingSM = 4;
    constexpr int paddingMD = 8;
    constexpr int paddingLG = 12;
    constexpr int paddingXL = 16;
    constexpr int paddingXXL = 24;
    
    // Component spacing
    constexpr int componentGapSM = 4;
    constexpr int componentGapMD = 8;
    constexpr int componentGapLG = 16;
    
    //==============================================================================
    // Typography Scale
    //==============================================================================
    
    constexpr float fontSizeXS = 10.0f;
    constexpr float fontSizeSM = 11.0f;
    constexpr float fontSizeMD = 13.0f;
    constexpr float fontSizeLG = 14.0f;
    constexpr float fontSizeXL = 16.0f;
    constexpr float fontSizeTitle = 18.0f;
    constexpr float fontSizeHeader = 20.0f;
    
    //==============================================================================
    // Component Heights (minimum touch target = 44px for accessibility)
    //==============================================================================
    
    constexpr int buttonHeightSM = 24;
    constexpr int buttonHeightMD = 30;
    constexpr int buttonHeightLG = 36;
    constexpr int buttonHeightTouch = 44;  // Minimum touch target
    
    constexpr int inputHeightSM = 24;
    constexpr int inputHeightMD = 30;
    constexpr int inputHeightLG = 36;
    
    constexpr int sliderHeightHorizontal = 24;
    constexpr int sliderThumbSize = 16;
    
    //==============================================================================
    // Panel Dimensions
    //==============================================================================
    
    // Transport bar
    constexpr int transportHeightMin = 44;
    constexpr int transportHeightDefault = 50;
    constexpr int transportHeightMax = 60;
    
    // Timeline
    constexpr int timelineHeightMin = 50;
    constexpr int timelineHeightDefault = 65;
    constexpr int timelineHeightMax = 80;
    
    // Sidebar / Prompt Panel
    constexpr int sidebarWidthMin = 280;
    constexpr int sidebarWidthDefault = 320;
    constexpr int sidebarWidthMax = 400;
    
    // Bottom panel
    constexpr int bottomPanelHeightMin = 200;
    constexpr int bottomPanelHeightDefault = 280;
    constexpr int bottomPanelRatio = 3;  // Takes 1/3 of available height
    
    // Tab bar
    constexpr int tabBarHeight = 32;
    constexpr int tabButtonMinWidth = 80;
    constexpr int tabButtonMaxWidth = 150;
    
    // Status bar
    constexpr int statusBarHeight = 24;
    
    //==============================================================================
    // Card/List Item Dimensions
    //==============================================================================
    
    constexpr int cardHeightSM = 50;
    constexpr int cardHeightMD = 70;
    constexpr int cardHeightLG = 90;
    
    constexpr int listItemHeight = 44;
    constexpr int listItemSpacing = 4;
    
    //==============================================================================
    // Border Radii
    //==============================================================================
    
    constexpr float borderRadiusSM = 4.0f;
    constexpr float borderRadiusMD = 6.0f;
    constexpr float borderRadiusLG = 8.0f;
    constexpr float borderRadiusXL = 12.0f;
    
    //==============================================================================
    // Responsive Breakpoints
    //==============================================================================
    
    constexpr int breakpointSmall = 1024;    // Small window / laptop
    constexpr int breakpointMedium = 1440;   // Standard desktop
    constexpr int breakpointLarge = 1920;    // Full HD
    constexpr int breakpointXLarge = 2560;   // QHD / 4K
    
    //==============================================================================
    // Helper Functions
    //==============================================================================
    
    /** Get scale factor based on display DPI */
    inline float getDisplayScale()
    {
        if (auto* display = juce::Desktop::getInstance().getDisplays().getPrimaryDisplay())
            return (float)display->scale;
        return 1.0f;
    }
    
    /** Scale a value by display DPI */
    inline int scaled(int value)
    {
        return juce::roundToInt(value * getDisplayScale());
    }
    
    /** Scale a float value by display DPI */
    inline float scaledF(float value)
    {
        return value * getDisplayScale();
    }
    
    /** Get appropriate padding based on available space */
    inline int getAdaptivePadding(int availableWidth)
    {
        if (availableWidth < breakpointSmall)
            return paddingSM;
        if (availableWidth < breakpointMedium)
            return paddingMD;
        if (availableWidth < breakpointLarge)
            return paddingLG;
        return paddingXL;
    }
    
    /** Get sidebar width based on total window width */
    inline int getAdaptiveSidebarWidth(int windowWidth)
    {
        if (windowWidth < breakpointSmall)
            return sidebarWidthMin;
        if (windowWidth < breakpointLarge)
            return sidebarWidthDefault;
        return sidebarWidthMax;
    }
    
    /** Get bottom panel height based on available height */
    inline int getAdaptiveBottomPanelHeight(int availableHeight)
    {
        int dynamicHeight = availableHeight / bottomPanelRatio;
        return juce::jlimit(bottomPanelHeightMin, availableHeight / 2, dynamicHeight);
    }
    
    /** Create a responsive FlexBox with standard settings */
    inline juce::FlexBox createRowFlex(juce::FlexBox::JustifyContent justify = juce::FlexBox::JustifyContent::flexStart)
    {
        juce::FlexBox fb;
        fb.flexDirection = juce::FlexBox::Direction::row;
        fb.justifyContent = justify;
        fb.alignItems = juce::FlexBox::AlignItems::center;
        fb.flexWrap = juce::FlexBox::Wrap::noWrap;
        return fb;
    }
    
    /** Create a vertical FlexBox with standard settings */
    inline juce::FlexBox createColumnFlex(juce::FlexBox::JustifyContent justify = juce::FlexBox::JustifyContent::flexStart)
    {
        juce::FlexBox fb;
        fb.flexDirection = juce::FlexBox::Direction::column;
        fb.justifyContent = justify;
        fb.alignItems = juce::FlexBox::AlignItems::stretch;
        fb.flexWrap = juce::FlexBox::Wrap::noWrap;
        return fb;
    }
    
    /** Create a FlexItem with minimum and preferred sizes */
    inline juce::FlexItem createFlexItem(juce::Component& comp, float flex, int minWidth = 0, int maxWidth = 0)
    {
        auto item = juce::FlexItem(comp).withFlex(flex);
        if (minWidth > 0)
            item = item.withMinWidth((float)minWidth);
        if (maxWidth > 0)
            item = item.withMaxWidth((float)maxWidth);
        return item;
    }
    
    /** Calculate appropriate font size based on window width */
    inline float getAdaptiveFontSize(int windowWidth, float baseSize)
    {
        if (windowWidth < breakpointSmall)
            return baseSize * 0.9f;
        if (windowWidth >= breakpointXLarge)
            return baseSize * 1.1f;
        return baseSize;
    }

}  // namespace Layout
