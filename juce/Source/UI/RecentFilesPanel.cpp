/*
  ==============================================================================

    RecentFilesPanel.cpp
    
    Implementation of the recent files browser panel.

  ==============================================================================
*/

#include "RecentFilesPanel.h"
#include "Theme/ColourScheme.h"

//==============================================================================
// FileListBox implementation
//==============================================================================
RecentFilesPanel::FileListBox::FileListBox(RecentFilesPanel& o)
    : juce::ListBox({}, this), owner(o)
{
    setRowHeight(60);
    setColour(juce::ListBox::backgroundColourId, juce::Colours::transparentBlack);
    setColour(juce::ListBox::outlineColourId, juce::Colours::transparentBlack);
}

int RecentFilesPanel::FileListBox::getNumRows()
{
    return owner.files.size();
}

void RecentFilesPanel::FileListBox::paintListBoxItem(int rowNumber, juce::Graphics& g,
                                                     int width, int height, bool rowIsSelected)
{
    if (rowNumber < 0 || rowNumber >= owner.files.size())
        return;
    
    const auto& info = owner.files[rowNumber];
    auto bounds = juce::Rectangle<int>(0, 0, width, height);
    
    // Background
    if (rowIsSelected)
    {
        g.setColour(AppColours::primary.withAlpha(0.2f));
        g.fillRoundedRectangle(bounds.reduced(2).toFloat(), 6.0f);
    }
    else if (rowNumber == owner.selectedRow)
    {
        g.setColour(AppColours::surface.brighter(0.1f));
        g.fillRoundedRectangle(bounds.reduced(2).toFloat(), 6.0f);
    }
    
    bounds = bounds.reduced(8, 4);
    
    // Left side - Icon based on genre
    auto iconArea = bounds.removeFromLeft(44);
    g.setColour(AppColours::primary.withAlpha(0.8f));
    g.fillRoundedRectangle(iconArea.reduced(4).toFloat(), 8.0f);
    
    // Genre abbreviation as icon
    g.setColour(AppColours::textPrimary);
    g.setFont(juce::Font(12.0f, juce::Font::bold));
    juce::String genreAbbrev = info.genre.substring(0, 2).toUpperCase();
    if (genreAbbrev.isEmpty()) genreAbbrev = "??";
    g.drawText(genreAbbrev, iconArea, juce::Justification::centred);
    
    bounds.removeFromLeft(8);
    
    // Right side - Date/size
    auto rightArea = bounds.removeFromRight(80);
    g.setColour(AppColours::textSecondary);
    g.setFont(juce::Font(11.0f));
    g.drawText(info.dateString, rightArea.removeFromTop(rightArea.getHeight() / 2), 
               juce::Justification::centredRight);
    g.drawText(info.sizeString, rightArea, juce::Justification::centredRight);
    
    bounds.removeFromRight(8);
    
    // Main content - Name and details
    auto nameArea = bounds.removeFromTop(24);
    g.setColour(AppColours::textPrimary);
    g.setFont(juce::Font(14.0f, juce::Font::bold));
    g.drawText(info.displayName, nameArea, juce::Justification::centredLeft, true);
    
    // Details line (BPM, Key)
    g.setColour(AppColours::textSecondary);
    g.setFont(juce::Font(12.0f));
    juce::String details;
    if (info.bpm > 0)
        details += juce::String(info.bpm) + " BPM";
    if (info.key.isNotEmpty())
    {
        if (details.isNotEmpty()) details += "  •  ";
        details += info.key;
    }
    g.drawText(details, bounds, juce::Justification::centredLeft);
}

void RecentFilesPanel::FileListBox::listBoxItemClicked(int row, const juce::MouseEvent&)
{
    DBG("RecentFilesPanel: Single-click on row " << row);
    owner.selectedRow = row;
    repaint();
    
    // Load file on single click for immediate feedback
    owner.loadSelectedFile();
}

void RecentFilesPanel::FileListBox::listBoxItemDoubleClicked(int row, const juce::MouseEvent&)
{
    if (row >= 0 && row < owner.files.size())
    {
        owner.selectedRow = row;
        owner.loadSelectedFile();
    }
}

juce::String RecentFilesPanel::FileListBox::getTooltipForRow(int row)
{
    if (row >= 0 && row < owner.files.size())
        return owner.files[row].file.getFullPathName();
    return {};
}

//==============================================================================
// RecentFilesPanel implementation
//==============================================================================
RecentFilesPanel::RecentFilesPanel(AppState& state, mmg::AudioEngine& engine)
    : appState(state),
      audioEngine(engine)
{
    // Title
    titleLabel.setFont(juce::Font(16.0f, juce::Font::bold));
    titleLabel.setColour(juce::Label::textColourId, AppColours::textPrimary);
    addAndMakeVisible(titleLabel);
    
    // Refresh button
    refreshButton.setColour(juce::TextButton::buttonColourId, juce::Colours::transparentBlack);
    refreshButton.setColour(juce::TextButton::textColourOffId, AppColours::textSecondary);
    refreshButton.setTooltip("Refresh file list");
    refreshButton.onClick = [this] { refresh(); };
    addAndMakeVisible(refreshButton);
    
    // Open folder button
    openFolderButton.setColour(juce::TextButton::buttonColourId, juce::Colours::transparentBlack);
    openFolderButton.setColour(juce::TextButton::textColourOffId, AppColours::textSecondary);
    openFolderButton.setTooltip("Open output folder");
    openFolderButton.onClick = [this] {
        if (outputDirectory.isDirectory())
            outputDirectory.startAsProcess();
    };
    addAndMakeVisible(openFolderButton);
    
    // File list
    fileList = std::make_unique<FileListBox>(*this);
    addAndMakeVisible(*fileList);
    
    // Empty state label
    emptyLabel.setFont(juce::Font(14.0f));
    emptyLabel.setColour(juce::Label::textColourId, AppColours::textSecondary);
    emptyLabel.setJustificationType(juce::Justification::centred);
    addChildComponent(emptyLabel);
    
    // Default output directory - relative to app
    auto appDir = juce::File::getSpecialLocation(juce::File::currentExecutableFile).getParentDirectory();
    // Navigate up from build folder to find output
    auto possibleOutputDir = appDir.getParentDirectory().getParentDirectory()
                                   .getParentDirectory().getParentDirectory()
                                   .getChildFile("output");
    
    if (possibleOutputDir.isDirectory())
        setOutputDirectory(possibleOutputDir);
    
    // Start auto-refresh timer (every 5 seconds)
    startTimerHz(1); // Check every second, but only scan if directory modified
}

RecentFilesPanel::~RecentFilesPanel()
{
    stopTimer();
}

//==============================================================================
void RecentFilesPanel::paint(juce::Graphics& g)
{
    // Background
    g.setColour(AppColours::surface);
    g.fillRoundedRectangle(getLocalBounds().toFloat(), 8.0f);
    
    // Border
    g.setColour(AppColours::border);
    g.drawRoundedRectangle(getLocalBounds().toFloat().reduced(0.5f), 8.0f, 1.0f);
}

void RecentFilesPanel::resized()
{
    auto bounds = getLocalBounds().reduced(12);
    
    // Header row
    auto headerRow = bounds.removeFromTop(28);
    titleLabel.setBounds(headerRow.removeFromLeft(150));
    
    openFolderButton.setBounds(headerRow.removeFromRight(32).withHeight(24));
    refreshButton.setBounds(headerRow.removeFromRight(32).withHeight(24));
    
    bounds.removeFromTop(8);
    
    // File list fills remaining space
    fileList->setBounds(bounds);
    emptyLabel.setBounds(bounds);
    
    // Show/hide empty state
    bool hasFiles = !files.isEmpty();
    fileList->setVisible(hasFiles);
    emptyLabel.setVisible(!hasFiles);
}

//==============================================================================
void RecentFilesPanel::setOutputDirectory(const juce::File& directory)
{
    if (directory.isDirectory())
    {
        outputDirectory = directory;
        scanDirectory();
    }
}

void RecentFilesPanel::refresh()
{
    scanDirectory();
}

void RecentFilesPanel::scanDirectory()
{
    if (!outputDirectory.isDirectory())
        return;
    
    files.clear();
    
    // Find all MIDI files
    auto midiFiles = outputDirectory.findChildFiles(
        juce::File::findFiles, false, "*.mid;*.midi");
    
    // Sort by date (newest first)
    midiFiles.sort();
    std::sort(midiFiles.begin(), midiFiles.end(), 
              [](const juce::File& a, const juce::File& b) {
                  return a.getLastModificationTime() > b.getLastModificationTime();
              });
    
    // Limit to most recent 50 files
    int maxFiles = juce::jmin(50, midiFiles.size());
    
    for (int i = 0; i < maxFiles; ++i)
    {
        files.add(parseFileInfo(midiFiles[i]));
    }
    
    lastScanTime = juce::Time::getCurrentTime();
    
    if (fileList)
    {
        fileList->updateContent();
        fileList->repaint();
    }
    
    // Update empty state visibility
    bool hasFiles = !files.isEmpty();
    fileList->setVisible(hasFiles);
    emptyLabel.setVisible(!hasFiles);
}

RecentFilesPanel::FileInfo RecentFilesPanel::parseFileInfo(const juce::File& file)
{
    FileInfo info;
    info.file = file;
    info.lastModified = file.getLastModificationTime();
    info.dateString = formatRelativeDate(info.lastModified);
    info.sizeString = formatFileSize(file.getSize());
    
    // Parse filename: genre_bpm_key_timestamp.mid
    // Example: trap_soul_92.0bpm_Gminor_20251209_125555.mid
    auto nameWithoutExt = file.getFileNameWithoutExtension();
    auto parts = juce::StringArray::fromTokens(nameWithoutExt, "_", "");
    
    if (parts.size() >= 1)
    {
        // First part(s) are genre
        juce::String genreParts;
        int i = 0;
        while (i < parts.size() && !parts[i].containsAnyOf("0123456789"))
        {
            if (genreParts.isNotEmpty()) genreParts += " ";
            genreParts += parts[i];
            ++i;
        }
        info.genre = genreParts.isEmpty() ? "Unknown" : genreParts;
        
        // Look for BPM (contains "bpm")
        for (const auto& part : parts)
        {
            if (part.containsIgnoreCase("bpm"))
            {
                info.bpm = part.getIntValue();
            }
            // Look for key (contains "major" or "minor")
            else if (part.containsIgnoreCase("major") || part.containsIgnoreCase("minor"))
            {
                // Convert "Cminor" to "C minor", "Csharpminor" to "C# minor"
                juce::String keyStr = part;
                keyStr = keyStr.replace("sharp", "#");
                keyStr = keyStr.replace("minor", " minor");
                keyStr = keyStr.replace("major", " major");
                info.key = keyStr;
            }
        }
    }
    
    // Create display name
    info.displayName = info.genre;
    if (info.displayName.length() > 0)
        info.displayName = info.displayName.substring(0, 1).toUpperCase() 
                         + info.displayName.substring(1);
    
    return info;
}

juce::String RecentFilesPanel::formatRelativeDate(const juce::Time& time)
{
    auto now = juce::Time::getCurrentTime();
    auto diff = juce::RelativeTime(now.toMilliseconds() - time.toMilliseconds());
    
    if (diff.inDays() < 1)
    {
        if (diff.inHours() < 1)
        {
            int mins = (int)diff.inMinutes();
            if (mins < 1) return "Just now";
            return juce::String(mins) + " min ago";
        }
        int hours = (int)diff.inHours();
        return juce::String(hours) + " hr ago";
    }
    else if (diff.inDays() < 2)
    {
        return "Yesterday";
    }
    else if (diff.inDays() < 7)
    {
        return juce::String((int)diff.inDays()) + " days ago";
    }
    else
    {
        return time.toString(false, false, false, true); // "Dec 9, 2025"
    }
}

juce::String RecentFilesPanel::formatFileSize(juce::int64 bytes)
{
    if (bytes < 1024)
        return juce::String(bytes) + " B";
    else if (bytes < 1024 * 1024)
        return juce::String(bytes / 1024) + " KB";
    else
        return juce::String::formatted("%.1f MB", (double)bytes / (1024.0 * 1024.0));
}

void RecentFilesPanel::loadSelectedFile()
{
    DBG("RecentFilesPanel::loadSelectedFile - selectedRow=" << selectedRow);
    
    if (selectedRow >= 0 && selectedRow < files.size())
    {
        auto& info = files[selectedRow];
        DBG("  Loading file: " << info.file.getFullPathName());
        
        bool loaded = audioEngine.loadMidiFile(info.file);
        DBG("  AudioEngine load result: " << (loaded ? "SUCCESS" : "FAILED"));
        
        // Always notify listeners so piano roll can load the file directly too
        listeners.call(&Listener::fileSelected, info.file);
        DBG("  Notified listeners");
        
        // Update app state with BPM if parsed
        if (info.bpm > 0)
            appState.setBPM(info.bpm);
    }
    else
    {
        DBG("  Invalid selectedRow or files empty");
    }
}

//==============================================================================
void RecentFilesPanel::timerCallback()
{
    // Check if directory has been modified
    if (outputDirectory.isDirectory())
    {
        auto dirModTime = outputDirectory.getLastModificationTime();
        if (dirModTime > lastScanTime)
        {
            scanDirectory();
        }
    }
}

//==============================================================================
void RecentFilesPanel::addListener(Listener* listener)
{
    listeners.add(listener);
}

void RecentFilesPanel::removeListener(Listener* listener)
{
    listeners.remove(listener);
}
