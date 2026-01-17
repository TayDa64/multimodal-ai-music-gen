/*
  ==============================================================================

    MainComponent.h
    
    Root UI component containing all application panels and managing layout.

  ==============================================================================
*/

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include <juce_osc/juce_osc.h>

#include <map>
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
#include "UI/ExpansionBrowserPanel.h"
#include "UI/Mixer/MixerComponent.h"
#include "UI/TakeLaneComponent.h"
#include "UI/ControlsWindow.h"
#include "UI/FloatingToolWindow.h"
#include "UI/Theme/LayoutConstants.h"
#include "UI/Mastering/MasteringSuitePanel.h"

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
                      public AppState::Listener,
                      public OSCBridge::Listener,
                      public PromptPanel::Listener,
                      public ProgressOverlay::Listener,
                      public VisualizationPanel::Listener,
                      public GenreSelector::Listener,
                      public InstrumentBrowserPanel::Listener,
                      public FXChainPanel::Listener,
                      public ExpansionBrowserPanel::Listener,
                      public TakeLanePanel::Listener,
                      public TimelineComponent::Listener,
                      public TransportComponent::Listener,
                      public Project::ProjectState::Listener,
                      public ControlsPanel::Listener,
                      public MasteringSuitePanel::Listener,
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
    // AppState::Listener
    void onNewProjectCreated() override;
    void onProjectLoaded(const juce::File& file) override;
    
    //==============================================================================
    // OSCBridge::Listener
    void onConnectionStatusChanged(bool connected) override;
    void onProgress(float percent, const juce::String& step, const juce::String& message) override;
    void onGenerationComplete(const GenerationResult& result) override;
    void onError(int code, const juce::String& message) override;
    void onAnalyzeResultReceived(const AnalyzeResult& result) override;
    void onAnalyzeError(int code, const juce::String& message) override;
    void onSchemaVersionWarning(int clientVersion, int serverVersion, const juce::String& message) override;
    
    //==============================================================================
    // OSCBridge::Listener - Instruments
    void onInstrumentsLoaded(const juce::String& json) override;
    
    //==============================================================================
    // PromptPanel::Listener
    void generateRequested(const juce::String& prompt) override;
    void cancelRequested() override;
    void analyzeUrlRequested(const juce::String& url) override;
    
    //==============================================================================
    // VisualizationPanel::Listener
    void fileSelected(const juce::File& file) override;
    void analyzeFileRequested(const juce::File& file) override;
    void regenerateRequested(int startBar, int endBar, const juce::StringArray& tracks) override;
    void trackInstrumentSelected(int trackIndex, const juce::String& instrumentId) override;
    void trackLoadSF2Requested(int trackIndex) override;
    void trackLoadSFZRequested(int trackIndex) override;
    
    //==============================================================================
    // GenreSelector::Listener
    void genreChanged(const juce::String& genreId, const GenreTemplate& genre) override;
    
    //==============================================================================
    // InstrumentBrowserPanel::Listener
    void instrumentChosen(const InstrumentInfo& info) override;
    void requestLibraryInstruments() override;
    
    //==============================================================================
    // FXChainPanel::Listener
    void fxChainChanged(FXChainPanel* panel) override;
    
    //==============================================================================
    // ExpansionBrowserPanel::Listener
    void requestExpansionListOSC() override;
    void requestInstrumentsOSC(const juce::String& expansionId) override;
    void requestResolveOSC(const juce::String& instrument, const juce::String& genre) override;
    void requestImportExpansionOSC(const juce::String& path) override;
    void requestScanExpansionsOSC(const juce::String& directory) override;
    void requestExpansionEnableOSC(const juce::String& expansionId, bool enabled) override;
    
    //==============================================================================
    // OSCBridge::Listener expansion callbacks
    void onExpansionListReceived(const juce::String& json) override;
    void onExpansionInstrumentsReceived(const juce::String& json) override;
    void onExpansionResolveReceived(const juce::String& json) override;
    
    //==============================================================================
    // OSCBridge::Listener take callbacks
    void onTakesAvailable(const juce::String& json) override;
    void onTakeSelected(const juce::String& track, const juce::String& takeId) override;
    void onTakeRendered(const juce::String& track, const juce::String& outputPath) override;
    
    //==============================================================================
    // TakeLanePanel::Listener
    void takeSelected(const juce::String& track, const juce::String& takeId, const juce::String& midiPath) override;
    void takePlayRequested(const juce::String& track, const juce::String& takeId, const juce::String& midiPath) override;
    void takeStopRequested(const juce::String& track) override;
    void renderTakesRequested() override;
    void commitCompRequested() override;
    void revertCompRequested() override;
    
    //==============================================================================
    // ProjectState::Listener overrides
    void valueTreePropertyChanged(juce::ValueTree& treeWhosePropertyHasChanged, const juce::Identifier& property) override;
    void valueTreeChildAdded(juce::ValueTree& parentTree, juce::ValueTree& childWhichHasBeenAdded) override;
    void valueTreeChildRemoved(juce::ValueTree& parentTree, juce::ValueTree& childWhichHasBeenRemoved, int indexFromWhichChildWasRemoved) override;
    void valueTreeChildOrderChanged(juce::ValueTree& parentTreeWhichHasChanged, int oldIndex, int newIndex) override {}
    void valueTreeParentChanged(juce::ValueTree& treeWhoseParentHasChanged) override {}
    
    //==============================================================================
    // TimelineComponent::Listener overrides
    void timelineSeekRequested(double positionSeconds) override;
    void loopRegionChanged(double startSeconds, double endSeconds) override;
    
    //==============================================================================
    // TransportComponent::Listener overrides
    void transportPlayRequested() override {}
    void transportPauseRequested() override {}
    void transportStopRequested() override {}
    void transportPositionChanged(double newPosition) override {}
    void transportBPMChanged(int newBPM) override {}
    void toolsMenuItemSelected(int itemId) override;

    //==============================================================================
    // Timer callback for UI updates
    void timerCallback() override;

    //==============================================================================
    // Key listener
    bool keyPressed(const juce::KeyPress& key) override;

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
    
  juce::int64 lastBackendConnectAttemptMs = 0;
    // NB Phase 2: Genre-aware components
    std::unique_ptr<GenreSelector> genreSelector;
    std::unique_ptr<InstrumentBrowserPanel> instrumentBrowser;
    std::unique_ptr<FXChainPanel> fxChainPanel;
    std::unique_ptr<ExpansionBrowserPanel> expansionBrowser;
    std::unique_ptr<UI::MixerComponent> mixerComponent;
    std::unique_ptr<TakeLanePanel> takeLanePanel;  // Take lanes for comping
    
    // Floating windows for Instruments and Expansions (MPC-style)
    std::unique_ptr<FloatingToolWindow> instrumentsWindow;
    std::unique_ptr<FloatingToolWindow> expansionsWindow;
    std::unique_ptr<ControlsWindow> controlsWindow;
    std::unique_ptr<FloatingToolWindow> masteringWindow;  // Mastering Suite floating window
    std::unique_ptr<MasteringSuitePanel> masteringSuitePanel;
    
    // Bottom panel visibility state (for FX Chain and Mixer)
    bool bottomPanelVisible = false;
    int currentBottomTool = 0;  // 0 = none, 2 = FX Chain, 4 = Mixer
    
    // Placeholder areas (will be replaced with actual components)
    juce::Rectangle<int> visualizationArea;
    juce::Rectangle<int> bottomPanelArea;
    
    //==============================================================================
    // Layout constants - now use Layout:: namespace from LayoutConstants.h
    // These are kept for backward compatibility but prefer using Layout:: directly
    static constexpr int transportHeight = Layout::transportHeightDefault;

    //==============================================================================
    void syncTrackAudioFromProjectState();
    void applyDefaultSynthSettingsForTrackFromProjectState(int trackIndex);
    static constexpr int timelineHeight = Layout::timelineHeightDefault;
    static constexpr int promptPanelWidth = Layout::sidebarWidthDefault;
    static constexpr int padding = Layout::paddingSM;
    
    //==============================================================================
    // State
    bool serverConnected = false;
    float currentProgress = 0.0f;
    juce::String currentStatus = "Ready";
    juce::String currentGenre = "auto";  // Default genre (synced with GenreSelector)
    bool initialInstrumentsRequested = false;
    AnalyzeResult lastAnalyzeResult;  // Store last analysis for Apply action

    // Debounce for backend connectivity warnings.
    juce::int64 lastBackendNotConnectedWarningMs = 0;

    // Apply-once overrides injected into the next /generate and /regenerate request.
    juce::var nextGenerateOverrides;
    juce::var nextRegenerateOverrides;

    // Take comping: snapshot of original per-track notes (keyed by track index).
    std::map<int, juce::ValueTree> takeCompSnapshots;
    
    //==============================================================================
    void startPythonServer();
    void stopPythonServer();
    void setupOSCConnection();
    void setupBottomPanel();
    void showToolWindow(int toolId);  // 1=Instruments, 2=FX, 3=Expansions, 4=Mixer, 5=Takes, 6=Controls, 7=Mastering
    void hideBottomPanel();

    // Returns true when OSC is connected. If Python is running but OSC isn't ready yet,
    // this updates the status bar (non-modal) instead of showing a misleading warning.
    bool ensureBackendConnected(const juce::String& actionLabel);

    int resolveTrackIndexForName(const juce::String& trackName);
    juce::File resolveTakeMidiFile(const juce::String& midiPath) const;
    bool applyTakeCompToProject(const juce::String& track, const juce::String& takeId, const juce::String& midiPath);

    // Take audition: keep the main project MIDI intact and restore it after audition.
    juce::MidiFile auditionBackupMidi;
    bool hasAuditionBackupMidi = false;
    void applyGenreTheme(const juce::String& genreId);
    void applyAnalysisResult(const AnalyzeResult& result);
    void scanLocalExpansions();  // Scan local expansion packs and populate instruments
    void drawPlaceholder(juce::Graphics& g, juce::Rectangle<int> area, 
                        const juce::String& label, juce::Colour colour);

    // ControlsPanel::Listener
    void controlsApplyGlobalRequested(const juce::var& overrides) override;
    void controlsClearGlobalRequested(const juce::StringArray& keys) override;
    void controlsApplyNextRequestRequested(const juce::var& overrides, ControlsPanel::NextScope scope) override;
    void controlsClearNextRequestRequested() override;
    
    //==============================================================================
    // MasteringSuitePanel::Listener
    void masteringSettingsChanged(MasteringSuitePanel* panel) override;
    void applyMasteringRequested(const juce::String& processorType, const juce::var& settings) override;
    void analyzeReferenceRequested(const juce::File& file) override;
    void separateStemsRequested(const juce::File& file) override;

    void updateControlsNextOverridesUi();
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(MainComponent)
};
