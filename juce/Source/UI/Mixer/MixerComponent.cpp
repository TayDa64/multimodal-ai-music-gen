#include "MixerComponent.h"

namespace UI
{
    MixerComponent::MixerComponent()
    {
        addAndMakeVisible(viewport);
        viewport.setViewedComponent(&container, false);
        viewport.setScrollBarsShown(true, true); // Allow both horizontal and vertical scrolling
    }

    MixerComponent::~MixerComponent()
    {
        if (projectState)
            projectState->getState().removeListener(this);
    }

    void MixerComponent::paint(juce::Graphics& g)
    {
        g.fillAll(juce::Colours::black);
    }

    void MixerComponent::resized()
    {
        viewport.setBounds(getLocalBounds());
        
        // Update container size
        if (strips.size() > 0)
        {
            int stripWidth = 80;
            int totalWidth = strips.size() * stripWidth;
            
            // Ensure minimum height for strips to be usable
            int minHeight = 280;
            int containerHeight = juce::jmax(minHeight, viewport.getHeight() - 16); // -16 for scrollbar
            
            container.setBounds(0, 0, totalWidth, containerHeight);
            
            // Layout strips
            for (int i = 0; i < strips.size(); ++i)
            {
                strips[i]->setBounds(i * stripWidth, 0, stripWidth, container.getHeight());
            }
        }
    }

    void MixerComponent::setTracks(const juce::StringArray& trackNames)
    {
        strips.clear();
        
        for (int i = 0; i < trackNames.size(); ++i)
        {
            auto* strip = new ChannelStrip(trackNames[i]);
            container.addAndMakeVisible(strip);
            strips.add(strip);
            
            // Selection logic
            strip->onSelectionChange = [this, i]() {
                selectTrack(i);
            };
            
            if (projectState)
            {
                // Bind sliders to project state
                // Volume
                strip->getVolumeSlider().onValueChange = [this, i, strip]() {
                    projectState->setTrackVolume(i, (float)strip->getVolumeSlider().getValue());
                };
                
                // Pan
                strip->getPanSlider().onValueChange = [this, i, strip]() {
                    projectState->setTrackPan(i, (float)strip->getPanSlider().getValue());
                };
                
                // Mute
                strip->getMuteButton().onClick = [this, i, strip]() {
                    projectState->setTrackMute(i, strip->getMuteButton().getToggleState());
                };
                
                // Solo
                strip->getSoloButton().onClick = [this, i, strip]() {
                    projectState->setTrackSolo(i, strip->getSoloButton().getToggleState());
                };
                
                // Initialize from state
                updateStripFromState(i);
            }
        }
        
        // Restore selection or default to 0
        if (selectedTrackIndex >= strips.size()) selectedTrackIndex = 0;
        selectTrack(selectedTrackIndex);
        
        resized();
    }

    void MixerComponent::selectTrack(int index)
    {
        if (index < 0 || index >= strips.size()) return;
        
        selectedTrackIndex = index;
        
        for (int i = 0; i < strips.size(); ++i)
        {
            strips[i]->setSelected(i == selectedTrackIndex);
        }
        
        if (onTrackSelected)
            onTrackSelected(selectedTrackIndex);
    }

    void MixerComponent::bindToProject(Project::ProjectState& state)
    {
        if (projectState)
            projectState->getState().removeListener(this);
            
        projectState = &state;
        projectState->getState().addListener(this);
        
        // Re-bind existing strips
        for (int i = 0; i < strips.size(); ++i)
        {
            auto* strip = strips[i];
            
            strip->getVolumeSlider().onValueChange = [this, i, strip]() {
                projectState->setTrackVolume(i, (float)strip->getVolumeSlider().getValue());
            };
            
            strip->getPanSlider().onValueChange = [this, i, strip]() {
                projectState->setTrackPan(i, (float)strip->getPanSlider().getValue());
            };
            
            strip->getMuteButton().onClick = [this, i, strip]() {
                projectState->setTrackMute(i, strip->getMuteButton().getToggleState());
            };
            
            strip->getSoloButton().onClick = [this, i, strip]() {
                projectState->setTrackSolo(i, strip->getSoloButton().getToggleState());
            };
            
            updateStripFromState(i);
        }
    }

    void MixerComponent::updateStripFromState(int index)
    {
        if (!projectState || index < 0 || index >= strips.size()) return;
        
        auto trackNode = projectState->getTrackNode(index);
        if (trackNode.isValid())
        {
            auto* strip = strips[index];
            
            // Update UI without triggering callbacks
            juce::ScopedValueSetter<std::function<void()>> volGuard(strip->getVolumeSlider().onValueChange, nullptr);
            strip->getVolumeSlider().setValue(trackNode.getProperty(Project::IDs::volume, 1.0f));
            
            juce::ScopedValueSetter<std::function<void()>> panGuard(strip->getPanSlider().onValueChange, nullptr);
            strip->getPanSlider().setValue(trackNode.getProperty(Project::IDs::pan, 0.0f));
            
            juce::ScopedValueSetter<std::function<void()>> muteGuard(strip->getMuteButton().onClick, nullptr);
            strip->getMuteButton().setToggleState(trackNode.getProperty(Project::IDs::mute, false), juce::dontSendNotification);
            
            juce::ScopedValueSetter<std::function<void()>> soloGuard(strip->getSoloButton().onClick, nullptr);
            strip->getSoloButton().setToggleState(trackNode.getProperty(Project::IDs::solo, false), juce::dontSendNotification);
            
            strip->setName(trackNode.getProperty(Project::IDs::name));
        }
    }

    // ProjectState::Listener overrides
    void MixerComponent::valueTreePropertyChanged(juce::ValueTree& treeWhosePropertyHasChanged, const juce::Identifier& property)
    {
        if (treeWhosePropertyHasChanged.hasType(Project::IDs::TRACK))
        {
            int index = treeWhosePropertyHasChanged.getProperty(Project::IDs::index);
            
            // We need to update on the message thread
            juce::MessageManager::callAsync([this, index]() {
                updateStripFromState(index);
            });
        }
    }

    void MixerComponent::valueTreeChildAdded(juce::ValueTree& parentTree, juce::ValueTree& childWhichHasBeenAdded) {}
    void MixerComponent::valueTreeChildRemoved(juce::ValueTree& parentTree, juce::ValueTree& childWhichHasBeenRemoved, int indexFromWhichChildWasRemoved) {}
    void MixerComponent::valueTreeChildOrderChanged(juce::ValueTree& parentTreeWhichHasChanged, int oldIndex, int newIndex) {}
    void MixerComponent::valueTreeParentChanged(juce::ValueTree& treeWhoseParentHasChanged) {}
}

