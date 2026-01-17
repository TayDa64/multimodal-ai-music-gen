/*
  ==============================================================================

    MasteringSuitePanel.h
    
    Professional mastering suite with 8 integrated processors:
    - True Peak Limiter
    - Transient Shaper  
    - Multiband Dynamics
    - Spectral Processing (Dynamic EQ, De-esser, Exciter)
    - Auto-Gain Staging
    - Reference Matching
    - Spatial Audio (Binaural, Atmos, Ambisonics)
    - Stem Separation

  ==============================================================================
*/

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include "../Theme/ColourScheme.h"
#include "../Theme/LayoutConstants.h"

//==============================================================================
// Forward declarations for processor sub-panels
class TruePeakLimiterPanel;
class TransientShaperPanel;
class MultibandDynamicsPanel;
class SpectralProcessorPanel;
class AutoGainStagingPanel;
class ReferenceMatchingPanel;
class SpatialAudioPanel;
class StemSeparationPanel;

//==============================================================================
/**
    MasteringSuitePanel - Professional mastering suite with tabbed interface
    
    Integrates 8 professional-grade audio processors in a cohesive UI
*/
class MasteringSuitePanel : public juce::Component,
                            public juce::Timer
{
public:
    MasteringSuitePanel();
    ~MasteringSuitePanel() override;
    
    //==============================================================================
    void paint(juce::Graphics& g) override;
    void resized() override;
    
    //==============================================================================
    // Tab navigation
    enum class ProcessorTab
    {
        TruePeakLimiter = 0,
        TransientShaper,
        MultibandDynamics,
        SpectralProcessing,
        AutoGainStaging,
        ReferenceMatching,
        SpatialAudio,
        StemSeparation,
        NumTabs
    };
    
    void showTab(ProcessorTab tab);
    ProcessorTab getCurrentTab() const { return currentTab; }
    
    //==============================================================================
    // JSON export for OSC/server communication
    juce::String toJSON() const;
    void loadFromJSON(const juce::String& json);
    
    //==============================================================================
    // Listener interface for parent components
    class Listener
    {
    public:
        virtual ~Listener() = default;
        virtual void masteringSettingsChanged(MasteringSuitePanel* panel) = 0;
        virtual void applyMasteringRequested(const juce::String& processorType, const juce::var& settings) = 0;
        virtual void analyzeReferenceRequested(const juce::File& file) = 0;
        virtual void separateStemsRequested(const juce::File& file) = 0;
    };
    
    void addListener(Listener* listener) { listeners.add(listener); }
    void removeListener(Listener* listener) { listeners.remove(listener); }
    
    //==============================================================================
    // Metering (called from audio thread via message manager)
    void updateMeters(float lufsShort, float lufsIntegrated, float truePeakL, float truePeakR);
    
private:
    void timerCallback() override;
    void setupTabs();
    void updateTabButtons();
    void createProcessorPanels();
    
    //==============================================================================
    // Tab buttons (icon-based for compact header)
    juce::OwnedArray<juce::TextButton> tabButtons;
    ProcessorTab currentTab = ProcessorTab::TruePeakLimiter;
    
    // Header components
    juce::Label titleLabel { {}, "Mastering Suite" };
    juce::ToggleButton bypassButton { "Bypass" };
    juce::TextButton presetButton { "Presets" };
    juce::ComboBox presetCombo;
    
    // Metering section (always visible)
    juce::Label lufsShortLabel { {}, "-∞" };
    juce::Label lufsIntegratedLabel { {}, "-∞" };
    juce::Label truePeakLabel { {}, "-∞ dB" };
    juce::Label lufsLabelTitle { {}, "LUFS-S" };
    juce::Label lufsIntLabelTitle { {}, "LUFS-I" };
    juce::Label truePeakLabelTitle { {}, "True Peak" };
    
    float currentLufsShort = -INFINITY;
    float currentLufsIntegrated = -INFINITY;
    float currentTruePeakL = -INFINITY;
    float currentTruePeakR = -INFINITY;
    
    // Processor panels (lazy-loaded)
    std::unique_ptr<TruePeakLimiterPanel> truePeakPanel;
    std::unique_ptr<TransientShaperPanel> transientPanel;
    std::unique_ptr<MultibandDynamicsPanel> multibandPanel;
    std::unique_ptr<SpectralProcessorPanel> spectralPanel;
    std::unique_ptr<AutoGainStagingPanel> autoGainPanel;
    std::unique_ptr<ReferenceMatchingPanel> referencePanel;
    std::unique_ptr<SpatialAudioPanel> spatialPanel;
    std::unique_ptr<StemSeparationPanel> stemPanel;
    
    // Listener list
    juce::ListenerList<Listener> listeners;
    
    // Tab names and icons
    static constexpr const char* tabNames[] = {
        "Limiter", "Transient", "Multiband", "Spectral",
        "Auto-Gain", "Reference", "Spatial", "Stems"
    };
    
    static constexpr const char* tabIcons[] = {
        "=", "!", "~", "^", "G", "R", "3D", "S"
    };
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(MasteringSuitePanel)
};

//==============================================================================
/**
    TruePeakLimiterPanel - ISP-aware limiter with lookahead
*/
class TruePeakLimiterPanel : public juce::Component
{
public:
    TruePeakLimiterPanel();
    
    void paint(juce::Graphics& g) override;
    void resized() override;
    
    juce::var toJSON() const;
    void loadFromJSON(const juce::var& json);
    
    std::function<void()> onSettingsChanged;
    
private:
    juce::Label titleLabel { {}, "True Peak Limiter" };
    juce::Label subtitleLabel { {}, "ITU-R BS.1770-4 compliant with ISP detection" };
    
    juce::Label ceilingLabel { {}, "Ceiling" };
    juce::Slider ceilingSlider;
    
    juce::Label releaseLabel { {}, "Release" };
    juce::Slider releaseSlider;
    
    juce::Label lookaheadLabel { {}, "Lookahead" };
    juce::Slider lookaheadSlider;
    
    juce::Label oversampleLabel { {}, "Oversample" };
    juce::ComboBox oversampleCombo;
    
    juce::ToggleButton enableISPDetection { "ISP Detection" };
    juce::ToggleButton enableAutoRelease { "Auto Release" };
    
    // Gain reduction meter
    juce::Label grLabel { {}, "GR" };
    float currentGR = 0.0f;
    
    void setupSlider(juce::Slider& slider, juce::Label& label, 
                     double min, double max, double step, const juce::String& suffix);
};

//==============================================================================
/**
    TransientShaperPanel - Attack and sustain control
*/
class TransientShaperPanel : public juce::Component
{
public:
    TransientShaperPanel();
    
    void paint(juce::Graphics& g) override;
    void resized() override;
    
    juce::var toJSON() const;
    void loadFromJSON(const juce::var& json);
    
    std::function<void()> onSettingsChanged;
    
private:
    juce::Label titleLabel { {}, "Transient Shaper" };
    juce::Label subtitleLabel { {}, "Envelope-follower based attack/sustain control" };
    
    juce::Label attackLabel { {}, "Attack" };
    juce::Slider attackSlider;
    
    juce::Label sustainLabel { {}, "Sustain" };
    juce::Slider sustainSlider;
    
    juce::Label outputLabel { {}, "Output" };
    juce::Slider outputSlider;
    
    juce::ToggleButton enableMultiband { "Multiband Mode" };
    
    juce::Label lowCrossLabel { {}, "Low X-Over" };
    juce::Slider lowCrossSlider;
    
    juce::Label highCrossLabel { {}, "High X-Over" };
    juce::Slider highCrossSlider;
    
    void setupSlider(juce::Slider& slider, juce::Label& label,
                     double min, double max, double step, const juce::String& suffix);
};

//==============================================================================
/**
    MultibandDynamicsPanel - 4-band dynamics with Linkwitz-Riley crossovers
*/
class MultibandDynamicsPanel : public juce::Component
{
public:
    MultibandDynamicsPanel();
    
    void paint(juce::Graphics& g) override;
    void resized() override;
    
    juce::var toJSON() const;
    void loadFromJSON(const juce::var& json);
    
    std::function<void()> onSettingsChanged;
    
private:
    juce::Label titleLabel { {}, "Multiband Dynamics" };
    juce::Label subtitleLabel { {}, "4-band LR4 crossovers with compression, expansion, saturation" };
    
    // Crossover frequencies
    juce::Label crossLabel { {}, "Crossover Frequencies" };
    juce::Slider lowMidSlider;  // Low/LowMid crossover
    juce::Slider midHighSlider; // LowMid/HighMid crossover
    juce::Slider highSlider;    // HighMid/High crossover
    
    // Band controls (simplified - full version would have per-band)
    struct BandControls
    {
        juce::Label nameLabel;
        juce::Slider thresholdSlider;
        juce::Slider ratioSlider;
        juce::Slider gainSlider;
        juce::ToggleButton soloButton;
        juce::ToggleButton bypassButton;
    };
    
    std::array<BandControls, 4> bands;
    
    juce::ComboBox processingModeCombo;  // Compress, Expand, Gate, Saturate
    
    void setupBandControls();
};

//==============================================================================
/**
    SpectralProcessorPanel - Dynamic EQ, De-esser, Harmonic Exciter
*/
class SpectralProcessorPanel : public juce::Component
{
public:
    SpectralProcessorPanel();
    
    void paint(juce::Graphics& g) override;
    void resized() override;
    
    juce::var toJSON() const;
    void loadFromJSON(const juce::var& json);
    
    std::function<void()> onSettingsChanged;
    
private:
    juce::Label titleLabel { {}, "Spectral Processing" };
    
    // Tab selector within this panel
    juce::TextButton dynEqTab { "Dynamic EQ" };
    juce::TextButton deesserTab { "De-esser" };
    juce::TextButton exciterTab { "Exciter" };
    
    int currentSubTab = 0;  // 0=DynEQ, 1=De-esser, 2=Exciter
    
    // Dynamic EQ controls
    juce::Label dynEqLabel { {}, "Frequency-dependent compression" };
    juce::Slider dynEqFreqSlider;
    juce::Slider dynEqQSlider;
    juce::Slider dynEqThreshSlider;
    juce::Slider dynEqRatioSlider;
    
    // De-esser controls
    juce::Label deesserLabel { {}, "Sibilance control" };
    juce::Slider deesserFreqSlider;
    juce::Slider deesserThreshSlider;
    juce::Slider deesserReductionSlider;
    juce::ComboBox deesserModeCombo;  // Wideband, Split-band
    
    // Exciter controls
    juce::Label exciterLabel { {}, "Harmonic enhancement" };
    juce::Slider exciterDriveSlider;
    juce::Slider exciterMixSlider;
    juce::Slider exciterFreqSlider;
    juce::ComboBox exciterTypeCombo;  // Tape, Tube, Transistor
    
    void showSubTab(int index);
};

//==============================================================================
/**
    AutoGainStagingPanel - LUFS-based automatic gain staging
*/
class AutoGainStagingPanel : public juce::Component
{
public:
    AutoGainStagingPanel();
    
    void paint(juce::Graphics& g) override;
    void resized() override;
    
    juce::var toJSON() const;
    void loadFromJSON(const juce::var& json);
    
    std::function<void()> onSettingsChanged;
    
private:
    juce::Label titleLabel { {}, "Auto-Gain Staging" };
    juce::Label subtitleLabel { {}, "ITU-R BS.1770-4 loudness normalization" };
    
    juce::Label targetLufsLabel { {}, "Target LUFS" };
    juce::Slider targetLufsSlider;
    
    juce::Label headroomLabel { {}, "Headroom" };
    juce::Slider headroomSlider;
    
    juce::Label genreLabel { {}, "Genre Template" };
    juce::ComboBox genreCombo;  // Pop, Hip-Hop, EDM, Classical, etc.
    
    juce::TextButton analyzeButton { "Analyze" };
    juce::TextButton applyButton { "Apply Gain" };
    
    // Analysis results display
    juce::Label currentLufsLabel { {}, "Current:" };
    juce::Label currentLufsValue { {}, "-- LUFS" };
    juce::Label suggestedGainLabel { {}, "Suggested:" };
    juce::Label suggestedGainValue { {}, "-- dB" };
    
    void populateGenreCombo();
};

//==============================================================================
/**
    ReferenceMatchingPanel - Match EQ/dynamics to reference track
*/
class ReferenceMatchingPanel : public juce::Component,
                               public juce::FileDragAndDropTarget
{
public:
    ReferenceMatchingPanel();
    
    void paint(juce::Graphics& g) override;
    void resized() override;
    
    // FileDragAndDropTarget
    bool isInterestedInFileDrag(const juce::StringArray& files) override;
    void filesDropped(const juce::StringArray& files, int x, int y) override;
    
    juce::var toJSON() const;
    void loadFromJSON(const juce::var& json);
    
    std::function<void(const juce::File&)> onAnalyzeReference;
    std::function<void()> onSettingsChanged;
    
private:
    juce::Label titleLabel { {}, "Reference Matching" };
    juce::Label subtitleLabel { {}, "Match your mix to a reference track" };
    
    juce::TextButton loadRefButton { "Load Reference" };
    juce::Label refFileLabel { {}, "Drop reference audio here..." };
    
    juce::Label matchAmountLabel { {}, "Match Amount" };
    juce::Slider matchAmountSlider;
    
    juce::ToggleButton matchEQButton { "Match EQ Curve" };
    juce::ToggleButton matchLoudnessButton { "Match Loudness" };
    juce::ToggleButton matchDynamicsButton { "Match Dynamics" };
    juce::ToggleButton matchStereoButton { "Match Stereo Width" };
    
    juce::TextButton analyzeButton { "Analyze" };
    juce::TextButton applyButton { "Apply Matching" };
    
    // Spectrum visualization placeholder
    juce::Rectangle<int> spectrumArea;
    
    juce::File loadedReference;
    bool referenceAnalyzed = false;
};

//==============================================================================
/**
    SpatialAudioPanel - Binaural, Upmixing, Atmos export
*/
class SpatialAudioPanel : public juce::Component
{
public:
    SpatialAudioPanel();
    
    void paint(juce::Graphics& g) override;
    void resized() override;
    
    juce::var toJSON() const;
    void loadFromJSON(const juce::var& json);
    
    std::function<void()> onSettingsChanged;
    
private:
    juce::Label titleLabel { {}, "Spatial Audio" };
    juce::Label subtitleLabel { {}, "Immersive audio rendering and export" };
    
    // Processing mode
    juce::Label modeLabel { {}, "Mode" };
    juce::ComboBox modeCombo;  // Binaural, Stereo-to-7.1.4, Ambisonics
    
    // Binaural controls
    juce::Label binauralLabel { {}, "Binaural Processing" };
    juce::ComboBox hrirCombo;  // HRTF database selection
    juce::Slider azimuthSlider;
    juce::Slider elevationSlider;
    juce::Slider distanceSlider;
    
    // Upmix controls
    juce::Label upmixLabel { {}, "Upmix Configuration" };
    juce::ComboBox outputFormatCombo;  // 5.1, 7.1, 7.1.4
    juce::Slider centerExtractSlider;
    juce::Slider surroundSlider;
    juce::Slider heightSlider;
    
    // Atmos export
    juce::Label atmosLabel { {}, "Dolby Atmos Export" };
    juce::TextButton exportAtmosButton { "Export ADM BWF" };
    juce::ToggleButton includeBedButton { "Include Bed Mix" };
    juce::ToggleButton includeObjectsButton { "Include Objects" };
    
    void setupModeCombo();
    void showModeControls(int modeIndex);
};

//==============================================================================
/**
    StemSeparationPanel - AI-powered stem separation
*/
class StemSeparationPanel : public juce::Component,
                            public juce::FileDragAndDropTarget
{
public:
    StemSeparationPanel();
    
    void paint(juce::Graphics& g) override;
    void resized() override;
    
    // FileDragAndDropTarget
    bool isInterestedInFileDrag(const juce::StringArray& files) override;
    void filesDropped(const juce::StringArray& files, int x, int y) override;
    
    juce::var toJSON() const;
    void loadFromJSON(const juce::var& json);
    
    std::function<void(const juce::File&)> onSeparateStems;
    std::function<void()> onSettingsChanged;
    
private:
    juce::Label titleLabel { {}, "Stem Separation" };
    juce::Label subtitleLabel { {}, "AI-powered source separation (Demucs/Spleeter)" };
    
    juce::TextButton loadButton { "Load Audio" };
    juce::Label fileLabel { {}, "Drop audio file here..." };
    
    juce::Label backendLabel { {}, "Backend" };
    juce::ComboBox backendCombo;  // Demucs, Spleeter
    
    juce::Label modelLabel { {}, "Model" };
    juce::ComboBox modelCombo;  // 2-stem, 4-stem, 6-stem
    
    juce::TextButton separateButton { "Separate Stems" };
    
    // Progress and results
    double separationProgress = 0.0;
    juce::ProgressBar progressBar { separationProgress };
    
    struct StemResult
    {
        juce::String name;
        juce::File path;
        bool enabled = true;
    };
    juce::OwnedArray<juce::ToggleButton> stemButtons;
    
    juce::TextButton exportStemsButton { "Export Selected" };
    juce::TextButton styleTransferButton { "Style Transfer" };
    
    juce::File loadedFile;
    bool separationComplete = false;
};

