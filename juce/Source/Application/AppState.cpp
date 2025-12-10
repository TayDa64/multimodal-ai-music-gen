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
    currentProjectFile = juce::File();
    currentGeneration = GenerationState();
    unsavedChanges = false;
}

bool AppState::loadProject(const juce::File& file)
{
    if (!file.existsAsFile())
        return false;
    
    auto json = juce::JSON::parse(file);
    if (!json.isObject())
        return false;
    
    auto* obj = json.getDynamicObject();
    if (!obj)
        return false;
    
    currentGeneration.prompt = obj->getProperty("prompt").toString();
    currentGeneration.bpm = obj->getProperty("bpm");
    currentGeneration.key = obj->getProperty("key").toString();
    currentGeneration.genre = obj->getProperty("genre").toString();
    
    if (auto midiPath = obj->getProperty("midiPath").toString(); midiPath.isNotEmpty())
        currentGeneration.midiFile = file.getParentDirectory().getChildFile(midiPath);
    
    if (auto audioPath = obj->getProperty("audioPath").toString(); audioPath.isNotEmpty())
        currentGeneration.audioFile = file.getParentDirectory().getChildFile(audioPath);
    
    currentProjectFile = file;
    unsavedChanges = false;
    addRecentFile(file);
    
    return true;
}

bool AppState::saveProject()
{
    if (currentProjectFile == juce::File())
        return false;
    
    return saveProjectAs(currentProjectFile);
}

bool AppState::saveProjectAs(const juce::File& file)
{
    juce::DynamicObject::Ptr obj = new juce::DynamicObject();
    
    obj->setProperty("version", AppConfig::versionString);
    obj->setProperty("prompt", currentGeneration.prompt);
    obj->setProperty("bpm", currentGeneration.bpm);
    obj->setProperty("key", currentGeneration.key);
    obj->setProperty("genre", currentGeneration.genre);
    
    if (currentGeneration.midiFile.existsAsFile())
        obj->setProperty("midiPath", currentGeneration.midiFile.getRelativePathFrom(file.getParentDirectory()));
    
    if (currentGeneration.audioFile.existsAsFile())
        obj->setProperty("audioPath", currentGeneration.audioFile.getRelativePathFrom(file.getParentDirectory()));
    
    auto json = juce::JSON::toString(juce::var(obj.get()), true);
    
    if (!file.replaceWithText(json))
        return false;
    
    currentProjectFile = file;
    unsavedChanges = false;
    addRecentFile(file);
    
    return true;
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
