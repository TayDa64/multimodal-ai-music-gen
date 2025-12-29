/*
  ==============================================================================

    MainComponent.h
    
    Root UI component containing all application panels and managing layout.

  ==============================================================================
*/

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include <juce_osc/juce_osc.h>
#include "Application/AppState.h"
#include "Audio/AudioEngine.h"
#include "Communication/OSCBridge.h"
#include "Communication/PythonManager.h"
#include "UI/TransportComponent.h"
#include "UI/PromptPanel.h"
#include "UI/ProgressOverlay.h"
#include "UI/RecentFilesPanel.h"
#include "UI/TimelineComponent.h"
#include "UI/VisualizationPanel.h"
#include "UI/GenreSelector.h"
#include "UI/InstrumentBrowserPanel.h"
#include "UI/FXChainPanel.h"

//==============================================================================
/**
    Main component that serves as the root of the UI hierarchy.
    
    Layout:
    ┌─────────────────────────────────────────────────────────────────────────┐
    │  Transport Bar (play/pause/stop, position, BPM)                         │
    ├─────────────────────────────────────────────────────────────────────────┤
    │                           │                                              │
    │   Prompt Panel            │          Recent Files / Visualization        │
    │   (text input,            │          (file browser, piano roll)          │
    │    generate btn)          │                                              │
    │                           │                                              │
    ├───────────────────────────┴──────────────────────────────────────────────┤
    │  Status Bar / Quick Actions                                              │
    └─────────────────────────────────────────────────────────────────────────┘
*/
class MainComponent : public juce::Component,
                      public OSCBridge::Listener,
                      public PromptPanel::Listener,
                      public ProgressOverlay::Listener,
                      public VisualizationPanel::Listener,
                      public GenreSelector::Listener,
                      public InstrumentBrowserPanel::Listener,
                      public FXChainPanel::Listener,
                      public juce::Timer
{
public:
    //==============================================================================
    MainComponent(AppState& state, mmg::AudioEngine& engine);
    ~MainComponent() override;

    //==============================================================================
    void paint(juce::Graphics& g) override;
    void resized() override;
    
    //==============================================================================
    // OSCBridge::Listener
    void onConnectionStatusChanged(bool connected) override;
    void onProgress(float percent, const juce::String& step, const juce::String& message) override;
    void onGenerationComplete(const GenerationResult& result) override;
    void onError(int code, const juce::String& message) override;
    
    //==============================================================================
    // PromptPanel::Listener
    void generateRequested(const juce::String& prompt) override;
    void cancelRequested() override;
    
    //==============================================================================
    // VisualizationPanel::Listener
    void fileSelected(const juce::File& file) override;
    
    //==============================================================================
    // GenreSelector::Listener
    void genreChanged(const juce::String& genreId, const GenreTemplate& genre) override;
    
    //==============================================================================
    // InstrumentBrowserPanel::Listener
    void instrumentChosen(const InstrumentInfo& info) override;
    
    //==============================================================================
    // FXChainPanel::Listener
    void fxChainChanged(FXChainPanel* panel) override;
    
    //==============================================================================
    // Timer callback for UI updates
    void timerCallback() override;

private:
    //==============================================================================
    // State
    AppState& appState;
    mmg::AudioEngine& audioEngine;
    std::unique_ptr<PythonManager> pythonManager;
    std::unique_ptr<OSCBridge> oscBridge;
    
    //==============================================================================
    // UI Components
    std::unique_ptr<TransportComponent> transportBar;
    std::unique_ptr<TimelineComponent> timelineComponent;
    std::unique_ptr<PromptPanel> promptPanel;
    std::unique_ptr<ProgressOverlay> progressOverlay;
    std::unique_ptr<VisualizationPanel> visualizationPanel;
    
    // NB Phase 2: Genre-aware components
    std::unique_ptr<GenreSelector> genreSelector;
    std::unique_ptr<InstrumentBrowserPanel> instrumentBrowser;
    std::unique_ptr<FXChainPanel> fxChainPanel;
    
    // Bottom panel tab buttons
    juce::TextButton instrumentsTabButton { "Instruments" };
    juce::TextButton fxTabButton { "FX Chain" };
    int currentBottomTab = 0;  // 0 = Instruments, 1 = FX Chain
    
    // Placeholder areas (will be replaced with actual components)
    juce::Rectangle<int> visualizationArea;
    juce::Rectangle<int> bottomPanelArea;
    
    //==============================================================================
    // Layout constants
    static constexpr int transportHeight = 50;
    static constexpr int timelineHeight = 65;
    static constexpr int promptPanelWidth = 320;
    static constexpr int bottomPanelHeight = 150;
    static constexpr int padding = 4;
    
    //==============================================================================
    // State
    bool serverConnected = false;
    float currentProgress = 0.0f;
    juce::String currentStatus = "Ready";
    juce::String currentGenre = "trap";  // Default genre (synced with GenreSelector)
    
    //==============================================================================
    void startPythonServer();
    void stopPythonServer();
    void setupOSCConnection();
    void setupBottomPanel();
    void updateBottomPanelTabs();
    void applyGenreTheme(const juce::String& genreId);
    void drawPlaceholder(juce::Graphics& g, juce::Rectangle<int> area, 
                        const juce::String& label, juce::Colour colour);
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(MainComponent)
};
