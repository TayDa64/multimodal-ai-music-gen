/*
  ==============================================================================

    PythonManager.cpp
    
    Implementation of Python backend process manager.

  ==============================================================================
*/

#include "PythonManager.h"
#include "../Application/AppConfig.h"

//==============================================================================
PythonManager::PythonManager()
{
}

PythonManager::~PythonManager()
{
    stopServer();
}

//==============================================================================
bool PythonManager::startServer(const juce::String& pythonPath,
                                const juce::String& scriptPath,
                                int port,
                                bool verbose)
{
    // Stop any existing server
    stopServer();
    
    // Find Python
    auto python = pythonPath.isEmpty() ? findPython() : pythonPath;
    if (python.isEmpty())
    {
        DBG("PythonManager: Python not found");
        return false;
    }
    
    // Find main.py
    auto mainScript = scriptPath.isEmpty() ? findMainScript() : juce::File(scriptPath);
    if (!mainScript.existsAsFile())
    {
        DBG("PythonManager: main.py not found at " << mainScript.getFullPathName());
        return false;
    }
    
    // Build command line
    juce::StringArray args;
    args.add(python);
    args.add(mainScript.getFullPathName());
    args.add("--server");
    args.add("--port");
    args.add(juce::String(port));
    args.add("--no-signals");  // For embedded use
    
    if (verbose)
        args.add("--verbose");
    
    DBG("PythonManager: Starting server with command:");
    DBG("  " << args.joinIntoString(" "));
    
    // Start process
    process = std::make_unique<juce::ChildProcess>();
    
    if (!process->start(args))
    {
        DBG("PythonManager: Failed to start process");
        process = nullptr;
        return false;
    }
    
    serverPort = port;
    
    // Wait a moment for server to initialize
    juce::Thread::sleep(500);
    
    if (!process->isRunning())
    {
        // Process died immediately
        auto output = process->readAllProcessOutput();
        DBG("PythonManager: Process died. Output: " << output);
        process = nullptr;
        return false;
    }
    
    DBG("PythonManager: Server started successfully");
    return true;
}

void PythonManager::stopServer()
{
    if (process)
    {
        DBG("PythonManager: Stopping server...");
        
        // Try graceful shutdown first
        process->kill();
        
        // Wait for termination
        for (int i = 0; i < 50 && process->isRunning(); ++i)
            juce::Thread::sleep(100);
        
        process = nullptr;
        serverPort = 0;
        
        DBG("PythonManager: Server stopped");
    }
}

bool PythonManager::isRunning() const
{
    return process && process->isRunning();
}

int PythonManager::getProcessId() const
{
    // ChildProcess doesn't expose PID directly
    return 0;
}

//==============================================================================
juce::String PythonManager::findPython()
{
    // Common Python executable names
    juce::StringArray pythonNames = {
        "python",
        "python3",
        "python.exe",
        "python3.exe"
    };
    
    // Try to find Python in PATH
    for (const auto& name : pythonNames)
    {
        juce::ChildProcess test;
        if (test.start(name + " --version"))
        {
            test.waitForProcessToFinish(2000);
            auto output = test.readAllProcessOutput();
            if (output.containsIgnoreCase("python"))
            {
                DBG("PythonManager: Found Python: " << name);
                return name;
            }
        }
    }
    
    // Check common installation paths on Windows
    #if JUCE_WINDOWS
    juce::StringArray windowsPaths = {
        "C:\\Python313\\python.exe",
        "C:\\Python312\\python.exe",
        "C:\\Python311\\python.exe",
        "C:\\Python310\\python.exe",
        juce::File::getSpecialLocation(juce::File::userHomeDirectory)
            .getChildFile("AppData\\Local\\Programs\\Python\\Python313\\python.exe").getFullPathName(),
        juce::File::getSpecialLocation(juce::File::userHomeDirectory)
            .getChildFile("AppData\\Local\\Programs\\Python\\Python312\\python.exe").getFullPathName(),
    };
    
    for (const auto& path : windowsPaths)
    {
        if (juce::File(path).existsAsFile())
        {
            DBG("PythonManager: Found Python at: " << path);
            return path;
        }
    }
    #endif
    
    return {};
}

juce::File PythonManager::findMainScript()
{
    // Look relative to executable
    auto exeDir = juce::File::getSpecialLocation(juce::File::currentExecutableFile).getParentDirectory();
    
    // Try various relative paths
    juce::Array<juce::File> searchPaths = {
        exeDir.getChildFile("main.py"),
        exeDir.getParentDirectory().getChildFile("main.py"),
        exeDir.getParentDirectory().getParentDirectory().getChildFile("main.py"),
        exeDir.getParentDirectory().getParentDirectory().getParentDirectory().getChildFile("main.py"),
    };
    
    for (const auto& path : searchPaths)
    {
        if (path.existsAsFile())
        {
            DBG("PythonManager: Found main.py at: " << path.getFullPathName());
            return path;
        }
    }
    
    // Not found
    return {};
}
