/*
  ==============================================================================

    MasteringSuitePanel.cpp
    
    Implementation of the professional mastering suite UI.

  ==============================================================================
*/

#include "MasteringSuitePanel.h"

//==============================================================================
// MasteringSuitePanel
//==============================================================================

MasteringSuitePanel::MasteringSuitePanel()
{
    // Title and header
    titleLabel.setFont(juce::Font(18.0f, juce::Font::bold));
    titleLabel.setColour(juce::Label::textColourId, juce::Colours::white);
    addAndMakeVisible(titleLabel);
    
    bypassButton.setColour(juce::ToggleButton::textColourId, AppColours::textSecondary);
    bypassButton.setColour(juce::ToggleButton::tickColourId, AppColours::warning);
    addAndMakeVisible(bypassButton);
    
    presetButton.setColour(juce::TextButton::buttonColourId, AppColours::surface.brighter(0.1f));
    presetButton.onClick = [this]() {
        // Show preset menu
        juce::PopupMenu menu;
        menu.addItem(1, "Save Preset...");
        menu.addItem(2, "Load Preset...");
        menu.addSeparator();
        menu.addItem(10, "Streaming Master (-14 LUFS)");
        menu.addItem(11, "Club Master (-9 LUFS)");
        menu.addItem(12, "Vinyl Master (-12 LUFS)");
        menu.addItem(13, "Broadcast (-24 LUFS)");
        menu.showMenuAsync(juce::PopupMenu::Options().withTargetComponent(&presetButton));
    };
    addAndMakeVisible(presetButton);
    
    // Metering labels
    auto setupMeterLabel = [](juce::Label& label, const juce::String& text, float fontSize, juce::Colour colour) {
        label.setText(text, juce::dontSendNotification);
        label.setFont(juce::Font(fontSize));
        label.setColour(juce::Label::textColourId, colour);
        label.setJustificationType(juce::Justification::centred);
    };
    
    setupMeterLabel(lufsLabelTitle, "LUFS-S", 10.0f, AppColours::textSecondary);
    setupMeterLabel(lufsIntLabelTitle, "LUFS-I", 10.0f, AppColours::textSecondary);
    setupMeterLabel(truePeakLabelTitle, "True Peak", 10.0f, AppColours::textSecondary);
    
    setupMeterLabel(lufsShortLabel, "-∞", 14.0f, AppColours::primary);
    setupMeterLabel(lufsIntegratedLabel, "-∞", 14.0f, AppColours::success);
    setupMeterLabel(truePeakLabel, "-∞ dB", 14.0f, AppColours::warning);
    
    addAndMakeVisible(lufsLabelTitle);
    addAndMakeVisible(lufsIntLabelTitle);
    addAndMakeVisible(truePeakLabelTitle);
    addAndMakeVisible(lufsShortLabel);
    addAndMakeVisible(lufsIntegratedLabel);
    addAndMakeVisible(truePeakLabel);
    
    setupTabs();
    createProcessorPanels();
    
    // Show first tab
    showTab(ProcessorTab::TruePeakLimiter);
    
    // Start metering update timer
    startTimerHz(30);
}

MasteringSuitePanel::~MasteringSuitePanel()
{
    stopTimer();
}

void MasteringSuitePanel::setupTabs()
{
    for (int i = 0; i < static_cast<int>(ProcessorTab::NumTabs); ++i)
    {
        auto* button = tabButtons.add(new juce::TextButton(tabNames[i]));
        button->setColour(juce::TextButton::buttonColourId, AppColours::surfaceAlt);
        button->setColour(juce::TextButton::textColourOffId, AppColours::textSecondary);
        button->onClick = [this, i]() {
            showTab(static_cast<ProcessorTab>(i));
        };
        addAndMakeVisible(button);
    }
}

void MasteringSuitePanel::createProcessorPanels()
{
    truePeakPanel = std::make_unique<TruePeakLimiterPanel>();
    truePeakPanel->onSettingsChanged = [this]() {
        listeners.call([this](Listener& l) { l.masteringSettingsChanged(this); });
    };
    addAndMakeVisible(*truePeakPanel);
    
    transientPanel = std::make_unique<TransientShaperPanel>();
    transientPanel->onSettingsChanged = [this]() {
        listeners.call([this](Listener& l) { l.masteringSettingsChanged(this); });
    };
    addChildComponent(*transientPanel);
    
    multibandPanel = std::make_unique<MultibandDynamicsPanel>();
    multibandPanel->onSettingsChanged = [this]() {
        listeners.call([this](Listener& l) { l.masteringSettingsChanged(this); });
    };
    addChildComponent(*multibandPanel);
    
    spectralPanel = std::make_unique<SpectralProcessorPanel>();
    spectralPanel->onSettingsChanged = [this]() {
        listeners.call([this](Listener& l) { l.masteringSettingsChanged(this); });
    };
    addChildComponent(*spectralPanel);
    
    autoGainPanel = std::make_unique<AutoGainStagingPanel>();
    autoGainPanel->onSettingsChanged = [this]() {
        listeners.call([this](Listener& l) { l.masteringSettingsChanged(this); });
    };
    addChildComponent(*autoGainPanel);
    
    referencePanel = std::make_unique<ReferenceMatchingPanel>();
    referencePanel->onAnalyzeReference = [this](const juce::File& file) {
        listeners.call([this, &file](Listener& l) { l.analyzeReferenceRequested(file); });
    };
    referencePanel->onSettingsChanged = [this]() {
        listeners.call([this](Listener& l) { l.masteringSettingsChanged(this); });
    };
    addChildComponent(*referencePanel);
    
    spatialPanel = std::make_unique<SpatialAudioPanel>();
    spatialPanel->onSettingsChanged = [this]() {
        listeners.call([this](Listener& l) { l.masteringSettingsChanged(this); });
    };
    addChildComponent(*spatialPanel);
    
    stemPanel = std::make_unique<StemSeparationPanel>();
    stemPanel->onSeparateStems = [this](const juce::File& file) {
        listeners.call([this, &file](Listener& l) { l.separateStemsRequested(file); });
    };
    stemPanel->onSettingsChanged = [this]() {
        listeners.call([this](Listener& l) { l.masteringSettingsChanged(this); });
    };
    addChildComponent(*stemPanel);
}

void MasteringSuitePanel::paint(juce::Graphics& g)
{
    // Background
    g.fillAll(AppColours::surface.darker(0.1f));
    
    // Header background
    auto headerArea = getLocalBounds().removeFromTop(50);
    g.setColour(AppColours::surface);
    g.fillRect(headerArea);
    
    // Tab bar background
    auto tabBarArea = getLocalBounds().withTrimmedTop(50).removeFromTop(36);
    g.setColour(AppColours::surfaceAlt.darker(0.1f));
    g.fillRect(tabBarArea);
    
    // Metering area background (right side of header)
    auto meterBg = headerArea.removeFromRight(260).reduced(4);
    g.setColour(juce::Colours::black.withAlpha(0.3f));
    g.fillRoundedRectangle(meterBg.toFloat(), 4.0f);
    
    // Draw True Peak indicator color based on level
    if (currentTruePeakL > -1.0f || currentTruePeakR > -1.0f)
    {
        g.setColour(AppColours::error);
    }
    else if (currentTruePeakL > -3.0f || currentTruePeakR > -3.0f)
    {
        g.setColour(AppColours::warning);
    }
    else
    {
        g.setColour(AppColours::success);
    }
    // Draw small indicator
    auto indicatorRect = truePeakLabel.getBounds().withWidth(4).withX(truePeakLabel.getX() - 6);
    g.fillRoundedRectangle(indicatorRect.toFloat(), 2.0f);
}

void MasteringSuitePanel::resized()
{
    auto bounds = getLocalBounds();
    
    // Header (50px)
    auto header = bounds.removeFromTop(50).reduced(8, 8);
    
    titleLabel.setBounds(header.removeFromLeft(150));
    bypassButton.setBounds(header.removeFromLeft(80));
    presetButton.setBounds(header.removeFromLeft(80));
    
    // Metering section (right side of header)
    auto meterArea = header.removeFromRight(240);
    int meterWidth = 75;
    
    auto lufsShortArea = meterArea.removeFromLeft(meterWidth);
    lufsLabelTitle.setBounds(lufsShortArea.removeFromTop(14));
    lufsShortLabel.setBounds(lufsShortArea);
    
    auto lufsIntArea = meterArea.removeFromLeft(meterWidth);
    lufsIntLabelTitle.setBounds(lufsIntArea.removeFromTop(14));
    lufsIntegratedLabel.setBounds(lufsIntArea);
    
    auto truePeakArea = meterArea.removeFromLeft(meterWidth);
    truePeakLabelTitle.setBounds(truePeakArea.removeFromTop(14));
    truePeakLabel.setBounds(truePeakArea);
    
    // Tab bar (36px)
    auto tabBar = bounds.removeFromTop(36).reduced(4, 2);
    int tabWidth = juce::jmin(90, tabBar.getWidth() / static_cast<int>(ProcessorTab::NumTabs));
    
    for (auto* button : tabButtons)
    {
        button->setBounds(tabBar.removeFromLeft(tabWidth).reduced(2, 0));
    }
    
    // Content area
    auto contentArea = bounds.reduced(8);
    
    if (truePeakPanel) truePeakPanel->setBounds(contentArea);
    if (transientPanel) transientPanel->setBounds(contentArea);
    if (multibandPanel) multibandPanel->setBounds(contentArea);
    if (spectralPanel) spectralPanel->setBounds(contentArea);
    if (autoGainPanel) autoGainPanel->setBounds(contentArea);
    if (referencePanel) referencePanel->setBounds(contentArea);
    if (spatialPanel) spatialPanel->setBounds(contentArea);
    if (stemPanel) stemPanel->setBounds(contentArea);
}

void MasteringSuitePanel::showTab(ProcessorTab tab)
{
    currentTab = tab;
    
    // Hide all panels
    if (truePeakPanel) truePeakPanel->setVisible(false);
    if (transientPanel) transientPanel->setVisible(false);
    if (multibandPanel) multibandPanel->setVisible(false);
    if (spectralPanel) spectralPanel->setVisible(false);
    if (autoGainPanel) autoGainPanel->setVisible(false);
    if (referencePanel) referencePanel->setVisible(false);
    if (spatialPanel) spatialPanel->setVisible(false);
    if (stemPanel) stemPanel->setVisible(false);
    
    // Show selected panel
    switch (tab)
    {
        case ProcessorTab::TruePeakLimiter:  if (truePeakPanel) truePeakPanel->setVisible(true); break;
        case ProcessorTab::TransientShaper:  if (transientPanel) transientPanel->setVisible(true); break;
        case ProcessorTab::MultibandDynamics: if (multibandPanel) multibandPanel->setVisible(true); break;
        case ProcessorTab::SpectralProcessing: if (spectralPanel) spectralPanel->setVisible(true); break;
        case ProcessorTab::AutoGainStaging:  if (autoGainPanel) autoGainPanel->setVisible(true); break;
        case ProcessorTab::ReferenceMatching: if (referencePanel) referencePanel->setVisible(true); break;
        case ProcessorTab::SpatialAudio:     if (spatialPanel) spatialPanel->setVisible(true); break;
        case ProcessorTab::StemSeparation:   if (stemPanel) stemPanel->setVisible(true); break;
        default: break;
    }
    
    updateTabButtons();
    repaint();
}

void MasteringSuitePanel::updateTabButtons()
{
    for (int i = 0; i < tabButtons.size(); ++i)
    {
        bool isActive = (i == static_cast<int>(currentTab));
        
        tabButtons[i]->setColour(juce::TextButton::buttonColourId,
                                  isActive ? AppColours::primary : AppColours::surfaceAlt);
        tabButtons[i]->setColour(juce::TextButton::textColourOffId,
                                  isActive ? juce::Colours::white : AppColours::textSecondary);
    }
}

void MasteringSuitePanel::updateMeters(float lufsShort, float lufsIntegrated, float truePeakL, float truePeakR)
{
    currentLufsShort = lufsShort;
    currentLufsIntegrated = lufsIntegrated;
    currentTruePeakL = truePeakL;
    currentTruePeakR = truePeakR;
}

void MasteringSuitePanel::timerCallback()
{
    // Update meter displays
    auto formatLufs = [](float lufs) -> juce::String {
        if (lufs <= -70.0f || std::isinf(lufs))
            return juce::String::fromUTF8("-∞");
        return juce::String(lufs, 1);
    };
    
    auto formatTruePeak = [](float peak) -> juce::String {
        if (peak <= -70.0f || std::isinf(peak))
            return juce::String::fromUTF8("-∞ dB");
        return juce::String(peak, 1) + " dB";
    };
    
    lufsShortLabel.setText(formatLufs(currentLufsShort), juce::dontSendNotification);
    lufsIntegratedLabel.setText(formatLufs(currentLufsIntegrated), juce::dontSendNotification);
    
    float maxTruePeak = juce::jmax(currentTruePeakL, currentTruePeakR);
    truePeakLabel.setText(formatTruePeak(maxTruePeak), juce::dontSendNotification);
    
    // Update true peak color
    if (maxTruePeak > -1.0f)
        truePeakLabel.setColour(juce::Label::textColourId, AppColours::error);
    else if (maxTruePeak > -3.0f)
        truePeakLabel.setColour(juce::Label::textColourId, AppColours::warning);
    else
        truePeakLabel.setColour(juce::Label::textColourId, AppColours::success);
}

juce::String MasteringSuitePanel::toJSON() const
{
    auto* root = new juce::DynamicObject();
    
    root->setProperty("bypass", bypassButton.getToggleState());
    root->setProperty("currentTab", static_cast<int>(currentTab));
    
    if (truePeakPanel) root->setProperty("truePeakLimiter", truePeakPanel->toJSON());
    if (transientPanel) root->setProperty("transientShaper", transientPanel->toJSON());
    if (multibandPanel) root->setProperty("multibandDynamics", multibandPanel->toJSON());
    if (spectralPanel) root->setProperty("spectralProcessing", spectralPanel->toJSON());
    if (autoGainPanel) root->setProperty("autoGainStaging", autoGainPanel->toJSON());
    if (referencePanel) root->setProperty("referenceMatching", referencePanel->toJSON());
    if (spatialPanel) root->setProperty("spatialAudio", spatialPanel->toJSON());
    if (stemPanel) root->setProperty("stemSeparation", stemPanel->toJSON());
    
    return juce::JSON::toString(juce::var(root));
}

void MasteringSuitePanel::loadFromJSON(const juce::String& json)
{
    auto parsed = juce::JSON::parse(json);
    if (parsed.isVoid()) return;
    
    bypassButton.setToggleState(parsed.getProperty("bypass", false), juce::dontSendNotification);
    
    int tabIndex = parsed.getProperty("currentTab", 0);
    showTab(static_cast<ProcessorTab>(tabIndex));
    
    if (truePeakPanel) truePeakPanel->loadFromJSON(parsed.getProperty("truePeakLimiter", juce::var()));
    if (transientPanel) transientPanel->loadFromJSON(parsed.getProperty("transientShaper", juce::var()));
    if (multibandPanel) multibandPanel->loadFromJSON(parsed.getProperty("multibandDynamics", juce::var()));
    if (spectralPanel) spectralPanel->loadFromJSON(parsed.getProperty("spectralProcessing", juce::var()));
    if (autoGainPanel) autoGainPanel->loadFromJSON(parsed.getProperty("autoGainStaging", juce::var()));
    if (referencePanel) referencePanel->loadFromJSON(parsed.getProperty("referenceMatching", juce::var()));
    if (spatialPanel) spatialPanel->loadFromJSON(parsed.getProperty("spatialAudio", juce::var()));
    if (stemPanel) stemPanel->loadFromJSON(parsed.getProperty("stemSeparation", juce::var()));
}

//==============================================================================
// TruePeakLimiterPanel
//==============================================================================

TruePeakLimiterPanel::TruePeakLimiterPanel()
{
    titleLabel.setFont(juce::Font(16.0f, juce::Font::bold));
    titleLabel.setColour(juce::Label::textColourId, juce::Colours::white);
    addAndMakeVisible(titleLabel);
    
    subtitleLabel.setFont(juce::Font(11.0f));
    subtitleLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(subtitleLabel);
    
    setupSlider(ceilingSlider, ceilingLabel, -12.0, 0.0, 0.1, " dB");
    ceilingSlider.setValue(-1.0);
    
    setupSlider(releaseSlider, releaseLabel, 10.0, 1000.0, 1.0, " ms");
    releaseSlider.setValue(100.0);
    releaseSlider.setSkewFactorFromMidPoint(150.0);
    
    setupSlider(lookaheadSlider, lookaheadLabel, 0.0, 10.0, 0.1, " ms");
    lookaheadSlider.setValue(1.5);
    
    oversampleLabel.setText("Oversample", juce::dontSendNotification);
    oversampleLabel.setFont(juce::Font(11.0f));
    oversampleLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(oversampleLabel);
    
    oversampleCombo.addItem("1x (Off)", 1);
    oversampleCombo.addItem("2x", 2);
    oversampleCombo.addItem("4x", 4);
    oversampleCombo.addItem("8x", 8);
    oversampleCombo.setSelectedId(4);
    oversampleCombo.setColour(juce::ComboBox::backgroundColourId, AppColours::inputBg);
    oversampleCombo.onChange = [this]() { if (onSettingsChanged) onSettingsChanged(); };
    addAndMakeVisible(oversampleCombo);
    
    enableISPDetection.setColour(juce::ToggleButton::textColourId, AppColours::textSecondary);
    enableISPDetection.setColour(juce::ToggleButton::tickColourId, AppColours::primary);
    enableISPDetection.setToggleState(true, juce::dontSendNotification);
    enableISPDetection.onClick = [this]() { if (onSettingsChanged) onSettingsChanged(); };
    addAndMakeVisible(enableISPDetection);
    
    enableAutoRelease.setColour(juce::ToggleButton::textColourId, AppColours::textSecondary);
    enableAutoRelease.setColour(juce::ToggleButton::tickColourId, AppColours::primary);
    enableAutoRelease.onClick = [this]() { if (onSettingsChanged) onSettingsChanged(); };
    addAndMakeVisible(enableAutoRelease);
    
    grLabel.setFont(juce::Font(24.0f, juce::Font::bold));
    grLabel.setColour(juce::Label::textColourId, AppColours::error);
    grLabel.setJustificationType(juce::Justification::centred);
    addAndMakeVisible(grLabel);
}

void TruePeakLimiterPanel::setupSlider(juce::Slider& slider, juce::Label& label,
                                        double min, double max, double step, const juce::String& suffix)
{
    label.setFont(juce::Font(11.0f));
    label.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(label);
    
    slider.setSliderStyle(juce::Slider::LinearHorizontal);
    slider.setTextBoxStyle(juce::Slider::TextBoxRight, false, 60, 20);
    slider.setRange(min, max, step);
    slider.setTextValueSuffix(suffix);
    slider.setColour(juce::Slider::trackColourId, AppColours::primary.withAlpha(0.6f));
    slider.setColour(juce::Slider::thumbColourId, AppColours::primaryLight);
    slider.setColour(juce::Slider::backgroundColourId, AppColours::surfaceAlt);
    slider.setColour(juce::Slider::textBoxTextColourId, AppColours::textPrimary);
    slider.setColour(juce::Slider::textBoxBackgroundColourId, AppColours::inputBg);
    slider.onValueChange = [this]() { if (onSettingsChanged) onSettingsChanged(); };
    addAndMakeVisible(slider);
}

void TruePeakLimiterPanel::paint(juce::Graphics& g)
{
    g.fillAll(AppColours::surface);
    
    // GR meter background
    auto grArea = getLocalBounds().removeFromRight(80).reduced(8);
    g.setColour(juce::Colours::black.withAlpha(0.3f));
    g.fillRoundedRectangle(grArea.toFloat(), 6.0f);
    
    // GR meter bar
    if (currentGR < 0.0f)
    {
        float grNormalized = juce::jlimit(0.0f, 1.0f, -currentGR / 20.0f);
        auto barHeight = static_cast<int>(grArea.getHeight() * grNormalized);
        auto barArea = grArea.removeFromBottom(barHeight);
        
        g.setColour(AppColours::error.withAlpha(0.7f));
        g.fillRoundedRectangle(barArea.reduced(4).toFloat(), 3.0f);
    }
}

void TruePeakLimiterPanel::resized()
{
    auto bounds = getLocalBounds().reduced(12);
    
    // Title area
    titleLabel.setBounds(bounds.removeFromTop(24));
    subtitleLabel.setBounds(bounds.removeFromTop(18));
    bounds.removeFromTop(16);
    
    // GR meter on right
    auto grMeterArea = bounds.removeFromRight(80);
    grLabel.setBounds(grMeterArea.removeFromTop(40));
    
    // Controls
    int rowHeight = 36;
    int labelWidth = 80;
    
    auto row1 = bounds.removeFromTop(rowHeight);
    ceilingLabel.setBounds(row1.removeFromLeft(labelWidth));
    ceilingSlider.setBounds(row1);
    
    bounds.removeFromTop(8);
    auto row2 = bounds.removeFromTop(rowHeight);
    releaseLabel.setBounds(row2.removeFromLeft(labelWidth));
    releaseSlider.setBounds(row2);
    
    bounds.removeFromTop(8);
    auto row3 = bounds.removeFromTop(rowHeight);
    lookaheadLabel.setBounds(row3.removeFromLeft(labelWidth));
    lookaheadSlider.setBounds(row3);
    
    bounds.removeFromTop(8);
    auto row4 = bounds.removeFromTop(rowHeight);
    oversampleLabel.setBounds(row4.removeFromLeft(labelWidth));
    oversampleCombo.setBounds(row4.removeFromLeft(120));
    
    bounds.removeFromTop(16);
    auto toggleRow = bounds.removeFromTop(28);
    enableISPDetection.setBounds(toggleRow.removeFromLeft(150));
    enableAutoRelease.setBounds(toggleRow.removeFromLeft(150));
}

juce::var TruePeakLimiterPanel::toJSON() const
{
    auto* obj = new juce::DynamicObject();
    obj->setProperty("ceiling", ceilingSlider.getValue());
    obj->setProperty("release", releaseSlider.getValue());
    obj->setProperty("lookahead", lookaheadSlider.getValue());
    obj->setProperty("oversample", oversampleCombo.getSelectedId());
    obj->setProperty("ispDetection", enableISPDetection.getToggleState());
    obj->setProperty("autoRelease", enableAutoRelease.getToggleState());
    return juce::var(obj);
}

void TruePeakLimiterPanel::loadFromJSON(const juce::var& json)
{
    if (json.isVoid()) return;
    
    ceilingSlider.setValue(json.getProperty("ceiling", -1.0));
    releaseSlider.setValue(json.getProperty("release", 100.0));
    lookaheadSlider.setValue(json.getProperty("lookahead", 1.5));
    oversampleCombo.setSelectedId((int)json.getProperty("oversample", 4));
    enableISPDetection.setToggleState(json.getProperty("ispDetection", true), juce::dontSendNotification);
    enableAutoRelease.setToggleState(json.getProperty("autoRelease", false), juce::dontSendNotification);
}

//==============================================================================
// TransientShaperPanel
//==============================================================================

TransientShaperPanel::TransientShaperPanel()
{
    titleLabel.setFont(juce::Font(16.0f, juce::Font::bold));
    titleLabel.setColour(juce::Label::textColourId, juce::Colours::white);
    addAndMakeVisible(titleLabel);
    
    subtitleLabel.setFont(juce::Font(11.0f));
    subtitleLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(subtitleLabel);
    
    setupSlider(attackSlider, attackLabel, -100.0, 100.0, 1.0, " %");
    attackSlider.setValue(0.0);
    
    setupSlider(sustainSlider, sustainLabel, -100.0, 100.0, 1.0, " %");
    sustainSlider.setValue(0.0);
    
    setupSlider(outputSlider, outputLabel, -12.0, 12.0, 0.1, " dB");
    outputSlider.setValue(0.0);
    
    enableMultiband.setColour(juce::ToggleButton::textColourId, AppColours::textSecondary);
    enableMultiband.setColour(juce::ToggleButton::tickColourId, AppColours::primary);
    enableMultiband.onClick = [this]() {
        bool mb = enableMultiband.getToggleState();
        lowCrossSlider.setEnabled(mb);
        highCrossSlider.setEnabled(mb);
        if (onSettingsChanged) onSettingsChanged();
    };
    addAndMakeVisible(enableMultiband);
    
    setupSlider(lowCrossSlider, lowCrossLabel, 50.0, 500.0, 1.0, " Hz");
    lowCrossSlider.setValue(200.0);
    lowCrossSlider.setEnabled(false);
    
    setupSlider(highCrossSlider, highCrossLabel, 2000.0, 8000.0, 1.0, " Hz");
    highCrossSlider.setValue(4000.0);
    highCrossSlider.setEnabled(false);
}

void TransientShaperPanel::setupSlider(juce::Slider& slider, juce::Label& label,
                                        double min, double max, double step, const juce::String& suffix)
{
    label.setFont(juce::Font(11.0f));
    label.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(label);
    
    slider.setSliderStyle(juce::Slider::LinearHorizontal);
    slider.setTextBoxStyle(juce::Slider::TextBoxRight, false, 60, 20);
    slider.setRange(min, max, step);
    slider.setTextValueSuffix(suffix);
    slider.setColour(juce::Slider::trackColourId, AppColours::primary.withAlpha(0.6f));
    slider.setColour(juce::Slider::thumbColourId, AppColours::primaryLight);
    slider.setColour(juce::Slider::backgroundColourId, AppColours::surfaceAlt);
    slider.setColour(juce::Slider::textBoxTextColourId, AppColours::textPrimary);
    slider.setColour(juce::Slider::textBoxBackgroundColourId, AppColours::inputBg);
    slider.onValueChange = [this]() { if (onSettingsChanged) onSettingsChanged(); };
    addAndMakeVisible(slider);
}

void TransientShaperPanel::paint(juce::Graphics& g)
{
    g.fillAll(AppColours::surface);
}

void TransientShaperPanel::resized()
{
    auto bounds = getLocalBounds().reduced(12);
    
    titleLabel.setBounds(bounds.removeFromTop(24));
    subtitleLabel.setBounds(bounds.removeFromTop(18));
    bounds.removeFromTop(16);
    
    int rowHeight = 36;
    int labelWidth = 80;
    
    auto row1 = bounds.removeFromTop(rowHeight);
    attackLabel.setBounds(row1.removeFromLeft(labelWidth));
    attackSlider.setBounds(row1);
    
    bounds.removeFromTop(8);
    auto row2 = bounds.removeFromTop(rowHeight);
    sustainLabel.setBounds(row2.removeFromLeft(labelWidth));
    sustainSlider.setBounds(row2);
    
    bounds.removeFromTop(8);
    auto row3 = bounds.removeFromTop(rowHeight);
    outputLabel.setBounds(row3.removeFromLeft(labelWidth));
    outputSlider.setBounds(row3);
    
    bounds.removeFromTop(16);
    enableMultiband.setBounds(bounds.removeFromTop(28).removeFromLeft(200));
    
    bounds.removeFromTop(8);
    auto row4 = bounds.removeFromTop(rowHeight);
    lowCrossLabel.setBounds(row4.removeFromLeft(labelWidth));
    lowCrossSlider.setBounds(row4);
    
    bounds.removeFromTop(8);
    auto row5 = bounds.removeFromTop(rowHeight);
    highCrossLabel.setBounds(row5.removeFromLeft(labelWidth));
    highCrossSlider.setBounds(row5);
}

juce::var TransientShaperPanel::toJSON() const
{
    auto* obj = new juce::DynamicObject();
    obj->setProperty("attack", attackSlider.getValue());
    obj->setProperty("sustain", sustainSlider.getValue());
    obj->setProperty("output", outputSlider.getValue());
    obj->setProperty("multiband", enableMultiband.getToggleState());
    obj->setProperty("lowCross", lowCrossSlider.getValue());
    obj->setProperty("highCross", highCrossSlider.getValue());
    return juce::var(obj);
}

void TransientShaperPanel::loadFromJSON(const juce::var& json)
{
    if (json.isVoid()) return;
    
    attackSlider.setValue(json.getProperty("attack", 0.0));
    sustainSlider.setValue(json.getProperty("sustain", 0.0));
    outputSlider.setValue(json.getProperty("output", 0.0));
    enableMultiband.setToggleState(json.getProperty("multiband", false), juce::dontSendNotification);
    lowCrossSlider.setValue(json.getProperty("lowCross", 200.0));
    highCrossSlider.setValue(json.getProperty("highCross", 4000.0));
    
    bool mb = enableMultiband.getToggleState();
    lowCrossSlider.setEnabled(mb);
    highCrossSlider.setEnabled(mb);
}

//==============================================================================
// MultibandDynamicsPanel
//==============================================================================

MultibandDynamicsPanel::MultibandDynamicsPanel()
{
    titleLabel.setFont(juce::Font(16.0f, juce::Font::bold));
    titleLabel.setColour(juce::Label::textColourId, juce::Colours::white);
    addAndMakeVisible(titleLabel);
    
    subtitleLabel.setFont(juce::Font(11.0f));
    subtitleLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(subtitleLabel);
    
    crossLabel.setFont(juce::Font(12.0f, juce::Font::bold));
    crossLabel.setColour(juce::Label::textColourId, AppColours::textPrimary);
    addAndMakeVisible(crossLabel);
    
    // Crossover sliders
    auto setupCrossSlider = [this](juce::Slider& slider, double min, double max, double def) {
        slider.setSliderStyle(juce::Slider::LinearHorizontal);
        slider.setTextBoxStyle(juce::Slider::TextBoxRight, false, 55, 18);
        slider.setRange(min, max, 1.0);
        slider.setValue(def);
        slider.setTextValueSuffix(" Hz");
        slider.setSkewFactorFromMidPoint(std::sqrt(min * max));
        slider.setColour(juce::Slider::trackColourId, AppColours::primary.withAlpha(0.6f));
        slider.setColour(juce::Slider::thumbColourId, AppColours::primaryLight);
        slider.onValueChange = [this]() { if (onSettingsChanged) onSettingsChanged(); };
        addAndMakeVisible(slider);
    };
    
    setupCrossSlider(lowMidSlider, 50, 500, 200);
    setupCrossSlider(midHighSlider, 500, 4000, 2000);
    setupCrossSlider(highSlider, 4000, 16000, 8000);
    
    processingModeCombo.addItem("Compress", 1);
    processingModeCombo.addItem("Expand", 2);
    processingModeCombo.addItem("Gate", 3);
    processingModeCombo.addItem("Saturate", 4);
    processingModeCombo.setSelectedId(1);
    processingModeCombo.setColour(juce::ComboBox::backgroundColourId, AppColours::inputBg);
    processingModeCombo.onChange = [this]() { if (onSettingsChanged) onSettingsChanged(); };
    addAndMakeVisible(processingModeCombo);
    
    setupBandControls();
}

void MultibandDynamicsPanel::setupBandControls()
{
    const juce::String bandNames[] = { "Low", "Low-Mid", "High-Mid", "High" };
    const juce::Colour bandColours[] = { 
        juce::Colour(255, 100, 100),  // Red
        juce::Colour(255, 200, 100),  // Orange
        juce::Colour(100, 200, 255),  // Cyan
        juce::Colour(200, 150, 255)   // Purple
    };
    
    for (int i = 0; i < 4; ++i)
    {
        auto& band = bands[i];
        
        band.nameLabel.setText(bandNames[i], juce::dontSendNotification);
        band.nameLabel.setFont(juce::Font(11.0f, juce::Font::bold));
        band.nameLabel.setColour(juce::Label::textColourId, bandColours[i]);
        addAndMakeVisible(band.nameLabel);
        
        band.thresholdSlider.setSliderStyle(juce::Slider::LinearVertical);
        band.thresholdSlider.setTextBoxStyle(juce::Slider::TextBoxBelow, false, 50, 16);
        band.thresholdSlider.setRange(-60.0, 0.0, 0.5);
        band.thresholdSlider.setValue(-20.0);
        band.thresholdSlider.setTextValueSuffix(" dB");
        band.thresholdSlider.setColour(juce::Slider::trackColourId, bandColours[i].withAlpha(0.6f));
        band.thresholdSlider.onValueChange = [this]() { if (onSettingsChanged) onSettingsChanged(); };
        addAndMakeVisible(band.thresholdSlider);
        
        band.ratioSlider.setSliderStyle(juce::Slider::RotaryHorizontalVerticalDrag);
        band.ratioSlider.setTextBoxStyle(juce::Slider::TextBoxBelow, false, 40, 14);
        band.ratioSlider.setRange(1.0, 20.0, 0.1);
        band.ratioSlider.setValue(4.0);
        band.ratioSlider.setColour(juce::Slider::rotarySliderFillColourId, bandColours[i]);
        band.ratioSlider.onValueChange = [this]() { if (onSettingsChanged) onSettingsChanged(); };
        addAndMakeVisible(band.ratioSlider);
        
        band.gainSlider.setSliderStyle(juce::Slider::LinearVertical);
        band.gainSlider.setTextBoxStyle(juce::Slider::TextBoxBelow, false, 50, 16);
        band.gainSlider.setRange(-12.0, 12.0, 0.1);
        band.gainSlider.setValue(0.0);
        band.gainSlider.setTextValueSuffix(" dB");
        band.gainSlider.setColour(juce::Slider::trackColourId, bandColours[i].withAlpha(0.6f));
        band.gainSlider.onValueChange = [this]() { if (onSettingsChanged) onSettingsChanged(); };
        addAndMakeVisible(band.gainSlider);
        
        band.soloButton.setButtonText("S");
        band.soloButton.setColour(juce::ToggleButton::textColourId, AppColours::textSecondary);
        band.soloButton.setColour(juce::ToggleButton::tickColourId, AppColours::warning);
        addAndMakeVisible(band.soloButton);
        
        band.bypassButton.setButtonText("B");
        band.bypassButton.setColour(juce::ToggleButton::textColourId, AppColours::textSecondary);
        addAndMakeVisible(band.bypassButton);
    }
}

void MultibandDynamicsPanel::paint(juce::Graphics& g)
{
    g.fillAll(AppColours::surface);
    
    // Draw band separators
    auto bandArea = getLocalBounds().withTrimmedTop(120).withTrimmedBottom(10).reduced(12, 0);
    int bandWidth = bandArea.getWidth() / 4;
    
    g.setColour(AppColours::border.withAlpha(0.3f));
    for (int i = 1; i < 4; ++i)
    {
        int x = bandArea.getX() + i * bandWidth;
        g.drawVerticalLine(x, (float)bandArea.getY(), (float)bandArea.getBottom());
    }
}

void MultibandDynamicsPanel::resized()
{
    auto bounds = getLocalBounds().reduced(12);
    
    titleLabel.setBounds(bounds.removeFromTop(24));
    subtitleLabel.setBounds(bounds.removeFromTop(18));
    bounds.removeFromTop(12);
    
    // Crossover section
    auto crossSection = bounds.removeFromTop(50);
    crossLabel.setBounds(crossSection.removeFromTop(18));
    
    auto crossSliders = crossSection;
    int sliderWidth = (crossSliders.getWidth() - 100) / 3;
    lowMidSlider.setBounds(crossSliders.removeFromLeft(sliderWidth));
    crossSliders.removeFromLeft(10);
    midHighSlider.setBounds(crossSliders.removeFromLeft(sliderWidth));
    crossSliders.removeFromLeft(10);
    highSlider.setBounds(crossSliders.removeFromLeft(sliderWidth));
    processingModeCombo.setBounds(crossSliders.reduced(5, 4));
    
    bounds.removeFromTop(12);
    
    // Band controls
    auto bandArea = bounds;
    int bandWidth = bandArea.getWidth() / 4;
    
    for (int i = 0; i < 4; ++i)
    {
        auto& band = bands[i];
        auto bandBounds = bandArea.removeFromLeft(bandWidth).reduced(4, 0);
        
        band.nameLabel.setBounds(bandBounds.removeFromTop(20));
        
        auto sliderArea = bandBounds;
        int sliderCol = sliderArea.getWidth() / 3;
        
        band.thresholdSlider.setBounds(sliderArea.removeFromLeft(sliderCol));
        band.ratioSlider.setBounds(sliderArea.removeFromLeft(sliderCol).reduced(5));
        band.gainSlider.setBounds(sliderArea.removeFromLeft(sliderCol));
        
        // Solo/Bypass at bottom (would need adjustment)
    }
}

juce::var MultibandDynamicsPanel::toJSON() const
{
    auto* obj = new juce::DynamicObject();
    obj->setProperty("lowMidCross", lowMidSlider.getValue());
    obj->setProperty("midHighCross", midHighSlider.getValue());
    obj->setProperty("highCross", highSlider.getValue());
    obj->setProperty("mode", processingModeCombo.getSelectedId());
    
    juce::Array<juce::var> bandsArr;
    for (int i = 0; i < 4; ++i)
    {
        auto* bandObj = new juce::DynamicObject();
        bandObj->setProperty("threshold", bands[i].thresholdSlider.getValue());
        bandObj->setProperty("ratio", bands[i].ratioSlider.getValue());
        bandObj->setProperty("gain", bands[i].gainSlider.getValue());
        bandObj->setProperty("solo", bands[i].soloButton.getToggleState());
        bandObj->setProperty("bypass", bands[i].bypassButton.getToggleState());
        bandsArr.add(juce::var(bandObj));
    }
    obj->setProperty("bands", bandsArr);
    
    return juce::var(obj);
}

void MultibandDynamicsPanel::loadFromJSON(const juce::var& json)
{
    if (json.isVoid()) return;
    
    lowMidSlider.setValue(json.getProperty("lowMidCross", 200.0));
    midHighSlider.setValue(json.getProperty("midHighCross", 2000.0));
    highSlider.setValue(json.getProperty("highCross", 8000.0));
    processingModeCombo.setSelectedId((int)json.getProperty("mode", 1));
    
    if (auto* bandsArr = json.getProperty("bands", juce::var()).getArray())
    {
        for (int i = 0; i < juce::jmin(4, bandsArr->size()); ++i)
        {
            const auto& bandJson = (*bandsArr)[i];
            bands[i].thresholdSlider.setValue(bandJson.getProperty("threshold", -20.0));
            bands[i].ratioSlider.setValue(bandJson.getProperty("ratio", 4.0));
            bands[i].gainSlider.setValue(bandJson.getProperty("gain", 0.0));
            bands[i].soloButton.setToggleState(bandJson.getProperty("solo", false), juce::dontSendNotification);
            bands[i].bypassButton.setToggleState(bandJson.getProperty("bypass", false), juce::dontSendNotification);
        }
    }
}

//==============================================================================
// SpectralProcessorPanel - Simplified implementation
//==============================================================================

SpectralProcessorPanel::SpectralProcessorPanel()
{
    titleLabel.setFont(juce::Font(16.0f, juce::Font::bold));
    titleLabel.setColour(juce::Label::textColourId, juce::Colours::white);
    addAndMakeVisible(titleLabel);
    
    // Sub-tabs
    auto setupSubTab = [this](juce::TextButton& btn, int index) {
        btn.setColour(juce::TextButton::buttonColourId, AppColours::surfaceAlt);
        btn.onClick = [this, index]() { showSubTab(index); };
        addAndMakeVisible(btn);
    };
    
    setupSubTab(dynEqTab, 0);
    setupSubTab(deesserTab, 1);
    setupSubTab(exciterTab, 2);
    
    // All control labels and sliders would be set up here
    // For brevity, showing structure only
    
    dynEqLabel.setFont(juce::Font(11.0f));
    dynEqLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(dynEqLabel);
    
    deesserLabel.setFont(juce::Font(11.0f));
    deesserLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addChildComponent(deesserLabel);
    
    exciterLabel.setFont(juce::Font(11.0f));
    exciterLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addChildComponent(exciterLabel);
    
    showSubTab(0);
}

void SpectralProcessorPanel::showSubTab(int index)
{
    currentSubTab = index;
    
    dynEqTab.setColour(juce::TextButton::buttonColourId, index == 0 ? AppColours::primary : AppColours::surfaceAlt);
    deesserTab.setColour(juce::TextButton::buttonColourId, index == 1 ? AppColours::primary : AppColours::surfaceAlt);
    exciterTab.setColour(juce::TextButton::buttonColourId, index == 2 ? AppColours::primary : AppColours::surfaceAlt);
    
    dynEqLabel.setVisible(index == 0);
    deesserLabel.setVisible(index == 1);
    exciterLabel.setVisible(index == 2);
    
    repaint();
}

void SpectralProcessorPanel::paint(juce::Graphics& g)
{
    g.fillAll(AppColours::surface);
}

void SpectralProcessorPanel::resized()
{
    auto bounds = getLocalBounds().reduced(12);
    
    titleLabel.setBounds(bounds.removeFromTop(24));
    bounds.removeFromTop(8);
    
    // Sub-tabs
    auto tabRow = bounds.removeFromTop(28);
    int tabWidth = 90;
    dynEqTab.setBounds(tabRow.removeFromLeft(tabWidth).reduced(2, 0));
    deesserTab.setBounds(tabRow.removeFromLeft(tabWidth).reduced(2, 0));
    exciterTab.setBounds(tabRow.removeFromLeft(tabWidth).reduced(2, 0));
    
    bounds.removeFromTop(12);
    
    // Content area
    dynEqLabel.setBounds(bounds.removeFromTop(20));
    deesserLabel.setBounds(bounds.removeFromTop(20));
    exciterLabel.setBounds(bounds.removeFromTop(20));
}

juce::var SpectralProcessorPanel::toJSON() const
{
    auto* obj = new juce::DynamicObject();
    obj->setProperty("currentSubTab", currentSubTab);
    // Add all slider values here
    return juce::var(obj);
}

void SpectralProcessorPanel::loadFromJSON(const juce::var& json)
{
    if (json.isVoid()) return;
    showSubTab((int)json.getProperty("currentSubTab", 0));
}

//==============================================================================
// AutoGainStagingPanel
//==============================================================================

AutoGainStagingPanel::AutoGainStagingPanel()
{
    titleLabel.setFont(juce::Font(16.0f, juce::Font::bold));
    titleLabel.setColour(juce::Label::textColourId, juce::Colours::white);
    addAndMakeVisible(titleLabel);
    
    subtitleLabel.setFont(juce::Font(11.0f));
    subtitleLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(subtitleLabel);
    
    targetLufsLabel.setFont(juce::Font(11.0f));
    targetLufsLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(targetLufsLabel);
    
    targetLufsSlider.setSliderStyle(juce::Slider::LinearHorizontal);
    targetLufsSlider.setTextBoxStyle(juce::Slider::TextBoxRight, false, 60, 20);
    targetLufsSlider.setRange(-24.0, -6.0, 0.5);
    targetLufsSlider.setValue(-14.0);
    targetLufsSlider.setTextValueSuffix(" LUFS");
    targetLufsSlider.setColour(juce::Slider::trackColourId, AppColours::primary.withAlpha(0.6f));
    targetLufsSlider.setColour(juce::Slider::thumbColourId, AppColours::primaryLight);
    targetLufsSlider.onValueChange = [this]() { if (onSettingsChanged) onSettingsChanged(); };
    addAndMakeVisible(targetLufsSlider);
    
    headroomLabel.setFont(juce::Font(11.0f));
    headroomLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(headroomLabel);
    
    headroomSlider.setSliderStyle(juce::Slider::LinearHorizontal);
    headroomSlider.setTextBoxStyle(juce::Slider::TextBoxRight, false, 60, 20);
    headroomSlider.setRange(0.5, 6.0, 0.5);
    headroomSlider.setValue(1.0);
    headroomSlider.setTextValueSuffix(" dB");
    headroomSlider.setColour(juce::Slider::trackColourId, AppColours::primary.withAlpha(0.6f));
    headroomSlider.setColour(juce::Slider::thumbColourId, AppColours::primaryLight);
    headroomSlider.onValueChange = [this]() { if (onSettingsChanged) onSettingsChanged(); };
    addAndMakeVisible(headroomSlider);
    
    genreLabel.setFont(juce::Font(11.0f));
    genreLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(genreLabel);
    
    populateGenreCombo();
    genreCombo.setColour(juce::ComboBox::backgroundColourId, AppColours::inputBg);
    genreCombo.onChange = [this]() {
        // Auto-set target LUFS based on genre
        int genreId = genreCombo.getSelectedId();
        switch (genreId)
        {
            case 1: targetLufsSlider.setValue(-14.0); break;  // Pop/Streaming
            case 2: targetLufsSlider.setValue(-9.0); break;   // Hip-Hop
            case 3: targetLufsSlider.setValue(-8.0); break;   // EDM
            case 4: targetLufsSlider.setValue(-18.0); break;  // Classical
            case 5: targetLufsSlider.setValue(-12.0); break;  // Rock
            case 6: targetLufsSlider.setValue(-14.0); break;  // Jazz
            case 7: targetLufsSlider.setValue(-24.0); break;  // Broadcast
            case 8: targetLufsSlider.setValue(-16.0); break;  // Podcast
            default: break;
        }
        if (onSettingsChanged) onSettingsChanged();
    };
    addAndMakeVisible(genreCombo);
    
    analyzeButton.setColour(juce::TextButton::buttonColourId, AppColours::primary);
    analyzeButton.onClick = [this]() {
        // Trigger analysis
        currentLufsValue.setText("Analyzing...", juce::dontSendNotification);
    };
    addAndMakeVisible(analyzeButton);
    
    applyButton.setColour(juce::TextButton::buttonColourId, AppColours::success);
    applyButton.onClick = [this]() {
        if (onSettingsChanged) onSettingsChanged();
    };
    addAndMakeVisible(applyButton);
    
    // Results labels
    currentLufsLabel.setFont(juce::Font(11.0f));
    currentLufsLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(currentLufsLabel);
    
    currentLufsValue.setFont(juce::Font(14.0f, juce::Font::bold));
    currentLufsValue.setColour(juce::Label::textColourId, AppColours::primary);
    addAndMakeVisible(currentLufsValue);
    
    suggestedGainLabel.setFont(juce::Font(11.0f));
    suggestedGainLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(suggestedGainLabel);
    
    suggestedGainValue.setFont(juce::Font(14.0f, juce::Font::bold));
    suggestedGainValue.setColour(juce::Label::textColourId, AppColours::success);
    addAndMakeVisible(suggestedGainValue);
}

void AutoGainStagingPanel::populateGenreCombo()
{
    genreCombo.addItem("Pop / Streaming (-14 LUFS)", 1);
    genreCombo.addItem("Hip-Hop (-9 LUFS)", 2);
    genreCombo.addItem("EDM (-8 LUFS)", 3);
    genreCombo.addItem("Classical (-18 LUFS)", 4);
    genreCombo.addItem("Rock (-12 LUFS)", 5);
    genreCombo.addItem("Jazz (-14 LUFS)", 6);
    genreCombo.addItem("Broadcast (-24 LUFS)", 7);
    genreCombo.addItem("Podcast (-16 LUFS)", 8);
    genreCombo.setSelectedId(1);
}

void AutoGainStagingPanel::paint(juce::Graphics& g)
{
    g.fillAll(AppColours::surface);
    
    // Results panel background
    auto bounds = getLocalBounds().reduced(12);
    auto resultsArea = bounds.withTrimmedTop(180).removeFromTop(80);
    g.setColour(juce::Colours::black.withAlpha(0.2f));
    g.fillRoundedRectangle(resultsArea.toFloat(), 6.0f);
}

void AutoGainStagingPanel::resized()
{
    auto bounds = getLocalBounds().reduced(12);
    
    titleLabel.setBounds(bounds.removeFromTop(24));
    subtitleLabel.setBounds(bounds.removeFromTop(18));
    bounds.removeFromTop(16);
    
    int rowHeight = 36;
    int labelWidth = 100;
    
    auto row1 = bounds.removeFromTop(rowHeight);
    targetLufsLabel.setBounds(row1.removeFromLeft(labelWidth));
    targetLufsSlider.setBounds(row1);
    
    bounds.removeFromTop(8);
    auto row2 = bounds.removeFromTop(rowHeight);
    headroomLabel.setBounds(row2.removeFromLeft(labelWidth));
    headroomSlider.setBounds(row2);
    
    bounds.removeFromTop(8);
    auto row3 = bounds.removeFromTop(rowHeight);
    genreLabel.setBounds(row3.removeFromLeft(labelWidth));
    genreCombo.setBounds(row3.removeFromLeft(200));
    
    bounds.removeFromTop(16);
    
    // Results section
    auto resultsArea = bounds.removeFromTop(80).reduced(8);
    auto leftResults = resultsArea.removeFromLeft(resultsArea.getWidth() / 2);
    
    currentLufsLabel.setBounds(leftResults.removeFromTop(18));
    currentLufsValue.setBounds(leftResults.removeFromTop(24));
    
    suggestedGainLabel.setBounds(resultsArea.removeFromTop(18));
    suggestedGainValue.setBounds(resultsArea.removeFromTop(24));
    
    bounds.removeFromTop(16);
    
    // Buttons
    auto buttonRow = bounds.removeFromTop(32);
    analyzeButton.setBounds(buttonRow.removeFromLeft(100));
    buttonRow.removeFromLeft(8);
    applyButton.setBounds(buttonRow.removeFromLeft(100));
}

juce::var AutoGainStagingPanel::toJSON() const
{
    auto* obj = new juce::DynamicObject();
    obj->setProperty("targetLufs", targetLufsSlider.getValue());
    obj->setProperty("headroom", headroomSlider.getValue());
    obj->setProperty("genre", genreCombo.getSelectedId());
    return juce::var(obj);
}

void AutoGainStagingPanel::loadFromJSON(const juce::var& json)
{
    if (json.isVoid()) return;
    
    targetLufsSlider.setValue(json.getProperty("targetLufs", -14.0));
    headroomSlider.setValue(json.getProperty("headroom", 1.0));
    genreCombo.setSelectedId((int)json.getProperty("genre", 1));
}

//==============================================================================
// ReferenceMatchingPanel
//==============================================================================

ReferenceMatchingPanel::ReferenceMatchingPanel()
{
    titleLabel.setFont(juce::Font(16.0f, juce::Font::bold));
    titleLabel.setColour(juce::Label::textColourId, juce::Colours::white);
    addAndMakeVisible(titleLabel);
    
    subtitleLabel.setFont(juce::Font(11.0f));
    subtitleLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(subtitleLabel);
    
    loadRefButton.setColour(juce::TextButton::buttonColourId, AppColours::primary);
    loadRefButton.onClick = [this]() {
        auto chooser = std::make_shared<juce::FileChooser>(
            "Select Reference Track",
            juce::File::getSpecialLocation(juce::File::userMusicDirectory),
            "*.wav;*.mp3;*.flac;*.aiff"
        );
        
        chooser->launchAsync(juce::FileBrowserComponent::openMode, [this, chooser](const juce::FileChooser& fc) {
            auto file = fc.getResult();
            if (file.existsAsFile())
            {
                loadedReference = file;
                refFileLabel.setText(file.getFileName(), juce::dontSendNotification);
                referenceAnalyzed = false;
            }
        });
    };
    addAndMakeVisible(loadRefButton);
    
    refFileLabel.setFont(juce::Font(11.0f));
    refFileLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    refFileLabel.setJustificationType(juce::Justification::centred);
    addAndMakeVisible(refFileLabel);
    
    matchAmountLabel.setFont(juce::Font(11.0f));
    matchAmountLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(matchAmountLabel);
    
    matchAmountSlider.setSliderStyle(juce::Slider::LinearHorizontal);
    matchAmountSlider.setTextBoxStyle(juce::Slider::TextBoxRight, false, 50, 20);
    matchAmountSlider.setRange(0.0, 100.0, 1.0);
    matchAmountSlider.setValue(100.0);
    matchAmountSlider.setTextValueSuffix(" %");
    matchAmountSlider.setColour(juce::Slider::trackColourId, AppColours::primary.withAlpha(0.6f));
    matchAmountSlider.onValueChange = [this]() { if (onSettingsChanged) onSettingsChanged(); };
    addAndMakeVisible(matchAmountSlider);
    
    matchEQButton.setToggleState(true, juce::dontSendNotification);
    matchEQButton.setColour(juce::ToggleButton::textColourId, AppColours::textSecondary);
    matchEQButton.setColour(juce::ToggleButton::tickColourId, AppColours::primary);
    matchEQButton.onClick = [this]() { if (onSettingsChanged) onSettingsChanged(); };
    addAndMakeVisible(matchEQButton);
    
    matchLoudnessButton.setToggleState(true, juce::dontSendNotification);
    matchLoudnessButton.setColour(juce::ToggleButton::textColourId, AppColours::textSecondary);
    matchLoudnessButton.setColour(juce::ToggleButton::tickColourId, AppColours::primary);
    matchLoudnessButton.onClick = [this]() { if (onSettingsChanged) onSettingsChanged(); };
    addAndMakeVisible(matchLoudnessButton);
    
    matchDynamicsButton.setColour(juce::ToggleButton::textColourId, AppColours::textSecondary);
    matchDynamicsButton.setColour(juce::ToggleButton::tickColourId, AppColours::primary);
    matchDynamicsButton.onClick = [this]() { if (onSettingsChanged) onSettingsChanged(); };
    addAndMakeVisible(matchDynamicsButton);
    
    matchStereoButton.setColour(juce::ToggleButton::textColourId, AppColours::textSecondary);
    matchStereoButton.setColour(juce::ToggleButton::tickColourId, AppColours::primary);
    matchStereoButton.onClick = [this]() { if (onSettingsChanged) onSettingsChanged(); };
    addAndMakeVisible(matchStereoButton);
    
    analyzeButton.setColour(juce::TextButton::buttonColourId, AppColours::primary);
    analyzeButton.onClick = [this]() {
        if (loadedReference.existsAsFile() && onAnalyzeReference)
            onAnalyzeReference(loadedReference);
    };
    addAndMakeVisible(analyzeButton);
    
    applyButton.setColour(juce::TextButton::buttonColourId, AppColours::success);
    applyButton.onClick = [this]() { if (onSettingsChanged) onSettingsChanged(); };
    addAndMakeVisible(applyButton);
}

bool ReferenceMatchingPanel::isInterestedInFileDrag(const juce::StringArray& files)
{
    return files.size() == 1 && 
           (files[0].endsWithIgnoreCase(".wav") || 
            files[0].endsWithIgnoreCase(".mp3") ||
            files[0].endsWithIgnoreCase(".flac") ||
            files[0].endsWithIgnoreCase(".aiff"));
}

void ReferenceMatchingPanel::filesDropped(const juce::StringArray& files, int /*x*/, int /*y*/)
{
    if (files.size() == 1)
    {
        loadedReference = juce::File(files[0]);
        refFileLabel.setText(loadedReference.getFileName(), juce::dontSendNotification);
        referenceAnalyzed = false;
    }
}

void ReferenceMatchingPanel::paint(juce::Graphics& g)
{
    g.fillAll(AppColours::surface);
    
    // Drop zone
    auto dropArea = refFileLabel.getBounds().expanded(4);
    
    g.setColour(AppColours::border);
    g.drawRoundedRectangle(dropArea.toFloat(), 4.0f, 1.0f);
    
    if (isMouseOverOrDragging())
    {
        g.setColour(AppColours::primary.withAlpha(0.2f));
        g.fillRoundedRectangle(dropArea.toFloat(), 4.0f);
    }
    
    // Spectrum visualization area (placeholder)
    spectrumArea = getLocalBounds().withTrimmedTop(200).reduced(12).removeFromTop(100);
    g.setColour(juce::Colours::black.withAlpha(0.3f));
    g.fillRoundedRectangle(spectrumArea.toFloat(), 4.0f);
    
    if (!referenceAnalyzed)
    {
        g.setColour(AppColours::textSecondary);
        g.setFont(12.0f);
        g.drawText("Spectrum comparison will appear here", spectrumArea, juce::Justification::centred);
    }
}

void ReferenceMatchingPanel::resized()
{
    auto bounds = getLocalBounds().reduced(12);
    
    titleLabel.setBounds(bounds.removeFromTop(24));
    subtitleLabel.setBounds(bounds.removeFromTop(18));
    bounds.removeFromTop(12);
    
    // Load section
    auto loadRow = bounds.removeFromTop(28);
    loadRefButton.setBounds(loadRow.removeFromLeft(120));
    loadRow.removeFromLeft(8);
    refFileLabel.setBounds(loadRow);
    
    bounds.removeFromTop(16);
    
    // Match amount
    auto matchRow = bounds.removeFromTop(28);
    matchAmountLabel.setBounds(matchRow.removeFromLeft(100));
    matchAmountSlider.setBounds(matchRow);
    
    bounds.removeFromTop(12);
    
    // Match options (2x2 grid)
    auto optionsRow1 = bounds.removeFromTop(24);
    matchEQButton.setBounds(optionsRow1.removeFromLeft(150));
    matchLoudnessButton.setBounds(optionsRow1.removeFromLeft(150));
    
    auto optionsRow2 = bounds.removeFromTop(24);
    matchDynamicsButton.setBounds(optionsRow2.removeFromLeft(150));
    matchStereoButton.setBounds(optionsRow2.removeFromLeft(150));
    
    bounds.removeFromTop(12);
    
    // Spectrum area is drawn in paint()
    bounds.removeFromTop(110);
    
    // Buttons
    auto buttonRow = bounds.removeFromTop(32);
    analyzeButton.setBounds(buttonRow.removeFromLeft(100));
    buttonRow.removeFromLeft(8);
    applyButton.setBounds(buttonRow.removeFromLeft(100));
}

juce::var ReferenceMatchingPanel::toJSON() const
{
    auto* obj = new juce::DynamicObject();
    obj->setProperty("referencePath", loadedReference.getFullPathName());
    obj->setProperty("matchAmount", matchAmountSlider.getValue());
    obj->setProperty("matchEQ", matchEQButton.getToggleState());
    obj->setProperty("matchLoudness", matchLoudnessButton.getToggleState());
    obj->setProperty("matchDynamics", matchDynamicsButton.getToggleState());
    obj->setProperty("matchStereo", matchStereoButton.getToggleState());
    return juce::var(obj);
}

void ReferenceMatchingPanel::loadFromJSON(const juce::var& json)
{
    if (json.isVoid()) return;
    
    juce::String refPath = json.getProperty("referencePath", "").toString();
    if (refPath.isNotEmpty())
    {
        loadedReference = juce::File(refPath);
        if (loadedReference.existsAsFile())
            refFileLabel.setText(loadedReference.getFileName(), juce::dontSendNotification);
    }
    
    matchAmountSlider.setValue(json.getProperty("matchAmount", 100.0));
    matchEQButton.setToggleState(json.getProperty("matchEQ", true), juce::dontSendNotification);
    matchLoudnessButton.setToggleState(json.getProperty("matchLoudness", true), juce::dontSendNotification);
    matchDynamicsButton.setToggleState(json.getProperty("matchDynamics", false), juce::dontSendNotification);
    matchStereoButton.setToggleState(json.getProperty("matchStereo", false), juce::dontSendNotification);
}

//==============================================================================
// SpatialAudioPanel
//==============================================================================

SpatialAudioPanel::SpatialAudioPanel()
{
    titleLabel.setFont(juce::Font(16.0f, juce::Font::bold));
    titleLabel.setColour(juce::Label::textColourId, juce::Colours::white);
    addAndMakeVisible(titleLabel);
    
    subtitleLabel.setFont(juce::Font(11.0f));
    subtitleLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(subtitleLabel);
    
    modeLabel.setFont(juce::Font(11.0f));
    modeLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(modeLabel);
    
    setupModeCombo();
    modeCombo.setColour(juce::ComboBox::backgroundColourId, AppColours::inputBg);
    modeCombo.onChange = [this]() {
        showModeControls(modeCombo.getSelectedId());
        if (onSettingsChanged) onSettingsChanged();
    };
    addAndMakeVisible(modeCombo);
    
    // Binaural controls
    binauralLabel.setFont(juce::Font(12.0f, juce::Font::bold));
    binauralLabel.setColour(juce::Label::textColourId, AppColours::textPrimary);
    addAndMakeVisible(binauralLabel);
    
    hrirCombo.addItem("KEMAR (MIT)", 1);
    hrirCombo.addItem("CIPIC (UC Davis)", 2);
    hrirCombo.addItem("ARI (Austrian)", 3);
    hrirCombo.addItem("LISTEN (IRCAM)", 4);
    hrirCombo.setSelectedId(1);
    hrirCombo.setColour(juce::ComboBox::backgroundColourId, AppColours::inputBg);
    addAndMakeVisible(hrirCombo);
    
    // Export button
    exportAtmosButton.setColour(juce::TextButton::buttonColourId, AppColours::success);
    exportAtmosButton.onClick = [this]() {
        if (onSettingsChanged) onSettingsChanged();
    };
    addAndMakeVisible(exportAtmosButton);
    
    showModeControls(1);
}

void SpatialAudioPanel::setupModeCombo()
{
    modeCombo.addItem("Binaural (Headphones)", 1);
    modeCombo.addItem("Stereo to 7.1.4 Upmix", 2);
    modeCombo.addItem("Ambisonics Encode", 3);
    modeCombo.setSelectedId(1);
}

void SpatialAudioPanel::showModeControls(int modeIndex)
{
    binauralLabel.setVisible(modeIndex == 1);
    hrirCombo.setVisible(modeIndex == 1);
    
    // Additional controls would be shown/hidden here
}

void SpatialAudioPanel::paint(juce::Graphics& g)
{
    g.fillAll(AppColours::surface);
}

void SpatialAudioPanel::resized()
{
    auto bounds = getLocalBounds().reduced(12);
    
    titleLabel.setBounds(bounds.removeFromTop(24));
    subtitleLabel.setBounds(bounds.removeFromTop(18));
    bounds.removeFromTop(16);
    
    auto modeRow = bounds.removeFromTop(28);
    modeLabel.setBounds(modeRow.removeFromLeft(80));
    modeCombo.setBounds(modeRow.removeFromLeft(200));
    
    bounds.removeFromTop(16);
    
    binauralLabel.setBounds(bounds.removeFromTop(20));
    hrirCombo.setBounds(bounds.removeFromTop(28).removeFromLeft(200));
    
    bounds.removeFromTop(20);
    exportAtmosButton.setBounds(bounds.removeFromTop(32).removeFromLeft(150));
}

juce::var SpatialAudioPanel::toJSON() const
{
    auto* obj = new juce::DynamicObject();
    obj->setProperty("mode", modeCombo.getSelectedId());
    obj->setProperty("hrir", hrirCombo.getSelectedId());
    return juce::var(obj);
}

void SpatialAudioPanel::loadFromJSON(const juce::var& json)
{
    if (json.isVoid()) return;
    
    modeCombo.setSelectedId((int)json.getProperty("mode", 1));
    hrirCombo.setSelectedId((int)json.getProperty("hrir", 1));
    showModeControls(modeCombo.getSelectedId());
}

//==============================================================================
// StemSeparationPanel
//==============================================================================

StemSeparationPanel::StemSeparationPanel()
{
    titleLabel.setFont(juce::Font(16.0f, juce::Font::bold));
    titleLabel.setColour(juce::Label::textColourId, juce::Colours::white);
    addAndMakeVisible(titleLabel);
    
    subtitleLabel.setFont(juce::Font(11.0f));
    subtitleLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(subtitleLabel);
    
    loadButton.setColour(juce::TextButton::buttonColourId, AppColours::primary);
    loadButton.onClick = [this]() {
        auto chooser = std::make_shared<juce::FileChooser>(
            "Select Audio File",
            juce::File::getSpecialLocation(juce::File::userMusicDirectory),
            "*.wav;*.mp3;*.flac;*.aiff"
        );
        
        chooser->launchAsync(juce::FileBrowserComponent::openMode, [this, chooser](const juce::FileChooser& fc) {
            auto file = fc.getResult();
            if (file.existsAsFile())
            {
                loadedFile = file;
                fileLabel.setText(file.getFileName(), juce::dontSendNotification);
                separationComplete = false;
            }
        });
    };
    addAndMakeVisible(loadButton);
    
    fileLabel.setFont(juce::Font(11.0f));
    fileLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    fileLabel.setJustificationType(juce::Justification::centred);
    addAndMakeVisible(fileLabel);
    
    backendLabel.setFont(juce::Font(11.0f));
    backendLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(backendLabel);
    
    backendCombo.addItem("Demucs (Meta AI)", 1);
    backendCombo.addItem("Spleeter (Deezer)", 2);
    backendCombo.setSelectedId(1);
    backendCombo.setColour(juce::ComboBox::backgroundColourId, AppColours::inputBg);
    backendCombo.onChange = [this]() {
        // Update model options based on backend
        modelCombo.clear();
        if (backendCombo.getSelectedId() == 1) // Demucs
        {
            modelCombo.addItem("htdemucs (4-stem)", 1);
            modelCombo.addItem("htdemucs_6s (6-stem)", 2);
            modelCombo.addItem("htdemucs_ft (fine-tuned)", 3);
        }
        else // Spleeter
        {
            modelCombo.addItem("2stems (Vocals/Accompaniment)", 1);
            modelCombo.addItem("4stems (Vocals/Drums/Bass/Other)", 2);
            modelCombo.addItem("5stems (+ Piano)", 3);
        }
        modelCombo.setSelectedId(1);
    };
    addAndMakeVisible(backendCombo);
    
    modelLabel.setFont(juce::Font(11.0f));
    modelLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    addAndMakeVisible(modelLabel);
    
    modelCombo.addItem("htdemucs (4-stem)", 1);
    modelCombo.addItem("htdemucs_6s (6-stem)", 2);
    modelCombo.addItem("htdemucs_ft (fine-tuned)", 3);
    modelCombo.setSelectedId(1);
    modelCombo.setColour(juce::ComboBox::backgroundColourId, AppColours::inputBg);
    addAndMakeVisible(modelCombo);
    
    separateButton.setColour(juce::TextButton::buttonColourId, AppColours::success);
    separateButton.onClick = [this]() {
        if (loadedFile.existsAsFile() && onSeparateStems)
            onSeparateStems(loadedFile);
    };
    addAndMakeVisible(separateButton);
    
    progressBar.setColour(juce::ProgressBar::backgroundColourId, AppColours::surfaceAlt);
    progressBar.setColour(juce::ProgressBar::foregroundColourId, AppColours::primary);
    addAndMakeVisible(progressBar);
    
    exportStemsButton.setColour(juce::TextButton::buttonColourId, AppColours::primary);
    exportStemsButton.setEnabled(false);
    addAndMakeVisible(exportStemsButton);
    
    styleTransferButton.setColour(juce::TextButton::buttonColourId, AppColours::warning);
    styleTransferButton.setEnabled(false);
    addAndMakeVisible(styleTransferButton);
}

bool StemSeparationPanel::isInterestedInFileDrag(const juce::StringArray& files)
{
    return files.size() == 1 &&
           (files[0].endsWithIgnoreCase(".wav") ||
            files[0].endsWithIgnoreCase(".mp3") ||
            files[0].endsWithIgnoreCase(".flac") ||
            files[0].endsWithIgnoreCase(".aiff"));
}

void StemSeparationPanel::filesDropped(const juce::StringArray& files, int /*x*/, int /*y*/)
{
    if (files.size() == 1)
    {
        loadedFile = juce::File(files[0]);
        fileLabel.setText(loadedFile.getFileName(), juce::dontSendNotification);
        separationComplete = false;
    }
}

void StemSeparationPanel::paint(juce::Graphics& g)
{
    g.fillAll(AppColours::surface);
    
    // Drop zone
    auto dropArea = fileLabel.getBounds().expanded(4);
    g.setColour(AppColours::border);
    g.drawRoundedRectangle(dropArea.toFloat(), 4.0f, 1.0f);
}

void StemSeparationPanel::resized()
{
    auto bounds = getLocalBounds().reduced(12);
    
    titleLabel.setBounds(bounds.removeFromTop(24));
    subtitleLabel.setBounds(bounds.removeFromTop(18));
    bounds.removeFromTop(12);
    
    // Load section
    auto loadRow = bounds.removeFromTop(28);
    loadButton.setBounds(loadRow.removeFromLeft(100));
    loadRow.removeFromLeft(8);
    fileLabel.setBounds(loadRow);
    
    bounds.removeFromTop(12);
    
    // Backend selection
    auto backendRow = bounds.removeFromTop(28);
    backendLabel.setBounds(backendRow.removeFromLeft(80));
    backendCombo.setBounds(backendRow.removeFromLeft(180));
    
    bounds.removeFromTop(8);
    
    // Model selection
    auto modelRow = bounds.removeFromTop(28);
    modelLabel.setBounds(modelRow.removeFromLeft(80));
    modelCombo.setBounds(modelRow.removeFromLeft(180));
    
    bounds.removeFromTop(16);
    
    // Separate button
    separateButton.setBounds(bounds.removeFromTop(32).removeFromLeft(150));
    
    bounds.removeFromTop(12);
    
    // Progress bar
    progressBar.setBounds(bounds.removeFromTop(24).withTrimmedRight(100));
    
    bounds.removeFromTop(16);
    
    // Export buttons
    auto exportRow = bounds.removeFromTop(32);
    exportStemsButton.setBounds(exportRow.removeFromLeft(130));
    exportRow.removeFromLeft(8);
    styleTransferButton.setBounds(exportRow.removeFromLeft(130));
}

juce::var StemSeparationPanel::toJSON() const
{
    auto* obj = new juce::DynamicObject();
    obj->setProperty("loadedFile", loadedFile.getFullPathName());
    obj->setProperty("backend", backendCombo.getSelectedId());
    obj->setProperty("model", modelCombo.getSelectedId());
    return juce::var(obj);
}

void StemSeparationPanel::loadFromJSON(const juce::var& json)
{
    if (json.isVoid()) return;
    
    juce::String filePath = json.getProperty("loadedFile", "").toString();
    if (filePath.isNotEmpty())
    {
        loadedFile = juce::File(filePath);
        if (loadedFile.existsAsFile())
            fileLabel.setText(loadedFile.getFileName(), juce::dontSendNotification);
    }
    
    backendCombo.setSelectedId((int)json.getProperty("backend", 1));
    modelCombo.setSelectedId((int)json.getProperty("model", 1));
}

