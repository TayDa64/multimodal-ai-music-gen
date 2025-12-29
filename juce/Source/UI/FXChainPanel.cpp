/*
  ==============================================================================

    FXChainPanel.cpp
    
    Implementation of the FX chain visual editor.

  ==============================================================================
*/

#include "FXChainPanel.h"

//==============================================================================
// FXUnitComponent
//==============================================================================

FXUnitComponent::FXUnitComponent(const FXUnit& unit)
    : fxUnit(unit)
{
    enableButton.setToggleState(unit.enabled, juce::dontSendNotification);
    enableButton.onClick = [this]() {
        fxUnit.enabled = enableButton.getToggleState();
        if (listener)
            listener->fxUnitToggled(this, fxUnit.enabled);
        repaint();
    };
    addAndMakeVisible(enableButton);
}

juce::Colour FXUnitComponent::getTypeColor() const
{
    if (fxUnit.type == "eq" || fxUnit.type == "equalizer")
        return juce::Colour(100, 200, 255);  // Blue
    if (fxUnit.type == "compressor" || fxUnit.type == "comp")
        return juce::Colour(255, 200, 100);  // Orange
    if (fxUnit.type == "reverb" || fxUnit.type == "rev")
        return juce::Colour(200, 150, 255);  // Purple
    if (fxUnit.type == "delay")
        return juce::Colour(150, 255, 200);  // Cyan/Green
    if (fxUnit.type == "saturation" || fxUnit.type == "sat" || fxUnit.type == "distortion")
        return juce::Colour(255, 100, 100);  // Red
    if (fxUnit.type == "limiter")
        return juce::Colour(255, 255, 100);  // Yellow
    if (fxUnit.type == "chorus")
        return juce::Colour(100, 255, 200);  // Teal
    if (fxUnit.type == "filter")
        return juce::Colour(255, 150, 200);  // Pink
    
    return juce::Colours::grey;
}

juce::String FXUnitComponent::getTypeIcon() const
{
    if (fxUnit.type == "eq" || fxUnit.type == "equalizer")
        return "≈";
    if (fxUnit.type == "compressor" || fxUnit.type == "comp")
        return "◉";
    if (fxUnit.type == "reverb" || fxUnit.type == "rev")
        return "◎";
    if (fxUnit.type == "delay")
        return "⟳";
    if (fxUnit.type == "saturation" || fxUnit.type == "sat" || fxUnit.type == "distortion")
        return "⚡";
    if (fxUnit.type == "limiter")
        return "▬";
    if (fxUnit.type == "chorus")
        return "◇";
    if (fxUnit.type == "filter")
        return "∿";
    
    return "●";
}

void FXUnitComponent::paint(juce::Graphics& g)
{
    auto bounds = getLocalBounds().reduced(2);
    
    juce::Colour bgColor = getTypeColor();
    if (!fxUnit.enabled)
        bgColor = bgColor.withAlpha(0.3f);
    
    // Background
    g.setColour(bgColor.darker(0.3f));
    g.fillRoundedRectangle(bounds.toFloat(), 8.0f);
    
    // Gradient overlay
    g.setGradientFill(juce::ColourGradient(
        bgColor.brighter(0.2f), bounds.getX(), bounds.getY(),
        bgColor.darker(0.2f), bounds.getX(), bounds.getBottom(),
        false
    ));
    g.fillRoundedRectangle(bounds.reduced(1).toFloat(), 7.0f);
    
    // Selection border
    if (selected)
    {
        g.setColour(juce::Colours::white);
        g.drawRoundedRectangle(bounds.toFloat(), 8.0f, 2.0f);
    }
    
    // Icon
    g.setColour(fxUnit.enabled ? juce::Colours::white : juce::Colours::grey);
    g.setFont(20.0f);
    g.drawText(getTypeIcon(), bounds.removeFromTop(30), juce::Justification::centred);
    
    // Name
    g.setFont(11.0f);
    g.drawText(fxUnit.displayName, bounds.reduced(2, 0), juce::Justification::centred);
}

void FXUnitComponent::resized()
{
    auto bounds = getLocalBounds();
    enableButton.setBounds(bounds.removeFromBottom(20).reduced(5, 2));
}

void FXUnitComponent::mouseDown(const juce::MouseEvent& e)
{
    if (listener)
        listener->fxUnitClicked(this);
}

void FXUnitComponent::mouseDrag(const juce::MouseEvent& e)
{
    if (listener)
        listener->fxUnitDragged(this, e);
}

void FXUnitComponent::setFXUnit(const FXUnit& unit)
{
    fxUnit = unit;
    enableButton.setToggleState(unit.enabled, juce::dontSendNotification);
    repaint();
}

void FXUnitComponent::setSelected(bool sel)
{
    selected = sel;
    repaint();
}

void FXUnitComponent::setEnabled(bool enabled)
{
    fxUnit.enabled = enabled;
    enableButton.setToggleState(enabled, juce::dontSendNotification);
    repaint();
}

//==============================================================================
// FXChainStrip
//==============================================================================

FXChainStrip::FXChainStrip()
{
    busLabel.setFont(juce::Font(13.0f, juce::Font::bold));
    busLabel.setColour(juce::Label::textColourId, juce::Colours::lightgrey);
    addAndMakeVisible(busLabel);
    
    addButton.setColour(juce::TextButton::buttonColourId, juce::Colour(60, 60, 70));
    addButton.onClick = [this]() {
        // Show FX selection menu
        juce::PopupMenu menu;
        menu.addItem(1, "EQ");
        menu.addItem(2, "Compressor");
        menu.addItem(3, "Reverb");
        menu.addItem(4, "Delay");
        menu.addItem(5, "Saturation");
        menu.addItem(6, "Limiter");
        menu.addItem(7, "Chorus");
        menu.addItem(8, "Filter");
        
        menu.showMenuAsync(juce::PopupMenu::Options(),
            [this](int result) {
                if (result > 0)
                {
                    FXUnit newUnit;
                    newUnit.id = juce::Uuid().toString();
                    
                    switch (result)
                    {
                        case 1: newUnit.type = "eq"; newUnit.displayName = "EQ"; break;
                        case 2: newUnit.type = "compressor"; newUnit.displayName = "Comp"; break;
                        case 3: newUnit.type = "reverb"; newUnit.displayName = "Reverb"; break;
                        case 4: newUnit.type = "delay"; newUnit.displayName = "Delay"; break;
                        case 5: newUnit.type = "saturation"; newUnit.displayName = "Sat"; break;
                        case 6: newUnit.type = "limiter"; newUnit.displayName = "Limiter"; break;
                        case 7: newUnit.type = "chorus"; newUnit.displayName = "Chorus"; break;
                        case 8: newUnit.type = "filter"; newUnit.displayName = "Filter"; break;
                    }
                    
                    addFXUnit(newUnit);
                }
            });
    };
    addAndMakeVisible(addButton);
}

FXChainStrip::~FXChainStrip() {}

void FXChainStrip::paint(juce::Graphics& g)
{
    auto bounds = getLocalBounds();
    
    // Background
    g.setColour(juce::Colour(35, 35, 40));
    g.fillRoundedRectangle(bounds.toFloat(), 4.0f);
    
    // Draw connection lines between FX units
    if (fxUnits.size() > 1)
    {
        g.setColour(juce::Colour(80, 80, 90));
        
        auto chainBounds = bounds;
        chainBounds.removeFromLeft(70);  // Bus label
        chainBounds.removeFromRight(35); // Add button
        
        int unitWidth = 65;
        int spacing = 15;
        int y = chainBounds.getCentreY();
        
        for (int i = 0; i < fxUnits.size() - 1; ++i)
        {
            int x1 = chainBounds.getX() + (i + 1) * (unitWidth + spacing) - spacing/2;
            int x2 = x1 + spacing;
            
            // Arrow line
            g.drawArrow(juce::Line<float>(x1, y, x2, y), 2.0f, 8.0f, 6.0f);
        }
    }
}

void FXChainStrip::resized()
{
    auto bounds = getLocalBounds();
    
    busLabel.setBounds(bounds.removeFromLeft(70));
    addButton.setBounds(bounds.removeFromRight(30).reduced(2, 8));
    
    updateLayout();
}

void FXChainStrip::setChain(const juce::Array<FXUnit>& chain)
{
    clearChain();
    
    for (const auto& unit : chain)
        addFXUnit(unit);
}

void FXChainStrip::addFXUnit(const FXUnit& unit)
{
    auto* comp = fxUnits.add(new FXUnitComponent(unit));
    comp->setListener(this);
    addAndMakeVisible(comp);
    updateLayout();
    
    listeners.call([this](Listener& l) { l.chainChanged(this); });
}

void FXChainStrip::removeFXUnit(int index)
{
    if (index >= 0 && index < fxUnits.size())
    {
        if (fxUnits[index] == selectedUnit)
            selectedUnit = nullptr;
        
        fxUnits.remove(index);
        updateLayout();
        
        listeners.call([this](Listener& l) { l.chainChanged(this); });
    }
}

void FXChainStrip::clearChain()
{
    selectedUnit = nullptr;
    fxUnits.clear();
}

void FXChainStrip::setBusName(const juce::String& name)
{
    busName = name;
    busLabel.setText(name + ":", juce::dontSendNotification);
}

juce::Array<FXUnit> FXChainStrip::getChain() const
{
    juce::Array<FXUnit> chain;
    for (auto* comp : fxUnits)
        chain.add(comp->getFXUnit());
    return chain;
}

void FXChainStrip::fxUnitClicked(FXUnitComponent* unit)
{
    if (selectedUnit && selectedUnit != unit)
        selectedUnit->setSelected(false);
    
    selectedUnit = unit;
    selectedUnit->setSelected(true);
    
    listeners.call([this, unit](Listener& l) { l.fxUnitSelected(this, unit); });
}

void FXChainStrip::fxUnitToggled(FXUnitComponent* unit, bool enabled)
{
    listeners.call([this](Listener& l) { l.chainChanged(this); });
}

void FXChainStrip::fxUnitDragged(FXUnitComponent* unit, const juce::MouseEvent& e)
{
    // TODO: Implement drag reordering
}

void FXChainStrip::updateLayout()
{
    auto bounds = getLocalBounds();
    bounds.removeFromLeft(70);  // Bus label
    bounds.removeFromRight(35); // Add button
    bounds = bounds.reduced(5);
    
    int unitWidth = 60;
    int spacing = 15;
    int x = bounds.getX();
    
    for (auto* unit : fxUnits)
    {
        unit->setBounds(x, bounds.getY(), unitWidth, bounds.getHeight());
        x += unitWidth + spacing;
    }
}

//==============================================================================
// FXParameterPanel
//==============================================================================

FXParameterPanel::FXParameterPanel()
{
    titleLabel.setFont(juce::Font(14.0f, juce::Font::bold));
    titleLabel.setColour(juce::Label::textColourId, juce::Colours::white);
    titleLabel.setText("Select an effect to edit", juce::dontSendNotification);
    addAndMakeVisible(titleLabel);
}

void FXParameterPanel::paint(juce::Graphics& g)
{
    auto bounds = getLocalBounds();
    
    g.setColour(juce::Colour(30, 30, 35));
    g.fillRoundedRectangle(bounds.toFloat(), 4.0f);
    
    // Top border
    g.setColour(juce::Colour(50, 50, 60));
    g.drawLine(0, 0, getWidth(), 0, 1.0f);
}

void FXParameterPanel::resized()
{
    auto bounds = getLocalBounds().reduced(10, 5);
    
    titleLabel.setBounds(bounds.removeFromTop(25));
    bounds.removeFromTop(5);
    
    // Layout sliders in a grid
    int sliderHeight = 30;
    int y = bounds.getY();
    
    for (int i = 0; i < sliders.size(); ++i)
    {
        auto row = bounds.removeFromTop(sliderHeight);
        
        if (i < labels.size())
            labels[i]->setBounds(row.removeFromLeft(80));
        
        sliders[i]->setBounds(row);
    }
}

void FXParameterPanel::setFXUnit(const FXUnit& unit)
{
    currentUnit = unit;
    hasUnit = true;
    
    titleLabel.setText(unit.displayName + " Parameters", juce::dontSendNotification);
    
    updateSliders();
}

void FXParameterPanel::clearFXUnit()
{
    hasUnit = false;
    currentUnit = {};
    titleLabel.setText("Select an effect to edit", juce::dontSendNotification);
    sliders.clear();
    labels.clear();
    repaint();
}

void FXParameterPanel::updateSliders()
{
    sliders.clear();
    labels.clear();
    
    // Create sliders based on FX type
    std::vector<std::pair<juce::String, std::pair<float, float>>> params;
    
    if (currentUnit.type == "eq" || currentUnit.type == "equalizer")
    {
        params = {
            {"Low", {-12.0f, 12.0f}},
            {"Mid", {-12.0f, 12.0f}},
            {"High", {-12.0f, 12.0f}},
            {"Low Freq", {50.0f, 500.0f}},
            {"High Freq", {2000.0f, 12000.0f}}
        };
    }
    else if (currentUnit.type == "compressor" || currentUnit.type == "comp")
    {
        params = {
            {"Threshold", {-60.0f, 0.0f}},
            {"Ratio", {1.0f, 20.0f}},
            {"Attack", {0.1f, 100.0f}},
            {"Release", {10.0f, 1000.0f}},
            {"Makeup", {0.0f, 24.0f}}
        };
    }
    else if (currentUnit.type == "reverb" || currentUnit.type == "rev")
    {
        params = {
            {"Size", {0.0f, 1.0f}},
            {"Decay", {0.1f, 10.0f}},
            {"Damping", {0.0f, 1.0f}},
            {"Mix", {0.0f, 1.0f}},
            {"Pre-Delay", {0.0f, 100.0f}}
        };
    }
    else if (currentUnit.type == "delay")
    {
        params = {
            {"Time", {1.0f, 2000.0f}},
            {"Feedback", {0.0f, 0.95f}},
            {"Mix", {0.0f, 1.0f}},
            {"HP Filter", {20.0f, 2000.0f}},
            {"LP Filter", {1000.0f, 20000.0f}}
        };
    }
    else if (currentUnit.type == "saturation" || currentUnit.type == "sat")
    {
        params = {
            {"Drive", {0.0f, 100.0f}},
            {"Mix", {0.0f, 1.0f}},
            {"Tone", {0.0f, 1.0f}},
            {"Output", {-12.0f, 12.0f}}
        };
    }
    else if (currentUnit.type == "limiter")
    {
        params = {
            {"Ceiling", {-12.0f, 0.0f}},
            {"Release", {10.0f, 500.0f}}
        };
    }
    
    for (const auto& [name, range] : params)
    {
        auto* label = labels.add(new juce::Label({}, name));
        label->setColour(juce::Label::textColourId, juce::Colours::lightgrey);
        addAndMakeVisible(label);
        
        auto* slider = sliders.add(new juce::Slider(juce::Slider::LinearHorizontal, 
                                                     juce::Slider::TextBoxRight));
        slider->setRange(range.first, range.second);
        slider->setColour(juce::Slider::trackColourId, juce::Colour(60, 60, 100));
        slider->setColour(juce::Slider::thumbColourId, juce::Colour(100, 150, 255));
        
        // Set current value if exists
        auto it = currentUnit.parameters.find(name.toLowerCase().replaceCharacter(' ', '_'));
        if (it != currentUnit.parameters.end())
            slider->setValue(it->second, juce::dontSendNotification);
        else
            slider->setValue((range.first + range.second) / 2.0f, juce::dontSendNotification);
        
        juce::String paramName = name.toLowerCase().replaceCharacter(' ', '_');
        slider->onValueChange = [this, paramName]() {
            // Find the slider and notify
            for (int i = 0; i < sliders.size(); ++i)
            {
                if (auto* s = sliders[i])
                {
                    listeners.call([&](Listener& l) {
                        l.parameterChanged(currentUnit.id, paramName, (float)s->getValue());
                    });
                    break;
                }
            }
        };
        
        addAndMakeVisible(slider);
    }
    
    resized();
}

//==============================================================================
// FXChainPanel
//==============================================================================

FXChainPanel::FXChainPanel()
{
    titleLabel.setText("FX Chain", juce::dontSendNotification);
    titleLabel.setFont(juce::Font(16.0f, juce::Font::bold));
    titleLabel.setColour(juce::Label::textColourId, juce::Colours::white);
    
    presetComboBox.setTextWhenNothingSelected("Select Preset...");
    presetComboBox.onChange = [this]() {
        int idx = presetComboBox.getSelectedItemIndex();
        if (idx >= 0 && idx < availablePresets.size())
            loadPreset(availablePresets[idx]);
    };
    
    resetButton.setColour(juce::TextButton::buttonColourId, juce::Colour(80, 50, 50));
    resetButton.onClick = [this]() { resetToDefault(); };
    
    addAndMakeVisible(titleLabel);
    addAndMakeVisible(presetComboBox);
    addAndMakeVisible(resetButton);
    
    // Setup bus strips
    masterStrip.setBusName("Master");
    drumsStrip.setBusName("Drums");
    bassStrip.setBusName("Bass");
    melodicStrip.setBusName("Melodic");
    
    masterStrip.addListener(this);
    drumsStrip.addListener(this);
    bassStrip.addListener(this);
    melodicStrip.addListener(this);
    
    addAndMakeVisible(masterStrip);
    addAndMakeVisible(drumsStrip);
    addAndMakeVisible(bassStrip);
    addAndMakeVisible(melodicStrip);
    
    parameterPanel.addListener(this);
    addAndMakeVisible(parameterPanel);
    
    // Populate presets
    populatePresetComboBox();
}

FXChainPanel::~FXChainPanel() {}

void FXChainPanel::paint(juce::Graphics& g)
{
    g.fillAll(juce::Colour(25, 25, 30));
    
    // Header background
    g.setColour(juce::Colour(35, 35, 40));
    g.fillRect(0, 0, getWidth(), 40);
}

void FXChainPanel::resized()
{
    auto bounds = getLocalBounds();
    
    // Header
    auto header = bounds.removeFromTop(40).reduced(10, 5);
    titleLabel.setBounds(header.removeFromLeft(100));
    resetButton.setBounds(header.removeFromRight(60));
    header.removeFromRight(10);
    presetComboBox.setBounds(header.removeFromRight(150));
    
    // Parameter panel (bottom)
    parameterPanel.setBounds(bounds.removeFromBottom(180));
    
    // Bus strips
    int stripHeight = 60;
    bounds = bounds.reduced(5);
    
    masterStrip.setBounds(bounds.removeFromTop(stripHeight));
    bounds.removeFromTop(5);
    drumsStrip.setBounds(bounds.removeFromTop(stripHeight));
    bounds.removeFromTop(5);
    bassStrip.setBounds(bounds.removeFromTop(stripHeight));
    bounds.removeFromTop(5);
    melodicStrip.setBounds(bounds.removeFromTop(stripHeight));
}

void FXChainPanel::loadFromGenre(const juce::String& genreId, const juce::var& fxChainsJSON)
{
    currentGenre = genreId;
    
    // Parse FX chains for each bus
    auto parseFXChain = [](const juce::var& json) -> juce::Array<FXUnit> {
        juce::Array<FXUnit> chain;
        if (auto* arr = json.getArray())
        {
            for (const auto& item : *arr)
            {
                FXUnit unit;
                unit.id = juce::Uuid().toString();
                
                // Handle both string format ("EQ") and object format
                if (item.isString())
                {
                    unit.type = item.toString().toLowerCase();
                    unit.displayName = item.toString();
                }
                else
                {
                    unit = FXUnit::fromJSON(item);
                }
                
                chain.add(unit);
            }
        }
        return chain;
    };
    
    // Load chains
    masterStrip.setChain(parseFXChain(fxChainsJSON.getProperty("master", juce::var())));
    drumsStrip.setChain(parseFXChain(fxChainsJSON.getProperty("drums", juce::var())));
    bassStrip.setChain(parseFXChain(fxChainsJSON.getProperty("bass", juce::var())));
    melodicStrip.setChain(parseFXChain(fxChainsJSON.getProperty("melodic", juce::var())));
}

void FXChainPanel::loadPreset(const juce::String& presetName)
{
    applyGenrePreset(presetName);
}

void FXChainPanel::resetToDefault()
{
    masterStrip.clearChain();
    drumsStrip.clearChain();
    bassStrip.clearChain();
    melodicStrip.clearChain();
    parameterPanel.clearFXUnit();
    
    listeners.call([this](Listener& l) { l.fxChainChanged(this); });
}

juce::Array<FXUnit> FXChainPanel::getChainForBus(const juce::String& bus) const
{
    if (bus == "master") return masterStrip.getChain();
    if (bus == "drums") return drumsStrip.getChain();
    if (bus == "bass") return bassStrip.getChain();
    if (bus == "melodic") return melodicStrip.getChain();
    return {};
}

juce::String FXChainPanel::toJSON() const
{
    auto* root = new juce::DynamicObject();
    
    auto chainToVar = [](const juce::Array<FXUnit>& chain) -> juce::var {
        juce::Array<juce::var> arr;
        for (const auto& unit : chain)
            arr.add(unit.toJSON());
        return juce::var(arr);
    };
    
    root->setProperty("master", chainToVar(masterStrip.getChain()));
    root->setProperty("drums", chainToVar(drumsStrip.getChain()));
    root->setProperty("bass", chainToVar(bassStrip.getChain()));
    root->setProperty("melodic", chainToVar(melodicStrip.getChain()));
    
    return juce::JSON::toString(juce::var(root));
}

void FXChainPanel::chainChanged(FXChainStrip* strip)
{
    listeners.call([this](Listener& l) { l.fxChainChanged(this); });
}

void FXChainPanel::fxUnitSelected(FXChainStrip* strip, FXUnitComponent* unit)
{
    // Deselect from other strips
    if (strip != &masterStrip) { /* deselect in masterStrip */ }
    if (strip != &drumsStrip) { /* deselect in drumsStrip */ }
    if (strip != &bassStrip) { /* deselect in bassStrip */ }
    if (strip != &melodicStrip) { /* deselect in melodicStrip */ }
    
    if (unit)
        parameterPanel.setFXUnit(unit->getFXUnit());
    else
        parameterPanel.clearFXUnit();
}

void FXChainPanel::parameterChanged(const juce::String& fxId, 
                                     const juce::String& paramName, 
                                     float value)
{
    // Update the FX unit parameter
    // This would need to find the unit by ID and update it
    
    listeners.call([this](Listener& l) { l.fxChainChanged(this); });
}

void FXChainPanel::applyGenrePreset(const juce::String& genreId)
{
    // Hardcoded genre presets matching Python genres.json
    
    auto createUnit = [](const juce::String& type, const juce::String& name) {
        FXUnit unit;
        unit.id = juce::Uuid().toString();
        unit.type = type.toLowerCase();
        unit.displayName = name;
        unit.enabled = true;
        return unit;
    };
    
    if (genreId == "trap" || genreId == "drill")
    {
        masterStrip.setChain({ createUnit("eq", "EQ"), createUnit("comp", "Comp"), 
                               createUnit("saturation", "Sat"), createUnit("limiter", "Limiter") });
        drumsStrip.setChain({ createUnit("eq", "EQ"), createUnit("comp", "Comp"), 
                              createUnit("saturation", "Sat") });
        bassStrip.setChain({ createUnit("eq", "EQ"), createUnit("comp", "Comp") });
        melodicStrip.setChain({ createUnit("eq", "EQ"), createUnit("reverb", "Reverb"), 
                                createUnit("delay", "Delay") });
    }
    else if (genreId == "lofi")
    {
        masterStrip.setChain({ createUnit("eq", "EQ"), createUnit("saturation", "Sat"), 
                               createUnit("comp", "Comp") });
        drumsStrip.setChain({ createUnit("saturation", "Sat"), createUnit("filter", "Filter") });
        bassStrip.setChain({ createUnit("saturation", "Sat") });
        melodicStrip.setChain({ createUnit("filter", "Filter"), createUnit("chorus", "Chorus"), 
                                createUnit("reverb", "Reverb") });
    }
    else if (genreId == "boom_bap")
    {
        masterStrip.setChain({ createUnit("eq", "EQ"), createUnit("comp", "Comp") });
        drumsStrip.setChain({ createUnit("eq", "EQ"), createUnit("comp", "Comp"), 
                              createUnit("saturation", "Sat") });
        bassStrip.setChain({ createUnit("eq", "EQ") });
        melodicStrip.setChain({ createUnit("eq", "EQ"), createUnit("reverb", "Reverb") });
    }
    else if (genreId == "house")
    {
        masterStrip.setChain({ createUnit("eq", "EQ"), createUnit("comp", "Comp"), 
                               createUnit("limiter", "Limiter") });
        drumsStrip.setChain({ createUnit("eq", "EQ"), createUnit("comp", "Comp") });
        bassStrip.setChain({ createUnit("eq", "EQ"), createUnit("comp", "Comp") });
        melodicStrip.setChain({ createUnit("eq", "EQ"), createUnit("reverb", "Reverb"), 
                                createUnit("delay", "Delay") });
    }
    else if (genreId == "g_funk")
    {
        masterStrip.setChain({ createUnit("eq", "EQ"), createUnit("comp", "Comp") });
        drumsStrip.setChain({ createUnit("eq", "EQ"), createUnit("comp", "Comp") });
        bassStrip.setChain({ createUnit("eq", "EQ"), createUnit("chorus", "Chorus") });
        melodicStrip.setChain({ createUnit("eq", "EQ"), createUnit("chorus", "Chorus"), 
                                createUnit("reverb", "Reverb") });
    }
    else if (genreId == "ethiopian_traditional" || genreId == "eskista")
    {
        masterStrip.setChain({ createUnit("eq", "EQ"), createUnit("comp", "Comp") });
        drumsStrip.setChain({ createUnit("eq", "EQ"), createUnit("comp", "Comp") });
        bassStrip.setChain({ createUnit("eq", "EQ") });
        melodicStrip.setChain({ createUnit("eq", "EQ"), createUnit("reverb", "Reverb") });
    }
    else
    {
        // Default minimal chain
        masterStrip.setChain({ createUnit("eq", "EQ"), createUnit("comp", "Comp"), 
                               createUnit("limiter", "Limiter") });
        drumsStrip.setChain({ createUnit("eq", "EQ"), createUnit("comp", "Comp") });
        bassStrip.setChain({ createUnit("eq", "EQ") });
        melodicStrip.setChain({ createUnit("eq", "EQ") });
    }
    
    currentGenre = genreId;
    listeners.call([this](Listener& l) { l.fxChainChanged(this); });
}

void FXChainPanel::populatePresetComboBox()
{
    availablePresets = { "trap", "trap_soul", "lofi", "boom_bap", "house", 
                         "drill", "g_funk", "rnb", "ethiopian_traditional", "eskista" };
    
    presetComboBox.clear();
    int id = 1;
    for (const auto& preset : availablePresets)
    {
        juce::String displayName = preset;
        displayName = displayName.replace("_", " ");
        displayName = displayName.substring(0, 1).toUpperCase() + displayName.substring(1);
        
        presetComboBox.addItem(displayName, id++);
    }
}
