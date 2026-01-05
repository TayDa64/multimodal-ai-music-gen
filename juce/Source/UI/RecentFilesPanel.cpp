/*
  ==============================================================================

    RecentFilesPanel.cpp
    
    Implementation of the recent files browser panel with file management.

  ==============================================================================
*/

#include "RecentFilesPanel.h"
#include "Theme/ColourScheme.h"

//==============================================================================
// FileListBox implementation
//==============================================================================
RecentFilesPanel::FileListBox::FileListBox(RecentFilesPanel& o)
    : juce::ListBox({}, nullptr), owner(o)
{
    setModel(this);
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
    
    // Left side - Icon with genre abbreviation
    auto iconArea = bounds.removeFromLeft(44);
    g.setColour(AppColours::primary.withAlpha(0.8f));
    g.fillRoundedRectangle(iconArea.reduced(4).toFloat(), 8.0f);
    
    // Genre abbreviation as icon
    g.setColour(AppColours::textPrimary);
    g.setFont(juce::Font(11.0f, juce::Font::bold));
    juce::String genreAbbrev = info.genre.substring(0, 3).toUpperCase();
    if (genreAbbrev.isEmpty()) genreAbbrev = "???";
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

void RecentFilesPanel::FileListBox::listBoxItemClicked(int row, const juce::MouseEvent& e)
{
    DBG("RecentFilesPanel: Click on row " << row);
    owner.selectedRow = row;
    repaint();
    
    // Right-click shows context menu
    if (e.mods.isRightButtonDown() || e.mods.isPopupMenu())
    {
        owner.showContextMenu(row);
    }
    // Single left-click only selects, does NOT load
    // Loading happens on double-click for consistency
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
        return owner.files[row].file.getFullPathName() + "\n\nRight-click for options";
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
    openFolderButton.setTooltip("Open output folder in Explorer");
    openFolderButton.onClick = [this] { revealInExplorer(); };
    addAndMakeVisible(openFolderButton);
    
    // Delete button
    deleteButton.setColour(juce::TextButton::buttonColourId, juce::Colours::transparentBlack);
    deleteButton.setColour(juce::TextButton::textColourOffId, AppColours::error);
    deleteButton.setTooltip("Delete selected file");
    deleteButton.onClick = [this] { deleteSelectedFile(); };
    addAndMakeVisible(deleteButton);
    
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
    {
        setOutputDirectory(possibleOutputDir);
    }
    
    // Start auto-refresh timer (check every 2 seconds for new files)
    startTimer(2000);
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
    titleLabel.setBounds(headerRow.removeFromLeft(120));
    
    // Buttons on the right
    deleteButton.setBounds(headerRow.removeFromRight(32).withHeight(24));
    headerRow.removeFromRight(4);
    openFolderButton.setBounds(headerRow.removeFromRight(32).withHeight(24));
    headerRow.removeFromRight(4);
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
        DBG("RecentFilesPanel: Set output directory to " << directory.getFullPathName());
        scanDirectory();
    }
}

void RecentFilesPanel::refresh()
{
    DBG("RecentFilesPanel: Manual refresh triggered");
    scanDirectory();
}

void RecentFilesPanel::scanDirectory()
{
    if (!outputDirectory.isDirectory())
    {
        DBG("RecentFilesPanel: Output directory not set or invalid");
        return;
    }
    
    files.clear();

    // Find only MIDI files (WAV can be exported on demand)
    auto foundFiles = outputDirectory.findChildFiles(
        juce::File::findFiles,
        false,
        "*.mid;*.midi");

    DBG("RecentFilesPanel: Found " << foundFiles.size() << " MIDI files in " << outputDirectory.getFullPathName());

    // Sort by date (newest first)
    foundFiles.sort();
    std::sort(foundFiles.begin(), foundFiles.end(),
              [](const juce::File& a, const juce::File& b) {
                  return a.getLastModificationTime() > b.getLastModificationTime();
              });

    // Limit to most recent 50 files
    int maxFiles = juce::jmin(50, foundFiles.size());

    for (int i = 0; i < maxFiles; ++i)
        files.add(parseFileInfo(foundFiles[i]));

    lastScanTime = juce::Time::getCurrentTime();
    lastFileCount = foundFiles.size();
    
    if (fileList)
    {
        fileList->updateContent();
        fileList->repaint();
    }
    
    // Update empty state visibility
    bool hasFiles = !files.isEmpty();
    if (fileList) fileList->setVisible(hasFiles);
    emptyLabel.setVisible(!hasFiles);
    
    DBG("RecentFilesPanel: Scan complete, showing " << files.size() << " files");
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
    
    // Create display name (genre with proper capitalization)
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
        
        if (info.file.hasFileExtension(".mid;.midi"))
        {
            bool loaded = audioEngine.loadMidiFile(info.file);
            DBG("  AudioEngine load result: " << (loaded ? "SUCCESS" : "FAILED"));
        }
        
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
// File Management Operations
//==============================================================================
void RecentFilesPanel::showContextMenu(int row)
{
    if (row < 0 || row >= files.size())
        return;
    
    selectedRow = row;
    const auto& info = files[row];
    
    juce::PopupMenu menu;
    menu.addItem(1, "Load File", true);
    menu.addItem(8, "Export to WAV...", true);  // New option
    menu.addSeparator();
    menu.addItem(2, "Show in Explorer", true);
    menu.addItem(3, "Export MIDI to...", true);
    menu.addItem(4, "Rename...", true);
    menu.addSeparator();
    menu.addItem(5, "Delete", true);
    menu.addSeparator();
    menu.addItem(6, "Delete ALL Files...", true);
    
    menu.showMenuAsync(juce::PopupMenu::Options(),
        [this, info](int result) {
            switch (result)
            {
                case 1: loadSelectedFile(); break;
                case 8: exportToWav(); break;  // New handler
                case 2: revealInExplorer(); break;
                case 3: exportSelectedFile(); break;
                case 4: renameSelectedFile(); break;
                case 5: deleteSelectedFile(); break;
                case 6: deleteAllFiles(); break;
                default: break;
            }
        });
}

void RecentFilesPanel::exportToWav()
{
    if (selectedRow < 0 || selectedRow >= files.size())
        return;
    
    const auto& info = files[selectedRow];
    const auto midiFile = info.file;
    
    // Create default WAV filename (same name but .wav extension)
    auto defaultWavFile = midiFile.getParentDirectory()
                                  .getChildFile(midiFile.getFileNameWithoutExtension() + ".wav");
    
    auto chooser = std::make_shared<juce::FileChooser>(
        "Export to WAV",
        defaultWavFile,
        "*.wav"
    );
    
    chooser->launchAsync(juce::FileBrowserComponent::saveMode | juce::FileBrowserComponent::canSelectFiles,
        [this, chooser, midiFile](const juce::FileChooser& fc)
        {
            auto destFile = fc.getResult();
            if (destFile != juce::File{})
            {
                // Ensure .wav extension
                if (!destFile.hasFileExtension(".wav"))
                    destFile = destFile.withFileExtension("wav");
                
                // Load the MIDI file first
                if (!audioEngine.loadMidiFile(midiFile))
                {
                    juce::AlertWindow::showMessageBoxAsync(
                        juce::MessageBoxIconType::WarningIcon,
                        "Export Failed",
                        "Could not load the MIDI file for rendering."
                    );
                    return;
                }
                
                // Show progress message
                juce::AlertWindow::showMessageBoxAsync(
                    juce::MessageBoxIconType::InfoIcon,
                    "Exporting...",
                    "Rendering MIDI to WAV. This may take a moment..."
                );
                
                // Render to WAV (on background thread would be better, but this works for now)
                juce::MessageManager::callAsync([this, destFile, midiFile]()
                {
                    if (audioEngine.renderToWavFile(destFile))
                    {
                        juce::AlertWindow::showMessageBoxAsync(
                            juce::MessageBoxIconType::InfoIcon,
                            "Export Complete",
                            "Successfully exported to:\n\n" + destFile.getFullPathName()
                        );
                        
                        // Optionally reveal in explorer
                        destFile.revealToUser();
                    }
                    else
                    {
                        juce::AlertWindow::showMessageBoxAsync(
                            juce::MessageBoxIconType::WarningIcon,
                            "Export Failed",
                            "Could not render the MIDI file to WAV."
                        );
                    }
                });
            }
        });
}

void RecentFilesPanel::deleteSelectedFile()
{
    if (selectedRow < 0 || selectedRow >= files.size())
        return;
    
    const auto fileToDelete = files[selectedRow].file;
    const auto fileName = fileToDelete.getFileName();
    
    // Use async confirmation dialog
    juce::AlertWindow::showAsync(
        juce::MessageBoxOptions()
            .withIconType(juce::MessageBoxIconType::WarningIcon)
            .withTitle("Delete File")
            .withMessage("Are you sure you want to delete:\n\n" + fileName + "\n\nThis will move the file to Recycle Bin.")
            .withButton("Delete")
            .withButton("Cancel"),
        [this, fileToDelete](int result)
        {
            if (result == 1)  // Delete button clicked
            {
                // Move to recycle bin instead of permanent delete
                if (fileToDelete.moveToTrash())
                {
                    DBG("RecentFilesPanel: Moved to trash: " << fileToDelete.getFullPathName());
                    refresh();
                }
                else
                {
                    juce::AlertWindow::showMessageBoxAsync(
                        juce::MessageBoxIconType::WarningIcon,
                        "Delete Failed",
                        "Could not delete the file. It may be in use by another application."
                    );
                }
            }
        });
}

void RecentFilesPanel::exportSelectedFile()
{
    if (selectedRow < 0 || selectedRow >= files.size())
        return;
    
    const auto srcFile = files[selectedRow].file;
    const auto srcExt = srcFile.getFileExtension();
    const bool isMidi = srcFile.hasFileExtension(".mid;.midi");
    
    auto chooser = std::make_shared<juce::FileChooser>(
        isMidi ? "Export MIDI File" : "Export File",
        juce::File::getSpecialLocation(juce::File::userDocumentsDirectory)
            .getChildFile(srcFile.getFileName()),
        isMidi ? "*.mid;*.midi" : (srcExt.isNotEmpty() ? ("*" + srcExt) : "*.*")
    );
    
    chooser->launchAsync(juce::FileBrowserComponent::saveMode | juce::FileBrowserComponent::canSelectFiles,
        [this, chooser, srcFile, srcExt](const juce::FileChooser& fc)
        {
            auto destFile = fc.getResult();
            if (destFile != juce::File{})
            {
                // Preserve source extension if user didn't provide one
                if (destFile.getFileExtension().isEmpty() && srcExt.isNotEmpty())
                    destFile = destFile.withFileExtension(srcExt.substring(1));
                
                if (srcFile.copyFileTo(destFile))
                {
                    DBG("RecentFilesPanel: Exported to: " << destFile.getFullPathName());
                    juce::AlertWindow::showMessageBoxAsync(
                        juce::MessageBoxIconType::InfoIcon,
                        "Export Complete",
                        "File exported successfully to:\n\n" + destFile.getFullPathName()
                    );
                }
                else
                {
                    juce::AlertWindow::showMessageBoxAsync(
                        juce::MessageBoxIconType::WarningIcon,
                        "Export Failed",
                        "Could not export the file. Please check the destination path."
                    );
                }
            }
        });
}

void RecentFilesPanel::revealInExplorer()
{
    if (selectedRow >= 0 && selectedRow < files.size())
    {
        // Reveal specific file
        files[selectedRow].file.revealToUser();
    }
    else if (outputDirectory.isDirectory())
    {
        // Open folder
        outputDirectory.startAsProcess();
    }
}

void RecentFilesPanel::renameSelectedFile()
{
    if (selectedRow < 0 || selectedRow >= files.size())
        return;
    
    const auto& info = files[selectedRow];
    
    // Create input dialog
    auto* aw = new juce::AlertWindow("Rename File", 
                                     "Enter new name:", 
                                     juce::AlertWindow::QuestionIcon);
    aw->addTextEditor("newName", info.file.getFileNameWithoutExtension(), "New name:");
    aw->addButton("Rename", 1, juce::KeyPress(juce::KeyPress::returnKey));
    aw->addButton("Cancel", 0, juce::KeyPress(juce::KeyPress::escapeKey));
    
    aw->enterModalState(true, juce::ModalCallbackFunction::create(
        [this, aw, info](int result) {
            if (result == 1)
            {
                auto newName = aw->getTextEditorContents("newName").trim();
                if (newName.isNotEmpty())
                {
                    auto newFile = info.file.getParentDirectory()
                                       .getChildFile(newName + ".mid");
                    
                    if (newFile.exists())
                    {
                        juce::AlertWindow::showMessageBoxAsync(
                            juce::MessageBoxIconType::WarningIcon,
                            "Rename Failed",
                            "A file with that name already exists."
                        );
                    }
                    else if (info.file.moveFileTo(newFile))
                    {
                        DBG("RecentFilesPanel: Renamed to: " << newFile.getFullPathName());
                        this->refresh();
                    }
                    else
                    {
                        juce::AlertWindow::showMessageBoxAsync(
                            juce::MessageBoxIconType::WarningIcon,
                            "Rename Failed",
                            "Could not rename the file."
                        );
                    }
                }
            }
            delete aw;
        }), true);
}

void RecentFilesPanel::deleteAllFiles()
{
    if (files.isEmpty())
        return;
    
    const int fileCount = files.size();
    
    // Collect all file paths before showing dialog (since files array may change)
    juce::Array<juce::File> filesToDelete;
    for (const auto& info : files)
        filesToDelete.add(info.file);
    
    // Confirm deletion with count using async dialog
    juce::AlertWindow::showAsync(
        juce::MessageBoxOptions()
            .withIconType(juce::MessageBoxIconType::WarningIcon)
            .withTitle("Delete All Files")
            .withMessage("Are you sure you want to delete ALL " + juce::String(fileCount) + " MIDI files?\n\n"
                        "Files will be moved to the Recycle Bin.")
            .withButton("Delete All")
            .withButton("Cancel"),
        [this, filesToDelete](int result)
        {
            if (result == 1)  // Delete All clicked
            {
                int deleted = 0;
                int failed = 0;
                
                for (const auto& file : filesToDelete)
                {
                    if (file.moveToTrash())
                        deleted++;
                    else
                        failed++;
                }
                
                DBG("RecentFilesPanel: Deleted " << deleted << " files, " << failed << " failed");
                
                if (failed > 0)
                {
                    juce::AlertWindow::showMessageBoxAsync(
                        juce::MessageBoxIconType::WarningIcon,
                        "Partial Deletion",
                        "Deleted " + juce::String(deleted) + " files.\n" +
                        juce::String(failed) + " files could not be deleted (may be in use)."
                    );
                }
                
                refresh();
            }
        });
}

//==============================================================================
void RecentFilesPanel::timerCallback()
{
    // Check if directory has new files by counting
    if (outputDirectory.isDirectory())
    {
        auto foundFiles = outputDirectory.findChildFiles(
            juce::File::findFiles,
            false,
            "*.mid;*.midi");

        // Refresh if file count changed
        if (foundFiles.size() != lastFileCount)
        {
            DBG("RecentFilesPanel: File count changed from " << lastFileCount 
                << " to " << foundFiles.size() << ", refreshing...");
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
