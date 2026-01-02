# UI Improvements Phase 2 - Implementation Plan

Based on user testing of the Tools dropdown and layout changes (Jan 2, 2026).

---

## 1. Tools Dropdown Behavior Refinement

### Current State
- **Tools menu**: Instruments, FX Chain, Expansions, Mixer
- **Floating windows**: Instruments & Expansions open as DocumentWindow
- **Bottom panel**: FX Chain & Mixer toggle bottom panel

### Required Changes
| Tool | Current Behavior | Target Behavior |
|------|------------------|-----------------|
| Instruments | Floating window | **Bottom panel** (like FX/Mixer) |
| FX Chain | Bottom panel | Bottom panel ✓ |
| Expansions | Floating window | Floating window ✓ (graceful close needed) |
| Mixer | Bottom panel | Bottom panel ✓ |

### Implementation Tasks

#### Task 1.1: Move Instruments to Bottom Panel
**File**: `MainComponent.cpp`
```cpp
// In showToolWindow() - change Instruments from floating to bottom panel
case 1: // Instruments - now shows in bottom panel
    bottomPanel.setCurrentView(BottomPanel::View::Instruments);
    bottomPanelVisible = true;
    break;
```

#### Task 1.2: Add Graceful Close to Expansions Floating Window
**File**: `MainComponent.h` / `MainComponent.cpp`

Create a custom DocumentWindow subclass with proper close handling:
```cpp
class ExpansionsWindow : public juce::DocumentWindow
{
public:
    ExpansionsWindow(const juce::String& name, juce::Component* content, 
                     std::function<void()> onCloseCallback)
        : DocumentWindow(name, juce::Colours::darkgrey, 
                        DocumentWindow::closeButton | DocumentWindow::minimiseButton),
          closeCallback(onCloseCallback)
    {
        setContentOwned(content, true);
        setUsingNativeTitleBar(true);
        setResizable(true, true);
        centreWithSize(600, 400);
    }
    
    void closeButtonPressed() override
    {
        // Graceful close - notify parent, then delete
        if (closeCallback)
            closeCallback();
        // Parent will delete this window
    }
    
private:
    std::function<void()> closeCallback;
};
```

In MainComponent:
```cpp
void MainComponent::showExpansionsWindow()
{
    if (expansionsWindow == nullptr)
    {
        auto* content = new ExpansionsPanel(/* params */);
        expansionsWindow = std::make_unique<ExpansionsWindow>(
            "Expansions",
            content,
            [this]() { 
                // Called when close button pressed
                juce::MessageManager::callAsync([this]() {
                    expansionsWindow.reset();
                });
            }
        );
        expansionsWindow->setVisible(true);
    }
    else
    {
        expansionsWindow->toFront(true);
    }
}
```

---

## 2. Timeline Synchronization with Horizontal Zoom

### Problem
- ArrangementView's timeline ruler doesn't update when horizontal zoom changes
- Track lanes zoom correctly, but the ruler bar numbers stay static

### Root Cause Analysis
**File**: `ArrangementView.cpp`

The `drawTimelineRuler()` function likely uses fixed pixel-per-beat calculation instead of respecting `hZoom` factor.

### Implementation Tasks

#### Task 2.1: Sync Ruler with Zoom Level
**File**: `ArrangementView.cpp` - `drawTimelineRuler()`

```cpp
void ArrangementView::drawTimelineRuler(juce::Graphics& g, juce::Rectangle<int> bounds)
{
    g.setColour(AppColours::surfaceAlt);
    g.fillRect(bounds);
    
    // Calculate pixels per beat based on zoom level
    float beatsPerBar = 4.0f;
    float pixelsPerBeat = 30.0f * hZoom;  // BASE_PIXELS_PER_BEAT * zoom
    float pixelsPerBar = pixelsPerBeat * beatsPerBar;
    
    // Calculate visible range based on scroll position
    float startBar = scrollX / pixelsPerBar;
    float visibleBars = bounds.getWidth() / pixelsPerBar;
    
    // Draw bar lines and numbers
    int firstBar = (int)startBar;
    int lastBar = (int)(startBar + visibleBars) + 2;
    
    g.setColour(AppColours::textSecondary);
    g.setFont(11.0f);
    
    for (int bar = firstBar; bar <= lastBar; ++bar)
    {
        float x = (bar * pixelsPerBar) - scrollX + trackListWidth;
        
        if (x >= trackListWidth && x < bounds.getRight())
        {
            // Draw bar line
            g.setColour(AppColours::border);
            g.drawVerticalLine((int)x, (float)bounds.getY(), (float)bounds.getBottom());
            
            // Draw bar number
            g.setColour(AppColours::textSecondary);
            g.drawText(juce::String(bar + 1), 
                      (int)x + 4, bounds.getY() + 2, 
                      40, bounds.getHeight() - 4,
                      juce::Justification::centredLeft);
            
            // Draw beat subdivisions at higher zoom levels
            if (hZoom > 0.5f)
            {
                g.setColour(AppColours::border.withAlpha(0.3f));
                for (int beat = 1; beat < (int)beatsPerBar; ++beat)
                {
                    float beatX = x + (beat * pixelsPerBeat);
                    if (beatX < bounds.getRight())
                        g.drawVerticalLine((int)beatX, 
                                          (float)bounds.getY() + bounds.getHeight() * 0.6f, 
                                          (float)bounds.getBottom());
                }
            }
        }
    }
    
    // Border
    g.setColour(AppColours::border);
    g.drawHorizontalLine(bounds.getBottom() - 1, (float)bounds.getX(), (float)bounds.getRight());
}
```

#### Task 2.2: Ensure Track Lanes and Ruler Share Same Scroll/Zoom
**File**: `ArrangementView.cpp`

Add synchronization in `setHorizontalZoom()`:
```cpp
void ArrangementView::setHorizontalZoom(float zoom)
{
    hZoom = juce::jlimit(0.1f, 4.0f, zoom);
    
    // Update all track lanes
    for (auto* lane : trackLanes)
        lane->setHorizontalZoom(hZoom);
    
    // Trigger ruler repaint
    repaint();
    
    // Update lanes layout
    updateLanesLayout();
}
```

---

## 3. FX Chain / Bottom Panel Layout Optimization

### Problem
- FX Chain panel is too narrow
- Sat Parameters and FX Chain sections stacked vertically wastes horizontal space
- No scrolling for overflow content

### Proposed Layout (Side-by-Side)
```
┌─────────────────────────────────────────────────────────────────────┐
│ FX Chain                                    Select Preset... │ Copy │
├────────────────────────────────┬────────────────────────────────────┤
│ CHAIN EDITOR (left 60%)        │ PARAMETERS (right 40%)             │
│ ┌──────────────────────────┐   │ ┌────────────────────────────────┐ │
│ │ Master: [EQ] [Sat] [Comp]│   │ │ Sat Parameters                 │ │
│ │ Drums:  [+]              │   │ │ ─────────────────────────────  │ │
│ │ Bass:   [+]              │   │ │ Drive: ═══════════○──── 28.9   │ │
│ │ Keys:   [+]              │   │ │ Mix:   ════════○────── 0.43    │ │
│ │ ...                      │   │ │ Tone:  ════════════○── 0.64    │ │
│ │ (scrollable)             │   │ │                                │ │
│ └──────────────────────────┘   │ │ (updates based on selection)   │ │
│                                │ └────────────────────────────────┘ │
└────────────────────────────────┴────────────────────────────────────┘
```

### Implementation Tasks

#### Task 3.1: Create Split Layout in FXChainPanel
**File**: `FXChainPanel.h` / `FXChainPanel.cpp`

```cpp
void FXChainPanel::resized()
{
    auto bounds = getLocalBounds();
    
    // Header row
    auto header = bounds.removeFromTop(40);
    titleLabel.setBounds(header.removeFromLeft(100));
    header.removeFromRight(10);
    resetButton.setBounds(header.removeFromRight(60));
    pasteButton.setBounds(header.removeFromRight(60));
    copyButton.setBounds(header.removeFromRight(60));
    presetSelector.setBounds(header.removeFromRight(150));
    
    // Main content - side by side
    auto content = bounds.reduced(10);
    
    // Use StretchableLayoutManager for resizable split
    int dividerWidth = 8;
    int chainWidth = content.getWidth() * 0.6f;
    int paramsWidth = content.getWidth() - chainWidth - dividerWidth;
    
    // Left side: Chain editor with scroll
    auto chainArea = content.removeFromLeft(chainWidth);
    chainViewport.setBounds(chainArea);
    
    // Divider
    content.removeFromLeft(dividerWidth);
    
    // Right side: Parameters panel
    auto paramsArea = content;
    parametersPanel.setBounds(paramsArea);
}
```

#### Task 3.2: Add Viewport for Scrollable Chain List
```cpp
// In FXChainPanel constructor
chainViewport.setViewedComponent(&chainContent, false);
chainViewport.setScrollBarsShown(true, false); // Vertical scroll only
addAndMakeVisible(chainViewport);
```

#### Task 3.3: Dynamic Height Based on Content
```cpp
void FXChainPanel::updateChainContentSize()
{
    int requiredHeight = 0;
    requiredHeight += masterChainRow.getHeight();
    
    for (auto* trackRow : trackChainRows)
        requiredHeight += trackRow->getHeight();
    
    chainContent.setSize(chainViewport.getWidth() - 10, 
                         juce::jmax(requiredHeight, chainViewport.getHeight()));
}
```

---

## 4. Additional Improvements (Brainstormed)

### 4.1 Bottom Panel Height Memory
Remember last panel height per tool type:
```cpp
std::map<int, int> bottomPanelHeights; // toolId -> height

void MainComponent::showToolWindow(int toolId)
{
    if (bottomPanelHeights.count(toolId))
        bottomPanelHeight = bottomPanelHeights[toolId];
    // ... show panel
}

void MainComponent::onBottomPanelResized()
{
    bottomPanelHeights[currentBottomTool] = bottomPanelHeight;
}
```

### 4.2 Keyboard Shortcuts for Tools
| Key | Action |
|-----|--------|
| `I` | Toggle Instruments panel |
| `F` | Toggle FX Chain panel |
| `E` | Open Expansions window |
| `M` | Toggle Mixer panel |
| `Esc` | Close floating window / hide bottom panel |

**File**: `MainComponent.cpp`
```cpp
bool MainComponent::keyPressed(const juce::KeyPress& key)
{
    if (key == juce::KeyPress('i', juce::ModifierKeys::noModifiers, 0))
    {
        showToolWindow(1); // Instruments
        return true;
    }
    // ... etc
}
```

### 4.3 Minimize Bottom Panel (Collapse to Tab Bar)
Add a collapse button that shrinks panel to just a title bar:
```cpp
class CollapsibleBottomPanel : public juce::Component
{
    bool collapsed = false;
    static constexpr int collapsedHeight = 28;
    static constexpr int expandedHeight = 250;
    
    void toggleCollapse()
    {
        collapsed = !collapsed;
        getParentComponent()->resized();
    }
    
    int getDesiredHeight() const
    {
        return collapsed ? collapsedHeight : expandedHeight;
    }
};
```

### 4.4 Tool Window Tabs (Like Browser Dev Tools)
When multiple tools are "open", show them as tabs at bottom:
```
┌───────────┬───────────┬───────────┐
│ FX Chain  │ Mixer     │ Instruments│  ← Tab bar
├───────────┴───────────┴───────────┤
│ (Content of selected tab)          │
└────────────────────────────────────┘
```

---

## 5. File References for Implementation

| Component | File | Key Functions |
|-----------|------|---------------|
| Tools Menu | `TransportComponent.cpp` | `toolsButton.onClick` |
| Tool Window Logic | `MainComponent.cpp` | `showToolWindow()`, `toolsMenuItemSelected()` |
| Floating Windows | `MainComponent.h` | `expansionsWindow` unique_ptr |
| Bottom Panel | `MainComponent.cpp` | `setupBottomPanel()`, `resized()` |
| Timeline Ruler | `ArrangementView.cpp` | `drawTimelineRuler()` |
| FX Chain Layout | `FXChainPanel.cpp` | `resized()` |
| Track Lanes Zoom | `ArrangementView.cpp` | `setHorizontalZoom()` |

---

## 6. Priority Order

1. **HIGH**: Graceful close for Expansions window (blocking UX issue)
2. **HIGH**: Timeline zoom sync (visual consistency)
3. **MEDIUM**: Move Instruments to bottom panel (consistency)
4. **MEDIUM**: FX Chain side-by-side layout (space optimization)
5. **LOW**: Keyboard shortcuts (power user feature)
6. **LOW**: Collapsible panel / tab system (nice-to-have)

---

## 7. Testing Checklist

- [ ] Tools > Instruments shows in bottom panel
- [ ] Tools > FX Chain shows in bottom panel  
- [ ] Tools > Expansions opens floating window
- [ ] Tools > Mixer shows in bottom panel
- [ ] Expansions window X button closes gracefully
- [ ] Horizontal zoom affects both tracks AND ruler
- [ ] Ruler bar numbers align with track bar lines
- [ ] FX Chain and Parameters are side-by-side
- [ ] Bottom panel scrolls if content overflows
- [ ] Panel remembers height between sessions

---

*Document created: Jan 2, 2026*
*For implementation in new chat session with full context window*
