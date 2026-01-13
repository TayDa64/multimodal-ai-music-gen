/*
  ==============================================================================

    ControlsPanel.cpp

  ==============================================================================
*/

#include "ControlsPanel.h"

ControlsPanel::ControlsPanel()
{
    titleLabel.setText("Generation Controls", juce::dontSendNotification);
    titleLabel.setJustificationType(juce::Justification::centredLeft);
    addAndMakeVisible(titleLabel);

    tensionShapeLabel.setText("Tension Arc Shape", juce::dontSendNotification);
    addAndMakeVisible(tensionShapeLabel);

    tensionShapeCombo.addItem("(auto)", 1);
    tensionShapeCombo.addItem("rising", 2);
    tensionShapeCombo.addItem("falling", 3);
    tensionShapeCombo.addItem("arch", 4);
    tensionShapeCombo.addItem("valley", 5);
    tensionShapeCombo.addItem("flat", 6);
    tensionShapeCombo.setSelectedId(1);
    addAndMakeVisible(tensionShapeCombo);

    tensionIntensityLabel.setText("Tension Intensity", juce::dontSendNotification);
    addAndMakeVisible(tensionIntensityLabel);

    tensionIntensitySlider.setRange(0.0, 1.0, 0.01);
    tensionIntensitySlider.setValue(0.0);
    tensionIntensitySlider.setTextBoxStyle(juce::Slider::TextBoxRight, false, 60, 18);
    addAndMakeVisible(tensionIntensitySlider);

    motifModeLabel.setText("Motif Mode", juce::dontSendNotification);
    addAndMakeVisible(motifModeLabel);

    motifModeCombo.addItem("(auto)", 1);
    motifModeCombo.addItem("on", 2);
    motifModeCombo.addItem("off", 3);
    motifModeCombo.setSelectedId(1);
    addAndMakeVisible(motifModeCombo);

    numMotifsLabel.setText("Num Motifs", juce::dontSendNotification);
    addAndMakeVisible(numMotifsLabel);

    numMotifsSlider.setRange(1, 3, 1);
    numMotifsSlider.setValue(1);
    numMotifsSlider.setTextBoxStyle(juce::Slider::TextBoxRight, false, 60, 18);
    addAndMakeVisible(numMotifsSlider);

    presetLabel.setText("Preset", juce::dontSendNotification);
    addAndMakeVisible(presetLabel);

    presetEditor.setTextToShowWhenEmpty("(optional)", juce::Colours::grey);
    addAndMakeVisible(presetEditor);

    stylePresetLabel.setText("Style Preset", juce::dontSendNotification);
    addAndMakeVisible(stylePresetLabel);

    stylePresetEditor.setTextToShowWhenEmpty("(optional)", juce::Colours::grey);
    addAndMakeVisible(stylePresetEditor);

    productionPresetLabel.setText("Production Preset", juce::dontSendNotification);
    addAndMakeVisible(productionPresetLabel);

    productionPresetEditor.setTextToShowWhenEmpty("(optional)", juce::Colours::grey);
    addAndMakeVisible(productionPresetEditor);

    seedLabel.setText("Seed", juce::dontSendNotification);
    addAndMakeVisible(seedLabel);

    seedEditor.setTextToShowWhenEmpty("(optional integer)", juce::Colours::grey);
    addAndMakeVisible(seedEditor);

    durationBarsLabel.setText("Duration (Bars)", juce::dontSendNotification);
    addAndMakeVisible(durationBarsLabel);

    durationBarsSlider.setRange(1, 128, 1);
    durationBarsSlider.setValue(8);
    durationBarsSlider.setTextBoxStyle(juce::Slider::TextBoxRight, false, 60, 18);
    addAndMakeVisible(durationBarsSlider);

    applyGlobalButton.onClick = [this]() {
        listeners.call(&Listener::controlsApplyGlobalRequested, buildOverrides());
    };
    addAndMakeVisible(applyGlobalButton);

    clearGlobalButton.onClick = [this]() {
        listeners.call(&Listener::controlsClearGlobalRequested, juce::StringArray{});
    };
    addAndMakeVisible(clearGlobalButton);

    nextScopeLabel.setText("Apply Next To", juce::dontSendNotification);
    addAndMakeVisible(nextScopeLabel);

    nextScopeCombo.addItem("Both (Generate + Regenerate)", 1);
    nextScopeCombo.addItem("Generate only", 2);
    nextScopeCombo.addItem("Regenerate only", 3);
    nextScopeCombo.setSelectedId(1);
    addAndMakeVisible(nextScopeCombo);

    nextStatusLabel.setText("Next overrides: (none)", juce::dontSendNotification);
    nextStatusLabel.setJustificationType(juce::Justification::centredLeft);
    nextStatusLabel.setColour(juce::Label::textColourId, juce::Colours::grey);
    addAndMakeVisible(nextStatusLabel);

    applyNextButton.onClick = [this]() {
        NextScope scope = NextScope::Both;
        const auto selected = nextScopeCombo.getSelectedId();
        if (selected == 2)
            scope = NextScope::GenerateOnly;
        else if (selected == 3)
            scope = NextScope::RegenerateOnly;

        listeners.call(&Listener::controlsApplyNextRequestRequested, buildOverrides(), scope);
    };
    addAndMakeVisible(applyNextButton);

    clearNextButton.onClick = [this]() {
        listeners.call(&Listener::controlsClearNextRequestRequested);
    };
    addAndMakeVisible(clearNextButton);

    clearNextButton.setEnabled(false);
}

void ControlsPanel::addListener(Listener* listener)
{
    listeners.add(listener);
}

void ControlsPanel::removeListener(Listener* listener)
{
    listeners.remove(listener);
}

void ControlsPanel::setNextOverridesIndicator(bool forGenerate, bool forRegenerate)
{
    if (!forGenerate && !forRegenerate)
    {
        nextStatusLabel.setText("Next overrides: (none)", juce::dontSendNotification);
        clearNextButton.setEnabled(false);
        return;
    }

    if (forGenerate && forRegenerate)
        nextStatusLabel.setText("Next overrides armed: Generate + Regenerate", juce::dontSendNotification);
    else if (forGenerate)
        nextStatusLabel.setText("Next overrides armed: Generate", juce::dontSendNotification);
    else
        nextStatusLabel.setText("Next overrides armed: Regenerate", juce::dontSendNotification);

    clearNextButton.setEnabled(true);
}

juce::var ControlsPanel::buildOverrides() const
{
    juce::DynamicObject::Ptr overrides = new juce::DynamicObject();

    // tension_arc_shape
    {
        const auto selectedId = tensionShapeCombo.getSelectedId();
        if (selectedId > 1)
            overrides->setProperty("tension_arc_shape", tensionShapeCombo.getText());
    }

    // tension_intensity (0 means "unset" for global controls)
    {
        const double intensity = tensionIntensitySlider.getValue();
        if (intensity > 0.0)
            overrides->setProperty("tension_intensity", intensity);
    }

    // motif_mode
    {
        const auto selectedId = motifModeCombo.getSelectedId();
        if (selectedId > 1)
            overrides->setProperty("motif_mode", motifModeCombo.getText());
    }

    // num_motifs
    overrides->setProperty("num_motifs", (int) numMotifsSlider.getValue());

    // presets
    if (presetEditor.getText().trim().isNotEmpty())
        overrides->setProperty("preset", presetEditor.getText().trim());

    if (stylePresetEditor.getText().trim().isNotEmpty())
        overrides->setProperty("style_preset", stylePresetEditor.getText().trim());

    if (productionPresetEditor.getText().trim().isNotEmpty())
        overrides->setProperty("production_preset", productionPresetEditor.getText().trim());

    // seed
    if (seedEditor.getText().trim().isNotEmpty())
    {
        const auto seedText = seedEditor.getText().trim();
        const int seedValue = seedText.getIntValue();
        if (seedValue != 0 || seedText == "0")
            overrides->setProperty("seed", seedValue);
    }

    // duration_bars (server also accepts legacy "bars" per-request, but global uses duration_bars)
    overrides->setProperty("duration_bars", (int) durationBarsSlider.getValue());

    return juce::var(overrides.get());
}

void ControlsPanel::resized()
{
    auto area = getLocalBounds().reduced(12);

    titleLabel.setBounds(area.removeFromTop(24));
    area.removeFromTop(10);

    auto row = [&](juce::Component& left, juce::Component& right, int height = 24) {
        auto r = area.removeFromTop(height);
        auto leftW = (int) (r.getWidth() * 0.45f);
        left.setBounds(r.removeFromLeft(leftW));
        right.setBounds(r);
        area.removeFromTop(6);
    };

    row(tensionShapeLabel, tensionShapeCombo);
    row(tensionIntensityLabel, tensionIntensitySlider);
    row(motifModeLabel, motifModeCombo);
    row(numMotifsLabel, numMotifsSlider);
    row(presetLabel, presetEditor);
    row(stylePresetLabel, stylePresetEditor);
    row(productionPresetLabel, productionPresetEditor);
    row(seedLabel, seedEditor);
    row(durationBarsLabel, durationBarsSlider);

    area.removeFromTop(8);

    row(nextScopeLabel, nextScopeCombo);
    nextStatusLabel.setBounds(area.removeFromTop(20));
    area.removeFromTop(10);

    auto row1 = area.removeFromTop(28);
    applyGlobalButton.setBounds(row1.removeFromLeft((row1.getWidth() / 2) - 4));
    row1.removeFromLeft(8);
    clearGlobalButton.setBounds(row1);

    area.removeFromTop(8);
    auto row2 = area.removeFromTop(28);
    applyNextButton.setBounds(row2.removeFromLeft((row2.getWidth() / 2) - 4));
    row2.removeFromLeft(8);
    clearNextButton.setBounds(row2);
}
