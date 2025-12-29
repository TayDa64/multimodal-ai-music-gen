/*
  ==============================================================================

    FXChainPanel.h
    
    Visual FX chain editor with genre-aware presets.
    Part of NB Phase 2: JUCE Framework & UI Standardization.

  ==============================================================================
*/

#pragma once

#include <juce_gui_basics/juce_gui_basics.h>

//==============================================================================
/**
    FX unit definition representing a single effect in the chain.
*/
struct FXUnit
{
    juce::String id;          // Unique ID
    juce::String type;        // Effect type: "eq", "compressor", "reverb", "delay", "saturation", etc.
    juce::String displayName;
    bool enabled = true;
    
    std::map<juce::String, float> parameters;
    
    /** Parse from JSON */
    static FXUnit fromJSON(const juce::var& json)
    {
        FXUnit fx;
        fx.id = json.getProperty("id", "").toString();
        fx.type = json.getProperty("type", "").toString();
        fx.displayName = json.getProperty("display_name", fx.type).toString();
        fx.enabled = json.getProperty("enabled", true);
        
        if (auto* paramsObj = json.getProperty("parameters", juce::var()).getDynamicObject())
        {
            for (const auto& prop : paramsObj->getProperties())
                fx.parameters[prop.name.toString()] = static_cast<float>(prop.value);
        }
        
        return fx;
    }
    
    /** Convert to JSON */
    juce::var toJSON() const
    {
        auto* obj = new juce::DynamicObject();
        obj->setProperty("id", id);
        obj->setProperty("type", type);
        obj->setProperty("display_name", displayName);
        obj->setProperty("enabled", enabled);
        
        auto* paramsObj = new juce::DynamicObject();
        for (const auto& [key, value] : parameters)
            paramsObj->setProperty(juce::Identifier(key), value);
        
        obj->setProperty("parameters", juce::var(paramsObj));
        return juce::var(obj);
    }
};

//==============================================================================
/**
    FX chain preset for a specific bus (master, drums, bass, melodic).
*/
struct FXChainPreset
{
    juce::String name;
    juce::String bus;  // "master", "drums", "bass", "melodic"
    juce::Array<FXUnit> chain;
    
    /** Parse from JSON */
    static FXChainPreset fromJSON(const juce::var& json)
    {
        FXChainPreset preset;
        preset.name = json.getProperty("name", "").toString();
        preset.bus = json.getProperty("bus", "master").toString();
        
        if (auto* chainArray = json.getProperty("chain", juce::var()).getArray())
        {
            for (const auto& fxVar : *chainArray)
                preset.chain.add(FXUnit::fromJSON(fxVar));
        }
        
        return preset;
    }
};

//==============================================================================
/**
    Visual component for a single FX unit in the chain.
*/
class FXUnitComponent : public juce::Component
{
public:
    FXUnitComponent(const FXUnit& unit);
    
    void paint(juce::Graphics& g) override;
    void resized() override;
    void mouseDown(const juce::MouseEvent& e) override;
    void mouseDrag(const juce::MouseEvent& e) override;
    
    const FXUnit& getFXUnit() const { return fxUnit; }
    void setFXUnit(const FXUnit& unit);
    
    void setSelected(bool selected);
    bool isSelected() const { return selected; }
    
    void setEnabled(bool enabled);
    bool isEnabled() const { return fxUnit.enabled; }
    
    /** Listener for FX unit events */
    class Listener
    {
    public:
        virtual ~Listener() = default;
        virtual void fxUnitClicked(FXUnitComponent* unit) = 0;
        virtual void fxUnitToggled(FXUnitComponent* unit, bool enabled) = 0;
        virtual void fxUnitDragged(FXUnitComponent* unit, const juce::MouseEvent& e) = 0;
    };
    
    void setListener(Listener* l) { listener = l; }
    
private:
    juce::Colour getTypeColor() const;
    juce::String getTypeIcon() const;
    
    FXUnit fxUnit;
    bool selected = false;
    Listener* listener = nullptr;
    
    juce::ToggleButton enableButton;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(FXUnitComponent)
};

//==============================================================================
/**
    FX chain strip showing a horizontal chain of effects.
*/
class FXChainStrip : public juce::Component,
                      public FXUnitComponent::Listener
{
public:
    FXChainStrip();
    ~FXChainStrip() override;
    
    void paint(juce::Graphics& g) override;
    void resized() override;
    
    void setChain(const juce::Array<FXUnit>& chain);
    void addFXUnit(const FXUnit& unit);
    void removeFXUnit(int index);
    void clearChain();
    
    void setBusName(const juce::String& name);
    juce::String getBusName() const { return busName; }
    
    /** Get the current chain */
    juce::Array<FXUnit> getChain() const;
    
    /** Listener for chain changes */
    class Listener
    {
    public:
        virtual ~Listener() = default;
        virtual void chainChanged(FXChainStrip* strip) = 0;
        virtual void fxUnitSelected(FXChainStrip* strip, FXUnitComponent* unit) = 0;
    };
    
    void addListener(Listener* l) { listeners.add(l); }
    void removeListener(Listener* l) { listeners.remove(l); }
    
private:
    void fxUnitClicked(FXUnitComponent* unit) override;
    void fxUnitToggled(FXUnitComponent* unit, bool enabled) override;
    void fxUnitDragged(FXUnitComponent* unit, const juce::MouseEvent& e) override;
    void updateLayout();
    
    juce::String busName;
    juce::OwnedArray<FXUnitComponent> fxUnits;
    FXUnitComponent* selectedUnit = nullptr;
    
    juce::Label busLabel;
    juce::TextButton addButton { "+" };
    
    juce::ListenerList<Listener> listeners;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(FXChainStrip)
};

//==============================================================================
/**
    FX parameter editor panel for the selected effect.
*/
class FXParameterPanel : public juce::Component
{
public:
    FXParameterPanel();
    
    void paint(juce::Graphics& g) override;
    void resized() override;
    
    void setFXUnit(const FXUnit& unit);
    void clearFXUnit();
    
    /** Listener for parameter changes */
    class Listener
    {
    public:
        virtual ~Listener() = default;
        virtual void parameterChanged(const juce::String& fxId, 
                                       const juce::String& paramName, 
                                       float value) = 0;
    };
    
    void addListener(Listener* l) { listeners.add(l); }
    void removeListener(Listener* l) { listeners.remove(l); }
    
private:
    void updateSliders();
    
    FXUnit currentUnit;
    bool hasUnit = false;
    
    juce::Label titleLabel;
    juce::OwnedArray<juce::Slider> sliders;
    juce::OwnedArray<juce::Label> labels;
    
    juce::ListenerList<Listener> listeners;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(FXParameterPanel)
};

//==============================================================================
/**
    Main FX Chain Panel with multiple bus strips and genre presets.
    
    Layout:
    ┌─────────────────────────────────────────────────────────────┐
    │ FX Chain                      [Genre Preset ▼] [Reset]      │
    ├─────────────────────────────────────────────────────────────┤
    │ Master: [EQ]──>[Comp]──>[Sat]──>[Limiter]     [+]           │
    │ ─────────────────────────────────────────────────────────── │
    │ Drums:  [EQ]──>[Comp]──>[Sat]                 [+]           │
    │ ─────────────────────────────────────────────────────────── │
    │ Bass:   [EQ]──>[Comp]                         [+]           │
    │ ─────────────────────────────────────────────────────────── │
    │ Melodic:[EQ]──>[Rev]──>[Delay]                [+]           │
    ├─────────────────────────────────────────────────────────────┤
    │ Selected: Compressor                                        │
    │ ┌─────────────────────────────────────────────────────────┐ │
    │ │ Threshold: [=======|===] -12dB                          │ │
    │ │ Ratio:     [====|======] 4:1                            │ │
    │ │ Attack:    [==|========] 10ms                           │ │
    │ │ Release:   [=====|=====] 100ms                          │ │
    │ └─────────────────────────────────────────────────────────┘ │
    └─────────────────────────────────────────────────────────────┘
*/
class FXChainPanel : public juce::Component,
                      public FXChainStrip::Listener,
                      public FXParameterPanel::Listener
{
public:
    FXChainPanel();
    ~FXChainPanel() override;
    
    void paint(juce::Graphics& g) override;
    void resized() override;
    
    /** Load FX chains from genre template JSON */
    void loadFromGenre(const juce::String& genreId, const juce::var& fxChainsJSON);
    
    /** Load specific preset */
    void loadPreset(const juce::String& presetName);
    
    /** Reset to default (no FX) */
    void resetToDefault();
    
    /** Get current FX chain for a bus */
    juce::Array<FXUnit> getChainForBus(const juce::String& bus) const;
    
    /** Get all chains as JSON for OSC transmission */
    juce::String toJSON() const;
    
    /** Listener for FX chain changes */
    class Listener
    {
    public:
        virtual ~Listener() = default;
        virtual void fxChainChanged(FXChainPanel* panel) = 0;
    };
    
    void addListener(Listener* l) { listeners.add(l); }
    void removeListener(Listener* l) { listeners.remove(l); }
    
private:
    void chainChanged(FXChainStrip* strip) override;
    void fxUnitSelected(FXChainStrip* strip, FXUnitComponent* unit) override;
    void parameterChanged(const juce::String& fxId, 
                          const juce::String& paramName, 
                          float value) override;
    
    void applyGenrePreset(const juce::String& genreId);
    void populatePresetComboBox();
    
    // Header
    juce::Label titleLabel;
    juce::ComboBox presetComboBox;
    juce::TextButton resetButton { "Reset" };
    
    // Bus strips
    FXChainStrip masterStrip;
    FXChainStrip drumsStrip;
    FXChainStrip bassStrip;
    FXChainStrip melodicStrip;
    
    // Parameter editor
    FXParameterPanel parameterPanel;
    
    // Current genre
    juce::String currentGenre;
    
    // Available presets
    juce::StringArray availablePresets;
    
    juce::ListenerList<Listener> listeners;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(FXChainPanel)
};
