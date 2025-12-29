/*
  ==============================================================================

    PythonManager.cpp
    
    Implementation of Python backend process manager.

  ==============================================================================
*/

#include "PythonManager.h"
#include "../Application/AppConfig.h"

#if JUCE_WINDOWS
#include <windows.h>
#include <shellapi.h>
#endif

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
    
    // Log file for debugging
    auto exeDir = juce::File::getSpecialLocation(juce::File::currentExecutableFile).getParentDirectory();
    auto logFile = exeDir.getChildFile("python_server.log");
    logFile.replaceWithText("PythonManager starting...\\n");
    
    // Find project root (4 levels up from Release folder)
    auto projectRoot = exeDir.getParentDirectory()
                            .getParentDirectory()
                            .getParentDirectory()
                            .getParentDirectory();
    
    logFile.appendText("Project root: " + projectRoot.getFullPathName() + "\\n");
    
    // Find Python (.venv first)
    auto python = pythonPath.isEmpty() ? findPython() : pythonPath;
    if (python.isEmpty())
    {
        DBG("PythonManager: Python not found");
        logFile.appendText("ERROR: Python not found\\n");
        return false;
    }
    logFile.appendText("Found Python: " + python + "\\n");
    
    // Find main.py
    auto mainScript = scriptPath.isEmpty() ? findMainScript() : juce::File(scriptPath);
    if (!mainScript.existsAsFile())
    {
        DBG("PythonManager: main.py not found");
        logFile.appendText("ERROR: main.py not found\\n");
        return false;
    }
    logFile.appendText("Found main.py: " + mainScript.getFullPathName() + "\\n");
    
    // Use Windows ShellExecute to run Python with proper path handling
    #if JUCE_WINDOWS
    {
        // Build argument string
        juce::String arguments = "\"" + mainScript.getFullPathName() + "\"";
        arguments += " --server --port " + juce::String(port);
        arguments += " --no-signals --no-banner";
        if (verbose)
            arguments += " --verbose";
        
        logFile.appendText("Launching with ShellExecute...\\n");
        logFile.appendText("Python: " + python + "\\n");
        logFile.appendText("Arguments: " + arguments + "\\n");
        
        // Use ShellExecuteW for proper Unicode/space handling
        HINSTANCE result = ShellExecuteW(
            NULL,
            L"open",
            python.toWideCharPointer(),
            arguments.toWideCharPointer(),
            projectRoot.getFullPathName().toWideCharPointer(),  // Working directory
            SW_HIDE  // Hide the window
        );
        
        if ((intptr_t)result > 32)
        {
            serverPort = port;
            juce::Thread::sleep(1500);  // Wait for server to start
            logFile.appendText("ShellExecute succeeded (result: " + juce::String((intptr_t)result) + ")\\n");
            
            // We can't track the process directly with ShellExecute
            // Mark as running - OSC bridge will handle connection
            return true;
        }
        else
        {
            logFile.appendText("ERROR: ShellExecute failed with code: " + juce::String((intptr_t)result) + "\\n");
        }
    }
    #endif
    
    // Fallback for non-Windows or if ShellExecute fails
    logFile.appendText("Trying ChildProcess fallback...\\n");
    
    juce::StringArray args;
    args.add(python);
    args.add(mainScript.getFullPathName());
    args.add("--server");
    args.add("--port");
    args.add(juce::String(port));
    args.add("--no-signals");
    args.add("--no-banner");
    if (verbose)
        args.add("--verbose");
    
    process = std::make_unique<juce::ChildProcess>();
    
    if (!process->start(args))
    {
        DBG("PythonManager: Failed to start process");
        logFile.appendText("ERROR: ChildProcess failed to start\\n");
        process = nullptr;
        return false;
    }
    
    serverPort = port;
    juce::Thread::sleep(1000);
    
    if (!process->isRunning())
    {
        auto output = process->readAllProcessOutput();
        logFile.appendText("ERROR: Process died. Output: " + output + "\\n");
        process = nullptr;
        return false;
    }
    
    logFile.appendText("Server started successfully\\n");
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
    // First, check for .venv in project directory (preferred)
    auto exeDir = juce::File::getSpecialLocation(juce::File::currentExecutableFile).getParentDirectory();
    auto projectRoot = exeDir.getParentDirectory()  // MultimodalMusicGen_artefacts
                            .getParentDirectory()   // build
                            .getParentDirectory()   // juce
                            .getParentDirectory();  // project root
    
    // Check for .venv first (Windows)
    #if JUCE_WINDOWS
    auto venvPython = projectRoot.getChildFile(".venv").getChildFile("Scripts").getChildFile("python.exe");
    if (venvPython.existsAsFile())
    {
        DBG("PythonManager: Found venv Python at: " << venvPython.getFullPathName());
        return venvPython.getFullPathName();
    }
    #else
    auto venvPython = projectRoot.getChildFile(".venv").getChildFile("bin").getChildFile("python");
    if (venvPython.existsAsFile())
    {
        DBG("PythonManager: Found venv Python at: " << venvPython.getFullPathName());
        return venvPython.getFullPathName();
    }
    #endif
    
    // Fall back to system Python
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
    
    // Executable is in: juce/build/MultimodalMusicGen_artefacts/Release/
    // main.py is in: project root (4 levels up from Release)
    auto projectRoot = exeDir.getParentDirectory()  // MultimodalMusicGen_artefacts
                            .getParentDirectory()   // build
                            .getParentDirectory()   // juce
                            .getParentDirectory();  // project root
    
    // Try various paths in priority order
    juce::Array<juce::File> searchPaths = {
        // Most likely: project root (where main.py lives)
        projectRoot.getChildFile("main.py"),
        // Development paths
        exeDir.getChildFile("main.py"),
        exeDir.getParentDirectory().getChildFile("main.py"),
        exeDir.getParentDirectory().getParentDirectory().getChildFile("main.py"),
        exeDir.getParentDirectory().getParentDirectory().getParentDirectory().getChildFile("main.py"),
        // Additional fallback: 5 levels up
        exeDir.getParentDirectory().getParentDirectory().getParentDirectory().getParentDirectory().getChildFile("main.py"),
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
