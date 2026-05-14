/*
  ==============================================================================

    ControlsPanel.cpp

  ==============================================================================
*/

#include "ControlsPanel.h"
#include "Theme/ColourScheme.h"
#include "Theme/LayoutConstants.h"

namespace
{
    void styleLabel(juce::Label& label, bool emphasis = false)
    {
        label.setColour(juce::Label::textColourId, emphasis ? AppColours::textPrimary : AppColours::textSecondary);
        label.setFont(juce::Font(emphasis ? Layout::fontSizeLG : Layout::fontSizeSM,
                                 emphasis ? juce::Font::bold : juce::Font::plain));
    }

    void styleCombo(juce::ComboBox& combo)
    {
        combo.setColour(juce::ComboBox::backgroundColourId, AppColours::inputBg);
        combo.setColour(juce::ComboBox::outlineColourId, AppColours::inputBorder);
        combo.setColour(juce::ComboBox::focusedOutlineColourId, AppColours::focusRing);
        combo.setColour(juce::ComboBox::textColourId, AppColours::textPrimary);
        combo.setColour(juce::ComboBox::arrowColourId, AppColours::primaryLight);
    }

    void styleEditor(juce::TextEditor& editor)
    {
        editor.setColour(juce::TextEditor::backgroundColourId, AppColours::inputBg);
        editor.setColour(juce::TextEditor::outlineColourId, AppColours::inputBorder);
        editor.setColour(juce::TextEditor::focusedOutlineColourId, AppColours::focusRing);
        editor.setColour(juce::TextEditor::textColourId, AppColours::textPrimary);
        editor.setColour(juce::TextEditor::highlightColourId, AppColours::primary.withAlpha(0.35f));
    }

    void styleSlider(juce::Slider& slider)
    {
        slider.setColour(juce::Slider::thumbColourId, AppColours::primaryLight);
        slider.setColour(juce::Slider::trackColourId, AppColours::primary.withAlpha(0.75f));
        slider.setColour(juce::Slider::backgroundColourId, AppColours::surfaceSunken);
        slider.setColour(juce::Slider::textBoxBackgroundColourId, AppColours::inputBg);
        slider.setColour(juce::Slider::textBoxOutlineColourId, AppColours::inputBorder);
        slider.setColour(juce::Slider::textBoxTextColourId, AppColours::textPrimary);
    }

    void styleButton(juce::TextButton& button, juce::Colour colour)
    {
        button.setColour(juce::TextButton::buttonColourId, colour);
        button.setColour(juce::TextButton::buttonOnColourId, colour.brighter(0.12f));
        button.setColour(juce::TextButton::textColourOffId, AppColours::textPrimary);
        button.setColour(juce::TextButton::textColourOnId, AppColours::textPrimary);
    }

    void drawSection(juce::Graphics& g, juce::Rectangle<float> bounds, const juce::String& title)
    {
        juce::ignoreUnused(title);

        g.setColour(AppColours::surfaceRaised.withAlpha(0.46f));
        g.fillRoundedRectangle(bounds, Layout::borderRadiusMD);
        g.setColour(AppColours::borderSubtle);
        g.drawRoundedRectangle(bounds, Layout::borderRadiusMD, 1.0f);
    }
}

ControlsPanel::ControlsPanel()
{
    titleLabel.setText("Generation Controls · Global + Next", juce::dontSendNotification);
    titleLabel.setJustificationType(juce::Justification::centredLeft);
    styleLabel(titleLabel, true);
    addAndMakeVisible(titleLabel);

    tensionShapeLabel.setText("Tension Arc Shape", juce::dontSendNotification);
    styleLabel(tensionShapeLabel);
    addAndMakeVisible(tensionShapeLabel);

    tensionShapeCombo.addItem("(auto)", 1);
    tensionShapeCombo.addItem("rising", 2);
    tensionShapeCombo.addItem("falling", 3);
    tensionShapeCombo.addItem("arch", 4);
    tensionShapeCombo.addItem("valley", 5);
    tensionShapeCombo.addItem("flat", 6);
    tensionShapeCombo.setSelectedId(1);
    styleCombo(tensionShapeCombo);
    addAndMakeVisible(tensionShapeCombo);

    tensionIntensityLabel.setText("Tension Intensity", juce::dontSendNotification);
    styleLabel(tensionIntensityLabel);
    addAndMakeVisible(tensionIntensityLabel);

    tensionIntensitySlider.setRange(0.0, 1.0, 0.01);
    tensionIntensitySlider.setValue(0.0);
    tensionIntensitySlider.setTextBoxStyle(juce::Slider::TextBoxRight, false, 60, 18);
    styleSlider(tensionIntensitySlider);
    addAndMakeVisible(tensionIntensitySlider);

    motifModeLabel.setText("Motif Mode", juce::dontSendNotification);
    styleLabel(motifModeLabel);
    addAndMakeVisible(motifModeLabel);

    motifModeCombo.addItem("(auto)", 1);
    motifModeCombo.addItem("on", 2);
    motifModeCombo.addItem("off", 3);
    motifModeCombo.setSelectedId(1);
    styleCombo(motifModeCombo);
    addAndMakeVisible(motifModeCombo);

    numMotifsLabel.setText("Num Motifs", juce::dontSendNotification);
    styleLabel(numMotifsLabel);
    addAndMakeVisible(numMotifsLabel);

    numMotifsSlider.setRange(1, 3, 1);
    numMotifsSlider.setValue(1);
    numMotifsSlider.setTextBoxStyle(juce::Slider::TextBoxRight, false, 60, 18);
    styleSlider(numMotifsSlider);
    addAndMakeVisible(numMotifsSlider);

    presetLabel.setText("Preset", juce::dontSendNotification);
    styleLabel(presetLabel);
    addAndMakeVisible(presetLabel);

    presetEditor.setTextToShowWhenEmpty("(optional)", juce::Colours::grey);
    styleEditor(presetEditor);
    addAndMakeVisible(presetEditor);

    stylePresetLabel.setText("Style Preset", juce::dontSendNotification);
    styleLabel(stylePresetLabel);
    addAndMakeVisible(stylePresetLabel);

    stylePresetEditor.setTextToShowWhenEmpty("(optional)", juce::Colours::grey);
    styleEditor(stylePresetEditor);
    addAndMakeVisible(stylePresetEditor);

    productionPresetLabel.setText("Production Preset", juce::dontSendNotification);
    styleLabel(productionPresetLabel);
    addAndMakeVisible(productionPresetLabel);

    productionPresetEditor.setTextToShowWhenEmpty("(optional)", juce::Colours::grey);
    styleEditor(productionPresetEditor);
    addAndMakeVisible(productionPresetEditor);

    seedLabel.setText("Seed", juce::dontSendNotification);
    styleLabel(seedLabel);
    addAndMakeVisible(seedLabel);

    seedEditor.setTextToShowWhenEmpty("(optional integer)", juce::Colours::grey);
    styleEditor(seedEditor);
    addAndMakeVisible(seedEditor);

    durationBarsLabel.setText("Duration (Bars)", juce::dontSendNotification);
    styleLabel(durationBarsLabel);
    addAndMakeVisible(durationBarsLabel);

    durationBarsSlider.setRange(1, 128, 1);
    durationBarsSlider.setValue(8);
    durationBarsSlider.setTextBoxStyle(juce::Slider::TextBoxRight, false, 60, 18);
    styleSlider(durationBarsSlider);
    addAndMakeVisible(durationBarsSlider);

    applyGlobalButton.setButtonText("Apply Global Defaults");
    styleButton(applyGlobalButton, AppColours::primaryDark);
    applyGlobalButton.onClick = [this]() {
        listeners.call(&Listener::controlsApplyGlobalRequested, buildOverrides());
    };
    addAndMakeVisible(applyGlobalButton);

    clearGlobalButton.setButtonText("Clear Global Defaults");
    styleButton(clearGlobalButton, AppColours::buttonBg);
    clearGlobalButton.onClick = [this]() {
        listeners.call(&Listener::controlsClearGlobalRequested, juce::StringArray{});
    };
    addAndMakeVisible(clearGlobalButton);

    nextScopeLabel.setText("Apply Next To", juce::dontSendNotification);
    styleLabel(nextScopeLabel);
    addAndMakeVisible(nextScopeLabel);

    nextScopeCombo.addItem("Both (Generate + Regenerate)", 1);
    nextScopeCombo.addItem("Generate only", 2);
    nextScopeCombo.addItem("Regenerate only", 3);
    nextScopeCombo.setSelectedId(1);
    styleCombo(nextScopeCombo);
    addAndMakeVisible(nextScopeCombo);

    nextStatusLabel.setText("Next overrides: (none)", juce::dontSendNotification);
    nextStatusLabel.setJustificationType(juce::Justification::centredLeft);
    nextStatusLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    nextStatusLabel.setFont(juce::Font(Layout::fontSizeSM, juce::Font::bold));
    addAndMakeVisible(nextStatusLabel);

    applyNextButton.setButtonText("Apply to Next Request");
    styleButton(applyNextButton, AppColours::accent.darker(0.1f));
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

    clearNextButton.setButtonText("Clear Next Request");
    styleButton(clearNextButton, AppColours::buttonBg);
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
        nextStatusLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
        clearNextButton.setEnabled(false);
        repaint();
        return;
    }

    if (forGenerate && forRegenerate)
        nextStatusLabel.setText("Next overrides armed: Generate + Regenerate", juce::dontSendNotification);
    else if (forGenerate)
        nextStatusLabel.setText("Next overrides armed: Generate", juce::dontSendNotification);
    else
        nextStatusLabel.setText("Next overrides armed: Regenerate", juce::dontSendNotification);

    nextStatusLabel.setColour(juce::Label::textColourId, AppColours::warning);
    clearNextButton.setEnabled(true);
    repaint();
}

void ControlsPanel::paint(juce::Graphics& g)
{
    auto bounds = getLocalBounds().toFloat().reduced(1.0f);
    g.setColour(AppColours::surface.withAlpha(0.82f));
    g.fillRoundedRectangle(bounds, Layout::borderRadiusLG);
    g.setColour(AppColours::borderSubtle);
    g.drawRoundedRectangle(bounds, Layout::borderRadiusLG, 1.0f);

    auto area = getLocalBounds().reduced(Layout::paddingLG).toFloat();
    area.removeFromTop(34.0f);
    auto intentSection = area.removeFromTop(9.0f * (float) (Layout::panelRowHeight + Layout::componentGapMD) + 8.0f);
    drawSection(g, intentSection.expanded(4.0f, 2.0f), "CREATIVE INTENT + PRESETS");

    area.removeFromTop(8.0f);
    auto scopeSection = area.removeFromTop(120.0f);
    drawSection(g, scopeSection.expanded(4.0f, 2.0f), "OVERRIDE SCOPE");
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
    auto area = getLocalBounds().reduced(Layout::paddingLG);

    titleLabel.setBounds(area.removeFromTop(Layout::panelHeaderHeight));
    area.removeFromTop(Layout::panelSectionGap);

    auto row = [&](juce::Component& left, juce::Component& right, int height = Layout::panelRowHeight) {
        auto r = area.removeFromTop(height);
        auto leftW = (int) (r.getWidth() * 0.45f);
        left.setBounds(r.removeFromLeft(leftW));
        right.setBounds(r);
        area.removeFromTop(Layout::componentGapMD);
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
