/*
  ==============================================================================

    PythonManager.h
    
    Manages the Python backend process.

  ==============================================================================
*/

#pragma once

#include <JuceHeader.h>

//==============================================================================
/**
    Manages the Python backend server process.
    
    Can automatically start and stop the Python server.
*/
class PythonManager
{
public:
    //==============================================================================
    PythonManager();
    ~PythonManager();
    
    //==============================================================================
    /**
        Start the Python server.
        
        @param pythonPath   Path to Python executable (auto-detect if empty)
        @param scriptPath   Path to main.py
        @param port         Server port
        @param verbose      Enable verbose output
        @return             True if server started successfully
    */
    bool startServer(const juce::String& pythonPath = {},
                    const juce::String& scriptPath = {},
                    int port = 9000,
                    bool verbose = true);
    
    /**
        Stop the Python server.
    */
    void stopServer();
    
    /**
        Check if server is running.
    */
    bool isRunning() const;
    
    /**
        Get process ID of running server.
    */
    int getProcessId() const;
    
    //==============================================================================
    /**
        Find Python executable on the system.
    */
    static juce::String findPython();
    
    /**
        Find the main.py script relative to the executable.
    */
    static juce::File findMainScript();

private:
    //==============================================================================
    std::unique_ptr<juce::ChildProcess> process;
    int serverPort = 0;
    
    JUCE_DECLARE_NON_COPYABLE_WITH_LEAK_DETECTOR(PythonManager)
};
