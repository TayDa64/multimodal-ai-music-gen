/*
  ==============================================================================

    Multimodal AI Music Generator
    Main Application Entry Point
    
    This file initializes the JUCE application and creates the main window.

  ==============================================================================
*/

#include <JuceHeader.h>
#include "MainComponent.h"
#include "Application/AppState.h"
#include "UI/Theme/AppLookAndFeel.h"

//==============================================================================
/**
    Main application class for the AI Music Generator.
    
    Handles application lifecycle:
    - Startup and shutdown
    - Window management
    - Global state management
*/
class MultimodalMusicGenApplication : public juce::JUCEApplication
{
public:
    //==============================================================================
    MultimodalMusicGenApplication() {}

    //==============================================================================
    const juce::String getApplicationName() override       
    { 
        return ProjectInfo::projectName; 
    }
    
    const juce::String getApplicationVersion() override    
    { 
        return ProjectInfo::versionString; 
    }
    
    bool moreThanOneInstanceAllowed() override             
    { 
        return false; 
    }

    //==============================================================================
    void initialise(const juce::String& commandLine) override
    {
        juce::ignoreUnused(commandLine);
        
        // Initialize custom look and feel
        lookAndFeel = std::make_unique<AppLookAndFeel>();
        juce::LookAndFeel::setDefaultLookAndFeel(lookAndFeel.get());
        
        // Initialize application state
        appState = std::make_unique<AppState>();
        
        // Create main window
        mainWindow = std::make_unique<MainWindow>(getApplicationName(), *appState);
        
        DBG("=== AI Music Generator Started ===");
        DBG("Version: " << getApplicationVersion());
    }

    void shutdown() override
    {
        DBG("=== AI Music Generator Shutting Down ===");
        
        // Save application state
        if (appState)
            appState->saveSettings();
        
        // Clean up
        mainWindow = nullptr;
        appState = nullptr;
        
        // Reset look and feel
        juce::LookAndFeel::setDefaultLookAndFeel(nullptr);
        lookAndFeel = nullptr;
    }

    //==============================================================================
    void systemRequestedQuit() override
    {
        // Check for unsaved changes
        if (appState && appState->hasUnsavedChanges())
        {
            auto options = juce::MessageBoxOptions()
                .withIconType(juce::MessageBoxIconType::QuestionIcon)
                .withTitle("Unsaved Changes")
                .withMessage("You have unsaved changes. Do you want to save before quitting?")
                .withButton("Save")
                .withButton("Don't Save")
                .withButton("Cancel");
            
            juce::AlertWindow::showAsync(options, [this](int result)
            {
                if (result == 1) // Save
                {
                    appState->saveProject();
                    quit();
                }
                else if (result == 2) // Don't Save
                {
                    quit();
                }
                // Cancel - do nothing
            });
        }
        else
        {
            quit();
        }
    }

    void anotherInstanceStarted(const juce::String& commandLine) override
    {
        juce::ignoreUnused(commandLine);
        
        // Bring existing window to front
        if (mainWindow)
            mainWindow->toFront(true);
    }

    //==============================================================================
    /**
        Main application window.
        
        Manages the window frame and contains the MainComponent.
    */
    class MainWindow : public juce::DocumentWindow
    {
    public:
        MainWindow(juce::String name, AppState& state)
            : DocumentWindow(name,
                            juce::Desktop::getInstance().getDefaultLookAndFeel()
                                .findColour(juce::ResizableWindow::backgroundColourId),
                            DocumentWindow::allButtons),
              appState(state)
        {
            setUsingNativeTitleBar(true);
            setContentOwned(new MainComponent(appState), true);

            #if JUCE_IOS || JUCE_ANDROID
                setFullScreen(true);
            #else
                // Restore window bounds from saved state
                auto savedBounds = appState.getWindowBounds();
                if (savedBounds.isEmpty())
                {
                    // Default size: 1280x800, centered
                    setResizable(true, true);
                    centreWithSize(1280, 800);
                }
                else
                {
                    setBounds(savedBounds);
                }
                
                // Set minimum size
                setResizeLimits(800, 600, 4096, 4096);
            #endif

            setVisible(true);
        }

        void closeButtonPressed() override
        {
            // Save window bounds before closing
            appState.setWindowBounds(getBounds());
            
            JUCEApplication::getInstance()->systemRequestedQuit();
        }
        
        void moved() override
        {
            DocumentWindow::moved();
            appState.setWindowBounds(getBounds());
        }
        
        void resized() override
        {
            DocumentWindow::resized();
            appState.setWindowBounds(getBounds());
        }

    private:
        AppState& appState;
        
        JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(MainWindow)
    };

private:
    std::unique_ptr<MainWindow> mainWindow;
    std::unique_ptr<AppState> appState;
    std::unique_ptr<AppLookAndFeel> lookAndFeel;
};

//==============================================================================
// Application instantiation
START_JUCE_APPLICATION(MultimodalMusicGenApplication)
