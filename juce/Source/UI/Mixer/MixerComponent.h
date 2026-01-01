#pragma once

#include <juce_gui_basics/juce_gui_basics.h>
#include <juce_graphics/juce_graphics.h>
#include <juce_data_structures/juce_data_structures.h>
#include "ChannelStrip.h"
#include "../../Project/ProjectState.h"

namespace UI
{
    class MixerComponent : public juce::Component,
                           public Project::ProjectState::Listener
    {
    public:
        MixerComponent();
        ~MixerComponent() override;

        void paint(juce::Graphics& g) override;
        void resized() override;

        /**
         * Rebuild the mixer UI based on track list.
         */
        void setTracks(const juce::StringArray& trackNames);
        
        /**
         * Bind to project state for persistence and undo/redo.
         */
        void bindToProject(Project::ProjectState& state);

        // ProjectState::Listener overrides
        void valueTreePropertyChanged(juce::ValueTree& treeWhosePropertyHasChanged, const juce::Identifier& property) override;
        void valueTreeChildAdded(juce::ValueTree& parentTree, juce::ValueTree& childWhichHasBeenAdded) override;
        void valueTreeChildRemoved(juce::ValueTree& parentTree, juce::ValueTree& childWhichHasBeenRemoved, int indexFromWhichChildWasRemoved) override;
        void valueTreeChildOrderChanged(juce::ValueTree& parentTreeWhichHasChanged, int oldIndex, int newIndex) override;
        void valueTreeParentChanged(juce::ValueTree& treeWhoseParentHasChanged) override;

        int getSelectedTrackIndex() const { return selectedTrackIndex; }
        std::function<void(int)> onTrackSelected;

    private:
        juce::OwnedArray<ChannelStrip> strips;
        juce::Viewport viewport;
        juce::Component container;
        
        Project::ProjectState* projectState = nullptr;
        int selectedTrackIndex = 0;
        
        void updateStripFromState(int index);
        void selectTrack(int index);

        JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(MixerComponent)
    };
}
