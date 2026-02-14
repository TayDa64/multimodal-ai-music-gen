/*
  ==============================================================================

    AppState.cpp
    
    Implementation of application state management.

  ==============================================================================
*/

#include "AppState.h"
#include "AppConfig.h"

//==============================================================================
AppState::AppState()
{
    loadSettings();
}

AppState::~AppState()
{
    saveSettings();
}

//==============================================================================
juce::File AppState::getSettingsFile() const
{
    auto appDataDir = juce::File::getSpecialLocation(
        juce::File::userApplicationDataDirectory
    ).getChildFile(AppConfig::companyName)
     .getChildFile(AppConfig::appName);
    
    appDataDir.createDirectory();
    
    return appDataDir.getChildFile("settings.xml");
}

void AppState::loadSettings()
{
    juce::PropertiesFile::Options options;
    options.applicationName = AppConfig::appName;
    options.filenameSuffix = ".xml";
    options.folderName = AppConfig::companyName;
    options.osxLibrarySubFolder = "Application Support";
    
    settings = std::make_unique<juce::PropertiesFile>(getSettingsFile(), options);
}

void AppState::saveSettings()
{
    if (settings)
        settings->saveIfNeeded();
}

//==============================================================================
juce::Rectangle<int> AppState::getWindowBounds() const
{
    if (!settings)
        return {};
    
    return juce::Rectangle<int>(
        settings->getIntValue("windowX", 0),
        settings->getIntValue("windowY", 0),
        settings->getIntValue("windowWidth", 0),
        settings->getIntValue("windowHeight", 0)
    );
}

void AppState::setWindowBounds(const juce::Rectangle<int>& bounds)
{
    if (!settings)
        return;
    
    settings->setValue("windowX", bounds.getX());
    settings->setValue("windowY", bounds.getY());
    settings->setValue("windowWidth", bounds.getWidth());
    settings->setValue("windowHeight", bounds.getHeight());
}

//==============================================================================
void AppState::newProject()
{
    projectState.newProject();
    currentProjectFile = juce::File();
    currentGeneration = GenerationState();
    unsavedChanges = false;

    listeners.call(&Listener::onNewProjectCreated);
}

bool AppState::loadProject(const juce::File& file)
{
    if (!file.existsAsFile())
        return false;
    
    // Try loading with ProjectState (XML/ValueTree)
    if (projectState.loadProject(file))
    {
        auto projectDir = file.getParentDirectory();
        
        // Sync legacy state from ProjectState
        auto genNode = projectState.getState().getChildWithName(Project::IDs::GENERATION);
        if (genNode.isValid())
        {
            currentGeneration.prompt = genNode.getProperty(Project::IDs::prompt);
            currentGeneration.bpm = genNode.getProperty(Project::IDs::bpm);
            currentGeneration.key = genNode.getProperty(Project::IDs::key);
            currentGeneration.genre = genNode.getProperty(Project::IDs::genre);
            
            juce::String midiPath = genNode.getProperty(Project::IDs::midiPath);
            if (midiPath.isNotEmpty())
                currentGeneration.midiFile = projectDir.getChildFile(midiPath);
                
            juce::String audioPath = genNode.getProperty(Project::IDs::audioPath);
            if (audioPath.isNotEmpty())
                currentGeneration.audioFile = projectDir.getChildFile(audioPath);
        }
        
        // Resolve TRACK paths: relative → absolute
        auto mixerNode = projectState.getMixerNode();
        if (mixerNode.isValid())
        {
            for (auto child : mixerNode)
            {
                if (child.hasType(Project::IDs::TRACK))
                {
                    juce::String pathStr = child.getProperty(Project::IDs::path).toString();
                    if (pathStr.isNotEmpty() && !juce::File::isAbsolutePath(pathStr))
                    {
                        auto resolved = projectDir.getChildFile(pathStr);
                        child.setProperty(Project::IDs::path, resolved.getFullPathName(), nullptr);
                    }
                }
            }
        }
        
        // Resolve INSTRUMENT paths: relative → absolute
        auto instsNode = projectState.getInstrumentsNode();
        if (instsNode.isValid())
        {
            for (auto child : instsNode)
            {
                if (child.hasType(Project::IDs::INSTRUMENT))
                {
                    juce::String pathStr = child.getProperty(Project::IDs::path).toString();
                    if (pathStr.isNotEmpty() && !juce::File::isAbsolutePath(pathStr))
                    {
                        auto resolved = projectDir.getChildFile(pathStr);
                        child.setProperty(Project::IDs::path, resolved.getFullPathName(), nullptr);
                    }
                }
            }
        }
        
        currentProjectFile = file;
        unsavedChanges = false;
        addRecentFile(file);

        listeners.call(&Listener::onProjectLoaded, file);
        return true;
    }
    
    // Fallback to legacy JSON loading
    auto json = juce::JSON::parse(file);
    if (json.isObject())
    {
        auto* obj = json.getDynamicObject();
        if (obj)
        {
            currentGeneration.prompt = obj->getProperty("prompt").toString();
            currentGeneration.bpm = obj->getProperty("bpm");
            currentGeneration.key = obj->getProperty("key").toString();
            currentGeneration.genre = obj->getProperty("genre").toString();
            
            if (auto midiPath = obj->getProperty("midiPath").toString(); midiPath.isNotEmpty())
                currentGeneration.midiFile = file.getParentDirectory().getChildFile(midiPath);
            
            if (auto audioPath = obj->getProperty("audioPath").toString(); audioPath.isNotEmpty())
                currentGeneration.audioFile = file.getParentDirectory().getChildFile(audioPath);
            
            // Initialize ProjectState with loaded data
            projectState.newProject();
            projectState.setGenerationData(currentGeneration.prompt, currentGeneration.bpm, currentGeneration.key, currentGeneration.genre);
            
            currentProjectFile = file;
            unsavedChanges = false;
            addRecentFile(file);
            return true;
        }
    }
    
    return false;
}

bool AppState::saveProject()
{
    if (currentProjectFile == juce::File())
        return false;
    
    return saveProjectAs(currentProjectFile);
}

bool AppState::saveProjectAs(const juce::File& file)
{
    // Ensure ProjectState is up to date
    projectState.setGenerationData(currentGeneration.prompt, currentGeneration.bpm, currentGeneration.key, currentGeneration.genre);
    
    if (currentGeneration.midiFile.existsAsFile())
        projectState.setGeneratedFiles(
            currentGeneration.midiFile.getRelativePathFrom(file.getParentDirectory()),
            currentGeneration.audioFile.getRelativePathFrom(file.getParentDirectory())
        );
    
    // Convert TRACK and INSTRUMENT paths to relative before saving
    auto projectDir = file.getParentDirectory();
    
    auto mixerNode = projectState.getMixerNode();
    if (mixerNode.isValid())
    {
        for (auto child : mixerNode)
        {
            if (child.hasType(Project::IDs::TRACK))
            {
                juce::String absPath = child.getProperty(Project::IDs::path).toString();
                if (absPath.isNotEmpty() && juce::File::isAbsolutePath(absPath))
                {
                    auto relative = juce::File(absPath).getRelativePathFrom(projectDir);
                    child.setProperty(Project::IDs::path, relative, nullptr);
                }
            }
        }
    }
    
    auto instsNode = projectState.getInstrumentsNode();
    if (instsNode.isValid())
    {
        for (auto child : instsNode)
        {
            if (child.hasType(Project::IDs::INSTRUMENT))
            {
                juce::String absPath = child.getProperty(Project::IDs::path).toString();
                if (absPath.isNotEmpty() && juce::File::isAbsolutePath(absPath))
                {
                    auto relative = juce::File(absPath).getRelativePathFrom(projectDir);
                    child.setProperty(Project::IDs::path, relative, nullptr);
                }
            }
        }
    }

    if (projectState.saveProject(file))
    {
        currentProjectFile = file;
        unsavedChanges = false;
        addRecentFile(file);
        return true;
    }
    
    return false;
}

//==============================================================================
juce::StringArray AppState::getRecentFiles() const
{
    juce::StringArray files;
    
    if (settings)
    {
        auto recentStr = settings->getValue("recentFiles", "");
        files.addTokens(recentStr, ";", "");
        files.removeEmptyStrings();
    }
    
    return files;
}

void AppState::addRecentFile(const juce::File& file)
{
    if (!settings)
        return;
    
    auto files = getRecentFiles();
    files.removeString(file.getFullPathName());
    files.insert(0, file.getFullPathName());
    
    // Keep only last 10 files
    while (files.size() > 10)
        files.remove(files.size() - 1);
    
    settings->setValue("recentFiles", files.joinIntoString(";"));
}

void AppState::clearRecentFiles()
{
    if (settings)
        settings->setValue("recentFiles", "");
}

//==============================================================================
juce::String AppState::getLastInstrumentPath() const
{
    return settings ? settings->getValue("lastInstrumentPath", "") : "";
}

void AppState::setLastInstrumentPath(const juce::String& path)
{
    if (settings)
        settings->setValue("lastInstrumentPath", path);
}

juce::String AppState::getLastOutputPath() const
{
    return settings ? settings->getValue("lastOutputPath", "") : "";
}

void AppState::setLastOutputPath(const juce::String& path)
{
    if (settings)
        settings->setValue("lastOutputPath", path);
}

int AppState::getServerPort() const
{
    return settings ? settings->getIntValue("serverPort", 9000) : 9000;
}

void AppState::setServerPort(int port)
{
    if (settings)
        settings->setValue("serverPort", port);
}

//==============================================================================
// Generation parameter accessors
int AppState::getBPM() const
{
    return currentGeneration.bpm;
}

void AppState::setBPM(int newBPM)
{
    currentGeneration.bpm = newBPM;
    projectState.setGenerationData(currentGeneration.prompt, currentGeneration.bpm, currentGeneration.key, currentGeneration.genre);
    unsavedChanges = true;
}

juce::String AppState::getKey() const
{
    return currentGeneration.key;
}

void AppState::setKey(const juce::String& newKey)
{
    currentGeneration.key = newKey;
    projectState.setGenerationData(currentGeneration.prompt, currentGeneration.bpm, currentGeneration.key, currentGeneration.genre);
    unsavedChanges = true;
}

int AppState::getDurationBars() const
{
    return durationBars;
}

void AppState::setDurationBars(int bars)
{
    durationBars = bars;
    unsavedChanges = true;
}

int AppState::getNumTakes() const
{
    return numTakes;
}

void AppState::setNumTakes(int takes)
{
    numTakes = juce::jmax(1, takes);
    unsavedChanges = true;
}

juce::String AppState::getPrompt() const
{
    return currentGeneration.prompt;
}

void AppState::setPrompt(const juce::String& newPrompt)
{
    currentGeneration.prompt = newPrompt;
    projectState.setGenerationData(currentGeneration.prompt, currentGeneration.bpm, currentGeneration.key, currentGeneration.genre);
    unsavedChanges = true;
}

bool AppState::isGenerating() const
{
    return generating;
}

void AppState::setGenerating(bool isGenerating)
{
    generating = isGenerating;
    
    if (isGenerating)
    {
        listeners.call([](Listener& l) { l.onGenerationStarted(); });
    }
    else
    {
        listeners.call([](Listener& l) { l.onGenerationFinished(); });
    }
}

juce::File AppState::getOutputFile() const
{
    return currentGeneration.audioFile;
}

void AppState::setOutputFile(const juce::File& file)
{
    currentGeneration.audioFile = file;
    // We don't update projectState here because we might not have the midi file yet.
    // It's better to update both at once or handle it separately.
    // But let's try to keep it in sync if possible.
    // projectState.setGeneratedFiles(..., ...); 
    // We'll leave it for saveProjectAs to sync fully for now.
    unsavedChanges = true;
}

//==============================================================================
// Progress management
void AppState::setProgress(const GenerationProgress& progress)
{
    currentProgress = progress;
    listeners.call([&progress](Listener& l) { l.onProgressChanged(progress); });
}

GenerationProgress AppState::getProgress() const
{
    return currentProgress;
}

//==============================================================================
// Listener management
void AppState::addListener(Listener* listener)
{
    listeners.add(listener);
}

void AppState::removeListener(Listener* listener)
{
    listeners.remove(listener);
}

//==============================================================================
// Pending Reference Management
void AppState::setPendingReference(const juce::String& url, int bpm, const juce::String& key, const juce::String& genre)
{
    pendingReferenceUrl = url;
    lastAnalysisBpm = bpm;
    lastAnalysisKey = key;
    lastAnalysisGenre = genre;
}

void AppState::clearPendingReference()
{
    pendingReferenceUrl = "";
    lastAnalysisBpm = 0;
    lastAnalysisKey = "";
    lastAnalysisGenre = "";
}
