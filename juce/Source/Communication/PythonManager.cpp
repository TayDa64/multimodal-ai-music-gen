/*
  ==============================================================================

    PythonManager.cpp
    
    Implementation of Python backend process manager.

  ==============================================================================
*/

#include "PythonManager.h"
#include "../Application/AppConfig.h"

#include <vector>

#if JUCE_WINDOWS
#include <windows.h>
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

    // Historically we launched `main.py`. The gateway uses `python -m multimodal_gen.server`
    // and does not require a `main.py` to exist. Keep this check best-effort for backward
    // compatibility/logging only.
    auto mainScript = scriptPath.isEmpty() ? findMainScript() : juce::File(scriptPath);
    if (mainScript.existsAsFile())
        logFile.appendText("Found main.py: " + mainScript.getFullPathName() + "\\n");
    else
        logFile.appendText("Note: main.py not found (ok when using -m multimodal_gen.server)\\n");
    
    // Use CreateProcessW so we can track/stop the process. (ShellExecuteW does not provide a PID.)
    #if JUCE_WINDOWS
    {
        // Build argument string (command line excluding exe)
        // Force UTF-8 mode so any backend logging won't crash due to Windows console codepages.
        juce::String arguments = "-X utf8 -m multimodal_gen.server";
        arguments += " --gateway --port " + juce::String(port);
        if (verbose)
            arguments += " --verbose";
        
        logFile.appendText("Launching with CreateProcessW...\\n");
        logFile.appendText("Python: " + python + "\\n");
        logFile.appendText("Arguments: " + arguments + "\\n");
        
        // Capture stdout/stderr to a log file so we can diagnose startup failures.
        auto backendLog = exeDir.getChildFile("python_backend.log");
        backendLog.deleteFile();

        SECURITY_ATTRIBUTES sa{};
        sa.nLength = sizeof(sa);
        sa.bInheritHandle = TRUE;

        HANDLE hLog = CreateFileW(
            backendLog.getFullPathName().toWideCharPointer(),
            FILE_APPEND_DATA,
            FILE_SHARE_READ | FILE_SHARE_WRITE,
            &sa,
            OPEN_ALWAYS,
            FILE_ATTRIBUTE_NORMAL,
            NULL
        );

        STARTUPINFOW si{};
        si.cb = sizeof(si);
        si.dwFlags = STARTF_USESHOWWINDOW | STARTF_USESTDHANDLES;
        si.wShowWindow = SW_HIDE;
        si.hStdOutput = hLog;
        si.hStdError = hLog;
        si.hStdInput = GetStdHandle(STD_INPUT_HANDLE);

        PROCESS_INFORMATION pi{};

        // CreateProcess requires a mutable, NUL-terminated command line buffer.
        const juce::String cmdLine = "\"" + python + "\" " + arguments;
        const std::wstring cmdWide(cmdLine.toWideCharPointer());
        std::vector<wchar_t> cmdMutable(cmdWide.begin(), cmdWide.end());
        cmdMutable.push_back(L'\0');

        const auto workingDir = projectRoot.getFullPathName();
        BOOL ok = CreateProcessW(
            /*lpApplicationName*/ nullptr,
            /*lpCommandLine*/ cmdMutable.data(),
            /*lpProcessAttributes*/ nullptr,
            /*lpThreadAttributes*/ nullptr,
            /*bInheritHandles*/ TRUE,
            /*dwCreationFlags*/ CREATE_NO_WINDOW,
            /*lpEnvironment*/ nullptr,
            /*lpCurrentDirectory*/ workingDir.toWideCharPointer(),
            /*lpStartupInfo*/ &si,
            /*lpProcessInformation*/ &pi
        );

        if (hLog != INVALID_HANDLE_VALUE && hLog != NULL)
            CloseHandle(hLog);

        if (ok)
        {
            // Close thread handle; we only need process handle.
            CloseHandle(pi.hThread);

            serverProcessHandle = pi.hProcess;
            serverPid = pi.dwProcessId;
            serverPort = port;

            logFile.appendText("CreateProcessW succeeded (pid: " + juce::String((int)serverPid) + ")\\n");
            juce::Thread::sleep(1500);  // Give the server a moment to bind ports
            return true;
        }

        const DWORD err = GetLastError();
        logFile.appendText("ERROR: CreateProcessW failed. GetLastError=" + juce::String((int)err) + "\\n");
    }
    #endif
    
    // Fallback for non-Windows or if ShellExecute fails
    logFile.appendText("Trying ChildProcess fallback...\\n");
    
    juce::StringArray args;
    args.add(python);
    args.add("-X");
    args.add("utf8");
    args.add("-m");
    args.add("multimodal_gen.server");
    args.add("--gateway");
    args.add("--port");
    args.add(juce::String(port));
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
    #if JUCE_WINDOWS
    if (serverProcessHandle != nullptr)
    {
        DBG("PythonManager: Stopping server (CreateProcessW)...");

        // Give it a chance to exit (MainComponent already tries OSC /shutdown).
        WaitForSingleObject(serverProcessHandle, 1500);

        DWORD exitCode = STILL_ACTIVE;
        if (GetExitCodeProcess(serverProcessHandle, &exitCode) && exitCode == STILL_ACTIVE)
        {
            TerminateProcess(serverProcessHandle, 0);
            WaitForSingleObject(serverProcessHandle, 2000);
        }

        CloseHandle(serverProcessHandle);
        serverProcessHandle = nullptr;
        serverPid = 0;
        serverPort = 0;
        return;
    }
    #endif

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
    #if JUCE_WINDOWS
    if (serverProcessHandle != nullptr)
    {
        DWORD exitCode = STILL_ACTIVE;
        if (GetExitCodeProcess(serverProcessHandle, &exitCode))
            return exitCode == STILL_ACTIVE;
    }
    #endif

    return process && process->isRunning();
}

int PythonManager::getProcessId() const
{
    #if JUCE_WINDOWS
    if (serverPid != 0)
        return (int)serverPid;
    #endif

    // juce::ChildProcess doesn't expose PID directly.
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
