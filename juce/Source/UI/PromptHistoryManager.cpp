/*
  ==============================================================================

    PromptHistoryManager.cpp
    
    Implementation of prompt history management system.

  ==============================================================================
*/

#include "PromptHistoryManager.h"
#include "Theme/ColourScheme.h"
#include "Theme/LayoutConstants.h"

//==============================================================================
// PromptHistoryManager Implementation
//==============================================================================

PromptHistoryManager::PromptHistoryManager()
{
    historyFile = getDefaultHistoryFile();
    loadFromFile(historyFile);
}

PromptHistoryManager::~PromptHistoryManager()
{
    if (autoSaveEnabled)
        saveToFile(historyFile);
}

//==============================================================================
void PromptHistoryManager::addPrompt(const juce::String& prompt,
                                      const juce::String& genre,
                                      int bpm,
                                      const juce::String& key,
                                      const juce::String& outputFile)
{
    if (prompt.trim().isEmpty())
        return;
    
    juce::ScopedLock sl(lock);
    
    // Check if prompt already exists
    for (auto& entry : history)
    {
        if (entry.prompt.trim().equalsIgnoreCase(prompt.trim()))
        {
            // Update existing entry
            entry.timestamp = juce::Time::getCurrentTime();
            entry.useCount++;
            entry.genre = genre.isNotEmpty() ? genre : entry.genre;
            entry.bpm = bpm > 0 ? bpm : entry.bpm;
            entry.key = key.isNotEmpty() ? key : entry.key;
            if (outputFile.isNotEmpty())
                entry.outputFile = outputFile;
            
            autoSave();
            return;
        }
    }
    
    // Add new entry
    PromptEntry entry;
    entry.prompt = prompt.trim();
    entry.genre = genre;
    entry.bpm = bpm;
    entry.key = key;
    entry.timestamp = juce::Time::getCurrentTime();
    entry.isFavorite = false;
    entry.useCount = 1;
    entry.outputFile = outputFile;
    
    history.push_back(entry);
    enforceMaxSize();
    autoSave();
}

void PromptHistoryManager::toggleFavorite(const juce::String& prompt)
{
    juce::ScopedLock sl(lock);
    
    for (auto& entry : history)
    {
        if (entry.prompt.trim().equalsIgnoreCase(prompt.trim()))
        {
            entry.isFavorite = !entry.isFavorite;
            autoSave();
            return;
        }
    }
}

bool PromptHistoryManager::isFavorite(const juce::String& prompt) const
{
    juce::ScopedLock sl(lock);
    
    for (const auto& entry : history)
    {
        if (entry.prompt.trim().equalsIgnoreCase(prompt.trim()))
            return entry.isFavorite;
    }
    return false;
}

void PromptHistoryManager::removePrompt(const juce::String& prompt)
{
    juce::ScopedLock sl(lock);
    
    history.erase(
        std::remove_if(history.begin(), history.end(),
            [&prompt](const PromptEntry& e) {
                return e.prompt.trim().equalsIgnoreCase(prompt.trim());
            }),
        history.end());
    
    autoSave();
}

void PromptHistoryManager::clearHistory()
{
    juce::ScopedLock sl(lock);
    
    // Keep only favorites
    history.erase(
        std::remove_if(history.begin(), history.end(),
            [](const PromptEntry& e) { return !e.isFavorite; }),
        history.end());
    
    autoSave();
}

void PromptHistoryManager::clearAll()
{
    juce::ScopedLock sl(lock);
    history.clear();
    autoSave();
}

//==============================================================================
std::vector<PromptEntry> PromptHistoryManager::getAllPrompts() const
{
    juce::ScopedLock sl(lock);
    
    std::vector<PromptEntry> sorted = history;
    std::sort(sorted.begin(), sorted.end());  // Uses operator< for proper ordering
    return sorted;
}

std::vector<PromptEntry> PromptHistoryManager::getRecentPrompts(int maxCount) const
{
    auto all = getAllPrompts();
    if ((int)all.size() > maxCount)
        all.resize(maxCount);
    return all;
}

std::vector<PromptEntry> PromptHistoryManager::getFavorites() const
{
    juce::ScopedLock sl(lock);
    
    std::vector<PromptEntry> favorites;
    for (const auto& entry : history)
    {
        if (entry.isFavorite)
            favorites.push_back(entry);
    }
    
    std::sort(favorites.begin(), favorites.end(),
        [](const PromptEntry& a, const PromptEntry& b) {
            return a.timestamp > b.timestamp;  // Newest first
        });
    
    return favorites;
}

int PromptHistoryManager::getFavoritesCount() const
{
    juce::ScopedLock sl(lock);
    
    int count = 0;
    for (const auto& entry : history)
    {
        if (entry.isFavorite)
            count++;
    }
    return count;
}

//==============================================================================
std::vector<PromptEntry> PromptHistoryManager::searchPrompts(const juce::String& searchText) const
{
    if (searchText.trim().isEmpty())
        return getAllPrompts();
    
    juce::ScopedLock sl(lock);
    
    std::vector<PromptEntry> results;
    juce::String search = searchText.toLowerCase();
    
    for (const auto& entry : history)
    {
        if (entry.prompt.toLowerCase().contains(search) ||
            entry.genre.toLowerCase().contains(search))
        {
            results.push_back(entry);
        }
    }
    
    std::sort(results.begin(), results.end());
    return results;
}

const PromptEntry* PromptHistoryManager::findPrompt(const juce::String& prompt) const
{
    juce::ScopedLock sl(lock);
    
    for (const auto& entry : history)
    {
        if (entry.prompt.trim().equalsIgnoreCase(prompt.trim()))
            return &entry;
    }
    return nullptr;
}

//==============================================================================
void PromptHistoryManager::saveToFile(const juce::File& file)
{
    juce::ScopedLock sl(lock);
    
    juce::Array<juce::var> arr;
    for (const auto& entry : history)
        arr.add(entry.toVar());
    
    juce::var root(arr);
    juce::String json = juce::JSON::toString(root, true);
    
    // Ensure directory exists
    file.getParentDirectory().createDirectory();
    file.replaceWithText(json);
}

void PromptHistoryManager::loadFromFile(const juce::File& file)
{
    if (!file.existsAsFile())
        return;
    
    juce::ScopedLock sl(lock);
    
    juce::String json = file.loadFileAsString();
    juce::var root = juce::JSON::parse(json);
    
    if (root.isArray())
    {
        history.clear();
        for (const auto& item : *root.getArray())
        {
            history.push_back(PromptEntry::fromVar(item));
        }
    }
}

juce::File PromptHistoryManager::getDefaultHistoryFile()
{
    return juce::File::getSpecialLocation(juce::File::userApplicationDataDirectory)
        .getChildFile("AI Music Generator")
        .getChildFile("prompt_history.json");
}

//==============================================================================
juce::String PromptHistoryManager::exportFavoritesToJSON() const
{
    auto favorites = getFavorites();
    
    juce::Array<juce::var> arr;
    for (const auto& entry : favorites)
        arr.add(entry.toVar());
    
    return juce::JSON::toString(juce::var(arr), true);
}

void PromptHistoryManager::importFavoritesFromJSON(const juce::String& json)
{
    juce::var root = juce::JSON::parse(json);
    
    if (root.isArray())
    {
        juce::ScopedLock sl(lock);
        
        for (const auto& item : *root.getArray())
        {
            PromptEntry imported = PromptEntry::fromVar(item);
            imported.isFavorite = true;  // Mark as favorite when importing
            
            // Check if already exists
            bool found = false;
            for (auto& entry : history)
            {
                if (entry.prompt.trim().equalsIgnoreCase(imported.prompt.trim()))
                {
                    entry.isFavorite = true;
                    found = true;
                    break;
                }
            }
            
            if (!found)
                history.push_back(imported);
        }
        
        autoSave();
    }
}

//==============================================================================
void PromptHistoryManager::autoSave()
{
    if (autoSaveEnabled && historyFile.getFullPathName().isNotEmpty())
        saveToFile(historyFile);
}

void PromptHistoryManager::enforceMaxSize()
{
    // Keep all favorites, but limit non-favorites
    if ((int)history.size() <= MaxHistorySize)
        return;
    
    // Sort by favorites first, then by timestamp
    std::sort(history.begin(), history.end());
    
    // Count favorites
    int favCount = 0;
    for (const auto& e : history)
        if (e.isFavorite) favCount++;
    
    // Remove oldest non-favorites to get under limit
    while ((int)history.size() > MaxHistorySize && (int)history.size() > favCount)
    {
        // Find oldest non-favorite (at the end after sorting)
        for (auto it = history.rbegin(); it != history.rend(); ++it)
        {
            if (!it->isFavorite)
            {
                history.erase(std::next(it).base());
                break;
            }
        }
    }
}


//==============================================================================
// PromptHistoryComponent Implementation
//==============================================================================

PromptHistoryComponent::PromptHistoryComponent(PromptHistoryManager& manager)
    : historyManager(manager)
{
    listBox = std::make_unique<juce::ListBox>("PromptHistory", this);
    listBox->setRowHeight(50);
    listBox->setColour(juce::ListBox::backgroundColourId, AppColours::surface);
    listBox->setColour(juce::ListBox::outlineColourId, AppColours::border);
    addAndMakeVisible(*listBox);
    
    refresh();
}

PromptHistoryComponent::~PromptHistoryComponent()
{
}

//==============================================================================
void PromptHistoryComponent::addListener(Listener* listener)
{
    listeners.add(listener);
}

void PromptHistoryComponent::removeListener(Listener* listener)
{
    listeners.remove(listener);
}

//==============================================================================
void PromptHistoryComponent::paint(juce::Graphics& g)
{
    g.setColour(AppColours::surface);
    g.fillRoundedRectangle(getLocalBounds().toFloat(), 8.0f);
    
    g.setColour(AppColours::border);
    g.drawRoundedRectangle(getLocalBounds().toFloat().reduced(0.5f), 8.0f, 1.0f);
}

void PromptHistoryComponent::resized()
{
    listBox->setBounds(getLocalBounds().reduced(2));
}

void PromptHistoryComponent::refresh()
{
    displayedPrompts = historyManager.getRecentPrompts();
    listBox->updateContent();
    listBox->repaint();
}

//==============================================================================
int PromptHistoryComponent::getNumRows()
{
    return (int)displayedPrompts.size();
}

void PromptHistoryComponent::paintListBoxItem(int rowNumber, juce::Graphics& g, 
                                               int width, int height, bool rowIsSelected)
{
    if (rowNumber < 0 || rowNumber >= (int)displayedPrompts.size())
        return;
    
    const auto& entry = displayedPrompts[rowNumber];
    
    // Background
    if (rowIsSelected)
    {
        g.setColour(AppColours::primary.withAlpha(0.2f));
        g.fillRect(0, 0, width, height);
    }
    else if (rowNumber % 2 == 1)
    {
        g.setColour(AppColours::surfaceAlt.withAlpha(0.3f));
        g.fillRect(0, 0, width, height);
    }
    
    // Favorite indicator
    int xOffset = 8;
    if (entry.isFavorite)
    {
        g.setColour(juce::Colour(0xFFFFD700));  // Gold star
        g.setFont(14.0f);
        g.drawText(juce::String::fromUTF8("\xe2\x98\x85"), xOffset, 0, 20, height, 
                   juce::Justification::centredLeft);  // Filled star
        xOffset += 20;
    }
    
    // Prompt text (truncated)
    g.setColour(AppColours::textPrimary);
    g.setFont(13.0f);
    
    juce::String displayText = entry.prompt;
    if (displayText.length() > 60)
        displayText = displayText.substring(0, 57) + "...";
    
    g.drawText(displayText, xOffset, 4, width - xOffset - 60, 20, 
               juce::Justification::centredLeft, true);
    
    // Meta info (genre, BPM, timestamp)
    g.setColour(AppColours::textSecondary);
    g.setFont(10.0f);
    
    juce::String metaText;
    if (entry.genre.isNotEmpty())
        metaText += entry.genre + " | ";
    metaText += juce::String(entry.bpm) + " BPM";
    if (entry.useCount > 1)
        metaText += " | Used " + juce::String(entry.useCount) + "x";
    
    g.drawText(metaText, xOffset, 24, width - xOffset - 60, 16, 
               juce::Justification::centredLeft);
    
    // Time ago
    auto now = juce::Time::getCurrentTime();
    auto diff = now - entry.timestamp;
    juce::String timeAgo;
    
    if (diff.inDays() > 0)
        timeAgo = juce::String((int)diff.inDays()) + "d ago";
    else if (diff.inHours() > 0)
        timeAgo = juce::String((int)diff.inHours()) + "h ago";
    else if (diff.inMinutes() > 0)
        timeAgo = juce::String((int)diff.inMinutes()) + "m ago";
    else
        timeAgo = "just now";
    
    g.drawText(timeAgo, width - 60, 0, 55, height, juce::Justification::centredRight);
}

void PromptHistoryComponent::listBoxItemClicked(int row, const juce::MouseEvent& /*event*/)
{
    notifySelection(row);
}

void PromptHistoryComponent::listBoxItemDoubleClicked(int row, const juce::MouseEvent& /*event*/)
{
    notifySelection(row);
}

juce::Component* PromptHistoryComponent::refreshComponentForRow(int rowNumber, bool /*isRowSelected*/, 
                                                                  juce::Component* existingComponentToUpdate)
{
    // For now, use default painting. Can upgrade to custom row component later.
    juce::ignoreUnused(rowNumber, existingComponentToUpdate);
    return nullptr;
}

void PromptHistoryComponent::notifySelection(int row)
{
    if (row >= 0 && row < (int)displayedPrompts.size())
    {
        listeners.call(&Listener::promptSelected, displayedPrompts[row]);
    }
}


//==============================================================================
// PromptHistoryRow Implementation
//==============================================================================

PromptHistoryRow::PromptHistoryRow(PromptHistoryManager& manager)
    : historyManager(manager)
{
    favoriteButton.setButtonText("*");
    favoriteButton.setTooltip("Toggle favorite");
    favoriteButton.onClick = [this] {
        historyManager.toggleFavorite(currentEntry.prompt);
        updateFavoriteButton();
        if (onFavoriteToggled)
            onFavoriteToggled();
    };
    addAndMakeVisible(favoriteButton);
    
    deleteButton.setButtonText("X");
    deleteButton.setTooltip("Remove from history");
    deleteButton.setColour(juce::TextButton::buttonColourId, AppColours::error.withAlpha(0.3f));
    deleteButton.onClick = [this] {
        if (onDeleteRequested)
            onDeleteRequested();
    };
    addAndMakeVisible(deleteButton);
}

void PromptHistoryRow::setEntry(const PromptEntry& entry)
{
    currentEntry = entry;
    updateFavoriteButton();
    repaint();
}

void PromptHistoryRow::paint(juce::Graphics& g)
{
    // Prompt text
    g.setColour(AppColours::textPrimary);
    g.setFont(12.0f);
    
    juce::String displayText = currentEntry.prompt;
    if (displayText.length() > 50)
        displayText = displayText.substring(0, 47) + "...";
    
    g.drawText(displayText, 30, 2, getWidth() - 90, 20, juce::Justification::centredLeft, true);
    
    // Meta info
    g.setColour(AppColours::textSecondary);
    g.setFont(10.0f);
    g.drawText(currentEntry.genre + " | " + juce::String(currentEntry.bpm) + " BPM",
               30, 22, getWidth() - 90, 16, juce::Justification::centredLeft);
}

void PromptHistoryRow::resized()
{
    favoriteButton.setBounds(4, (getHeight() - 20) / 2, 22, 20);
    deleteButton.setBounds(getWidth() - 26, (getHeight() - 20) / 2, 22, 20);
}

void PromptHistoryRow::updateFavoriteButton()
{
    if (currentEntry.isFavorite)
    {
        favoriteButton.setButtonText(juce::String::fromUTF8("\xe2\x98\x85"));  // Filled star
        favoriteButton.setColour(juce::TextButton::textColourOffId, juce::Colour(0xFFFFD700));
    }
    else
    {
        favoriteButton.setButtonText(juce::String::fromUTF8("\xe2\x98\x86"));  // Empty star
        favoriteButton.setColour(juce::TextButton::textColourOffId, AppColours::textSecondary);
    }
}
