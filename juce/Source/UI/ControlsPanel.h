/*
  ==============================================================================

    ControlsPanel.h

    UI for Phase 5.2 generation controls (tension/motif/presets/seed/duration).

  ==============================================================================
*/

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>

class ControlsPanel : public juce::Component
{
public:
  enum class NextScope
  {
    Both = 0,
    GenerateOnly,
    RegenerateOnly
  };

    class Listener
    {
    public:
        virtual ~Listener() = default;
        virtual void controlsApplyGlobalRequested(const juce::var& overrides) { juce::ignoreUnused(overrides); }
        virtual void controlsClearGlobalRequested(const juce::StringArray& keys) { juce::ignoreUnused(keys); }

    virtual void controlsApplyNextRequestRequested(const juce::var& overrides, NextScope scope)
    {
      juce::ignoreUnused(overrides, scope);
    }

    virtual void controlsClearNextRequestRequested() {}
    };

    ControlsPanel();

    void addListener(Listener* listener);
    void removeListener(Listener* listener);

    /** Update the UI to reflect which apply-once overrides are currently armed. */
    void setNextOverridesIndicator(bool forGenerate, bool forRegenerate);

    void resized() override;

private:
    juce::ListenerList<Listener> listeners;

    // Controls
    juce::Label titleLabel;

    juce::Label tensionShapeLabel;
    juce::ComboBox tensionShapeCombo;

    juce::Label tensionIntensityLabel;
    juce::Slider tensionIntensitySlider;

    juce::Label motifModeLabel;
    juce::ComboBox motifModeCombo;

    juce::Label numMotifsLabel;
    juce::Slider numMotifsSlider;

    juce::Label presetLabel;
    juce::TextEditor presetEditor;

    juce::Label stylePresetLabel;
    juce::TextEditor stylePresetEditor;

    juce::Label productionPresetLabel;
    juce::TextEditor productionPresetEditor;

    juce::Label seedLabel;
    juce::TextEditor seedEditor;

    juce::Label durationBarsLabel;
    juce::Slider durationBarsSlider;

    // Actions
    juce::TextButton applyGlobalButton { "Apply Global" };
    juce::TextButton clearGlobalButton { "Clear Global" };

    juce::Label nextScopeLabel;
    juce::ComboBox nextScopeCombo;
    juce::Label nextStatusLabel;

    juce::TextButton applyNextButton { "Apply Next" };
    juce::TextButton clearNextButton { "Clear Next" };

    juce::var buildOverrides() const;
};
