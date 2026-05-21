/*
  ==============================================================================

    ExpansionBrowserPanel.cpp
    
    Implementation of the expansion browser UI.

  ==============================================================================
*/

#include "ExpansionBrowserPanel.h"
#include "Theme/ThemeManager.h"

//==============================================================================
// ExpansionCard
//==============================================================================

ExpansionCard::ExpansionCard(const ExpansionInfo& info)
    : expansionInfo(info)
{
    enableToggle.setButtonText("");
    enableToggle.setToggleState(info.enabled, juce::dontSendNotification);
    enableToggle.onClick = [this] {
        bool newEnabled = enableToggle.getToggleState();
        expansionInfo.enabled = newEnabled;
        if (listener)
            listener->expansionEnableToggled(this, newEnabled);
        repaint();
    };
    addAndMakeVisible(enableToggle);
}

void ExpansionCard::paint(juce::Graphics& g)
{
    auto bounds = getLocalBounds().reduced(2);
    
    // Background
    juce::Colour bgColour = ThemeManager::getCurrentScheme().windowBackground;
    if (selected)
        bgColour = ThemeManager::getCurrentScheme().accent.withAlpha(0.3f);
    else if (hovered)
        bgColour = bgColour.brighter(0.1f);
    
    g.setColour(bgColour);
    g.fillRoundedRectangle(bounds.toFloat(), 6.0f);
    
    // Border
    g.setColour(selected ? ThemeManager::getCurrentScheme().accent 
                        : ThemeManager::getCurrentScheme().outline);
    g.drawRoundedRectangle(bounds.toFloat(), 6.0f, selected ? 2.0f : 1.0f);
    
    // Content
    auto contentBounds = bounds.reduced(8);
    
    // Name
    g.setColour(ThemeManager::getCurrentScheme().text);
    g.setFont(juce::Font(14.0f).boldened());
    g.drawText(expansionInfo.name, 
               contentBounds.removeFromTop(20),
               juce::Justification::centredLeft);
    
    // Instrument count
    g.setFont(juce::Font(11.0f));
    g.setColour(ThemeManager::getCurrentScheme().textSecondary);
    g.drawText(juce::String(expansionInfo.instrumentCount) + " instruments",
               contentBounds.removeFromTop(16),
               juce::Justification::centredLeft);
    
    // Target genres
    if (!expansionInfo.targetGenres.isEmpty())
    {
        auto genreText = expansionInfo.targetGenres.joinIntoString(", ");
        g.setColour(ThemeManager::getCurrentScheme().accent);
        g.setFont(juce::Font(10.0f));
        g.drawText(genreText,
                   contentBounds.removeFromTop(14),
                   juce::Justification::centredLeft);
    }
    
    // Enabled indicator
    if (!expansionInfo.enabled)
    {
        g.setColour(juce::Colours::red.withAlpha(0.5f));
        g.setFont(juce::Font(10.0f));
        g.drawText("(Disabled)", bounds, juce::Justification::topRight);
    }
}

void ExpansionCard::resized()
{
    auto bounds = getLocalBounds().reduced(8);
    enableToggle.setBounds(bounds.removeFromRight(24).removeFromTop(24));
}

void ExpansionCard::mouseEnter(const juce::MouseEvent&)
{
    hovered = true;
    repaint();
}

void ExpansionCard::mouseExit(const juce::MouseEvent&)
{
    hovered = false;
    repaint();
}

void ExpansionCard::mouseDown(const juce::MouseEvent&)
{
    if (listener)
        listener->expansionCardClicked(this);
}

void ExpansionCard::setSelected(bool sel)
{
    selected = sel;
    repaint();
}

void ExpansionCard::setEnabled(bool enabled)
{
    expansionInfo.enabled = enabled;
    enableToggle.setToggleState(enabled, juce::dontSendNotification);
    repaint();
}

//==============================================================================
// ExpansionListComponent
//==============================================================================

ExpansionListComponent::ExpansionListComponent()
{
    viewport.setViewedComponent(&contentComponent, false);
    viewport.setScrollBarsShown(true, false);
    addAndMakeVisible(viewport);
}

ExpansionListComponent::~ExpansionListComponent()
{
    clearExpansions();
}

void ExpansionListComponent::paint(juce::Graphics& g)
{
    g.fillAll(ThemeManager::getCurrentScheme().windowBackground);
}

void ExpansionListComponent::paintOverChildren(juce::Graphics& g)
{
    if (!cards.isEmpty())
        return;

    auto bounds = getLocalBounds().reduced(16);
    g.setColour(ThemeManager::getCurrentScheme().textSecondary);
    g.setFont(juce::Font(12.0f));
    g.drawFittedText(emptyStateMessage, bounds, juce::Justification::centred, 4);
}

void ExpansionListComponent::resized()
{
    viewport.setBounds(getLocalBounds());
    updateLayout();
}

void ExpansionListComponent::setExpansions(const juce::Array<ExpansionInfo>& expansions)
{
    clearExpansions();
    
    for (const auto& exp : expansions)
    {
        auto* card = cards.add(new ExpansionCard(exp));
        card->setListener(this);
        contentComponent.addAndMakeVisible(card);
    }
    
    updateLayout();
}

void ExpansionListComponent::clearExpansions()
{
    selectedCard = nullptr;
    cards.clear();
    repaint();
}

void ExpansionListComponent::setEmptyStateMessage(const juce::String& message)
{
    emptyStateMessage = message;
    repaint();
}

const ExpansionInfo* ExpansionListComponent::getSelectedExpansion() const
{
    if (selectedCard)
        return &selectedCard->getInfo();
    return nullptr;
}

void ExpansionListComponent::clearSelection()
{
    if (selectedCard)
    {
        selectedCard->setSelected(false);
        selectedCard = nullptr;
    }
}

void ExpansionListComponent::expansionCardClicked(ExpansionCard* card)
{
    if (selectedCard == card)
        return;
    
    clearSelection();
    
    selectedCard = card;
    selectedCard->setSelected(true);
    
    listeners.call(&Listener::expansionSelected, card->getInfo());
}

void ExpansionListComponent::expansionEnableToggled(ExpansionCard* card, bool enabled)
{
    listeners.call(&Listener::expansionEnableChanged, card->getInfo().id, enabled);
}

void ExpansionListComponent::updateLayout()
{
    const int cardHeight = 80;
    const int padding = 4;
    
    int y = padding;
    int width = viewport.getWidth() - viewport.getScrollBarThickness() - padding * 2;
    
    for (auto* card : cards)
    {
        card->setBounds(padding, y, width, cardHeight);
        y += cardHeight + padding;
    }
    
    contentComponent.setSize(viewport.getWidth(), y + padding);
}

//==============================================================================
// ExpansionInstrumentList
//==============================================================================

ExpansionInstrumentList::ExpansionInstrumentList()
    : table("InstrumentTable", this)
{
    // Setup columns
    table.getHeader().addColumn("Name", 1, 150, 100, 300);
    table.getHeader().addColumn("Category", 2, 80, 60, 120);
    table.getHeader().addColumn("Role", 3, 100, 80, 150);
    table.getHeader().addColumn("Tags", 4, 150, 100, 300);
    
    table.setMultipleSelectionEnabled(false);
    table.setColour(juce::ListBox::backgroundColourId, ThemeManager::getCurrentScheme().windowBackground);
    
    addAndMakeVisible(table);
}

ExpansionInstrumentList::~ExpansionInstrumentList() = default;

void ExpansionInstrumentList::paint(juce::Graphics& g)
{
    g.fillAll(ThemeManager::getCurrentScheme().windowBackground);
}

void ExpansionInstrumentList::paintOverChildren(juce::Graphics& g)
{
    if (!filteredInstruments.isEmpty())
        return;

    auto bounds = getLocalBounds().reduced(18);
    g.setColour(ThemeManager::getCurrentScheme().textSecondary);
    g.setFont(juce::Font(12.0f));
    g.drawFittedText(emptyStateMessage, bounds, juce::Justification::centred, 4);
}

void ExpansionInstrumentList::resized()
{
    table.setBounds(getLocalBounds());
}

void ExpansionInstrumentList::setInstruments(const juce::Array<ExpansionInstrumentInfo>& instruments)
{
    allInstruments = instruments;
    applyFilter();
}

void ExpansionInstrumentList::clearInstruments()
{
    allInstruments.clear();
    filteredInstruments.clear();
    table.updateContent();
    repaint();
}

void ExpansionInstrumentList::setFilter(const juce::String& filter)
{
    filterText = filter;
    applyFilter();
}

void ExpansionInstrumentList::setEmptyStateMessage(const juce::String& message)
{
    emptyStateMessage = message;
    repaint();
}

void ExpansionInstrumentList::applyFilter()
{
    filteredInstruments.clear();
    
    if (filterText.isEmpty())
    {
        filteredInstruments = allInstruments;
    }
    else
    {
        auto filterLower = filterText.toLowerCase();
        for (const auto& inst : allInstruments)
        {
            if (inst.name.toLowerCase().contains(filterLower) ||
                inst.category.toLowerCase().contains(filterLower) ||
                inst.role.toLowerCase().contains(filterLower) ||
                inst.tags.joinIntoString(" ").toLowerCase().contains(filterLower))
            {
                filteredInstruments.add(inst);
            }
        }
    }

    if (allInstruments.isEmpty() && filterText.isEmpty())
        emptyStateMessage = "Select an expansion to browse its instruments.";
    else if (filteredInstruments.isEmpty() && !filterText.isEmpty())
        emptyStateMessage = "No expansion instruments match the current search. Try manual browse or another pack.";
    
    table.updateContent();
    table.repaint();
    repaint();
}

int ExpansionInstrumentList::getNumRows()
{
    return filteredInstruments.size();
}

void ExpansionInstrumentList::paintRowBackground(juce::Graphics& g, int rowNumber, 
                                                  int width, int height, bool rowIsSelected)
{
    auto colour = ThemeManager::getCurrentScheme().windowBackground;
    if (rowIsSelected)
        colour = ThemeManager::getCurrentScheme().accent.withAlpha(0.3f);
    else if (rowNumber % 2)
        colour = colour.brighter(0.03f);
    
    g.fillAll(colour);
}

void ExpansionInstrumentList::paintCell(juce::Graphics& g, int rowNumber, int columnId,
                                         int width, int height, bool rowIsSelected)
{
    if (rowNumber >= filteredInstruments.size())
        return;
    
    const auto& inst = filteredInstruments[rowNumber];
    
    g.setColour(rowIsSelected ? ThemeManager::getCurrentScheme().text 
                              : ThemeManager::getCurrentScheme().textSecondary);
    g.setFont(juce::Font(12.0f));
    
    juce::String text;
    switch (columnId)
    {
        case 1: text = inst.name; break;
        case 2: text = inst.category; break;
        case 3: text = inst.role; break;
        case 4: text = inst.tags.joinIntoString(", "); break;
    }
    
    g.drawText(text, 4, 0, width - 8, height, juce::Justification::centredLeft);
}

void ExpansionInstrumentList::selectedRowsChanged(int lastRowSelected)
{
    if (lastRowSelected >= 0 && lastRowSelected < filteredInstruments.size())
    {
        listeners.call(&Listener::instrumentSelected, filteredInstruments[lastRowSelected]);
    }
}

void ExpansionInstrumentList::cellDoubleClicked(int rowNumber, int columnId, const juce::MouseEvent&)
{
    if (rowNumber >= 0 && rowNumber < filteredInstruments.size())
    {
        listeners.call(&Listener::instrumentActivated, filteredInstruments[rowNumber]);
    }
}

//==============================================================================
// ResolutionTestPanel
//==============================================================================

ResolutionTestPanel::ResolutionTestPanel()
{
    // Setup UI
    instructionLabel.setFont(juce::Font(12.0f).boldened());
    addAndMakeVisible(instructionLabel);
    
    instrumentInput.setTextToShowWhenEmpty("Instrument name...", juce::Colours::grey);
    instrumentInput.setFont(juce::Font(12.0f));
    addAndMakeVisible(instrumentInput);
    
    // Add common genres
    genreCombo.addItem("trap", 1);
    genreCombo.addItem("g_funk", 2);
    genreCombo.addItem("rnb", 3);
    genreCombo.addItem("lofi", 4);
    genreCombo.addItem("eskista", 5);
    genreCombo.addItem("boom_bap", 6);
    genreCombo.addItem("house", 7);
    genreCombo.addItem("drill", 8);
    genreCombo.setSelectedId(1, juce::dontSendNotification);
    addAndMakeVisible(genreCombo);
    
    testButton.onClick = [this] { onTestClicked(); };
    addAndMakeVisible(testButton);
    
    // Result labels
    resultNameLabel.setFont(juce::Font(12.0f).boldened());
    resultNameLabel.setColour(juce::Label::textColourId, ThemeManager::getCurrentScheme().accent);
    addAndMakeVisible(resultNameLabel);
    
    resultMatchLabel.setFont(juce::Font(11.0f));
    addAndMakeVisible(resultMatchLabel);
    
    resultPathLabel.setFont(juce::Font(10.0f));
    resultPathLabel.setColour(juce::Label::textColourId, ThemeManager::getCurrentScheme().textSecondary);
    addAndMakeVisible(resultPathLabel);
    
    resultNoteLabel.setFont(juce::Font(10.0f));
    resultNoteLabel.setColour(juce::Label::textColourId, ThemeManager::getCurrentScheme().textSecondary);
    addAndMakeVisible(resultNoteLabel);
}

void ResolutionTestPanel::paint(juce::Graphics& g)
{
    auto bounds = getLocalBounds();
    
    // Background
    g.setColour(ThemeManager::getCurrentScheme().panelBackground);
    g.fillRoundedRectangle(bounds.toFloat(), 4.0f);
    
    // Border
    g.setColour(ThemeManager::getCurrentScheme().outline);
    g.drawRoundedRectangle(bounds.toFloat().reduced(0.5f), 4.0f, 1.0f);
}

void ResolutionTestPanel::resized()
{
    auto bounds = getLocalBounds().reduced(8);
    
    // Row 1: Title
    instructionLabel.setBounds(bounds.removeFromTop(20));
    bounds.removeFromTop(4);
    
    // Row 2: Input controls
    auto inputRow = bounds.removeFromTop(28);
    instrumentInput.setBounds(inputRow.removeFromLeft(150));
    inputRow.removeFromLeft(8);
    genreCombo.setBounds(inputRow.removeFromLeft(100));
    inputRow.removeFromLeft(8);
    testButton.setBounds(inputRow.removeFromLeft(80));
    
    bounds.removeFromTop(8);
    
    // Row 3: Results
    resultNameLabel.setBounds(bounds.removeFromTop(18));
    resultMatchLabel.setBounds(bounds.removeFromTop(16));
    resultPathLabel.setBounds(bounds.removeFromTop(14));
    resultNoteLabel.setBounds(bounds.removeFromTop(14));
}

void ResolutionTestPanel::showPending(const juce::String& instrument, const juce::String& genre)
{
    resultNameLabel.setColour(juce::Label::textColourId, ThemeManager::getCurrentScheme().accent);
    resultNameLabel.setText("Resolving \"" + instrument + "\"...", juce::dontSendNotification);
    resultMatchLabel.setText("Checking for a matched or fallback/default expansion result for genre: " + genre,
                             juce::dontSendNotification);
    resultPathLabel.setText("", juce::dontSendNotification);
    resultNoteLabel.setText("", juce::dontSendNotification);
}

void ResolutionTestPanel::showResult(const ResolvedInstrumentInfo& result)
{
    const auto matchType = result.matchType.toLowerCase();
    const bool isFallbackLike = matchType == "default" || matchType.contains("fallback");

    if (result.path.isEmpty())
    {
        resultNameLabel.setColour(juce::Label::textColourId, juce::Colours::orange);
        resultNameLabel.setText("No expansion match found", juce::dontSendNotification);
        resultMatchLabel.setText("No match — manual browse needed", juce::dontSendNotification);
        resultPathLabel.setText("", juce::dontSendNotification);
        resultNoteLabel.setText(result.note.isNotEmpty() ? result.note
                                                         : "Try another search term or browse the expansion/instrument lists manually.",
                                juce::dontSendNotification);
        return;
    }
    
    resultNameLabel.setColour(juce::Label::textColourId,
                              isFallbackLike ? juce::Colours::orange : ThemeManager::getCurrentScheme().accent);
    resultNameLabel.setText((isFallbackLike ? "Fallback/default suggestion: " : "Matched: ")
                            + result.name + " (" + result.source + ")",
                            juce::dontSendNotification);
    
    // Format match type with confidence
    juce::String matchStr = isFallbackLike
        ? ("Fallback/default result (" + juce::String(result.confidence * 100, 0) + "%) — manual browse may still be needed")
        : ("Matched via " + result.matchType + " (" + juce::String(result.confidence * 100, 0) + "%)");
    resultMatchLabel.setText(matchStr, juce::dontSendNotification);
    
    // Truncate path for display
    auto displayPath = result.path;
    if (displayPath.length() > 60)
        displayPath = "..." + displayPath.substring(displayPath.length() - 57);
    resultPathLabel.setText(displayPath, juce::dontSendNotification);
    
    auto note = result.note;
    if (note.isEmpty() && isFallbackLike)
        note = "Fallback/default result — browse the expansion lists manually if this is not the instrument you wanted.";
    resultNoteLabel.setText(note, juce::dontSendNotification);
}

void ResolutionTestPanel::showFailure(const juce::String& message)
{
    resultNameLabel.setColour(juce::Label::textColourId, juce::Colours::red);
    resultNameLabel.setText("Resolution failed", juce::dontSendNotification);
    resultMatchLabel.setText("No match result returned", juce::dontSendNotification);
    resultPathLabel.setText("", juce::dontSendNotification);
    resultNoteLabel.setText(message, juce::dontSendNotification);
}

void ResolutionTestPanel::clear()
{
    resultNameLabel.setText("", juce::dontSendNotification);
    resultMatchLabel.setText("", juce::dontSendNotification);
    resultPathLabel.setText("", juce::dontSendNotification);
    resultNoteLabel.setText("", juce::dontSendNotification);
}

void ResolutionTestPanel::onTestClicked()
{
    auto instrument = instrumentInput.getText().trim();
    if (instrument.isEmpty())
    {
        showFailure("Enter an instrument name to test resolution. Fallback/default suggestions are shown only after a real query.");
        return;
    }
    
    auto genre = genreCombo.getText();
    
    if (listener)
        listener->resolveRequested(instrument, genre);
}

//==============================================================================
// ExpansionBrowserPanel
//==============================================================================

ExpansionBrowserPanel::ExpansionBrowserPanel()
{
    // Toolbar buttons
    importButton.onClick = [this] { onImportClicked(); };
    addAndMakeVisible(importButton);
    
    scanButton.onClick = [this] { onScanClicked(); };
    addAndMakeVisible(scanButton);
    
    refreshButton.onClick = [this] { onRefreshClicked(); };
    addAndMakeVisible(refreshButton);
    
    // Search
    searchLabel.attachToComponent(&searchBox, true);
    searchBox.setTextToShowWhenEmpty("Search instruments...", juce::Colours::grey);
    searchBox.onTextChange = [this] { onSearchChanged(); };
    addAndMakeVisible(searchBox);

    statusLabel.setFont(juce::Font(11.0f));
    statusLabel.setColour(juce::Label::textColourId, ThemeManager::getCurrentScheme().textSecondary);
    statusLabel.setJustificationType(juce::Justification::centredLeft);
    statusLabel.setTooltip(statusLabel.getText());
    addAndMakeVisible(statusLabel);
    
    // Lists
    expansionList.addListener(this);
    addAndMakeVisible(expansionList);
    
    instrumentList.addListener(this);
    addAndMakeVisible(instrumentList);
    
    // Resolution panel
    resolutionPanel.setListener(this);
    addAndMakeVisible(resolutionPanel);
}

ExpansionBrowserPanel::~ExpansionBrowserPanel()
{
    expansionList.removeListener(this);
    instrumentList.removeListener(this);
}

void ExpansionBrowserPanel::paint(juce::Graphics& g)
{
    g.fillAll(ThemeManager::getCurrentScheme().background);
}

void ExpansionBrowserPanel::resized()
{
    auto bounds = getLocalBounds().reduced(4);
    
    // Toolbar
    auto toolbar = bounds.removeFromTop(36);
    importButton.setBounds(toolbar.removeFromLeft(130));
    toolbar.removeFromLeft(8);
    scanButton.setBounds(toolbar.removeFromLeft(100));
    toolbar.removeFromLeft(8);
    refreshButton.setBounds(toolbar.removeFromLeft(80));
    
    // Search on right side
    auto searchArea = toolbar.removeFromRight(200);
    searchBox.setBounds(searchArea.withTrimmedLeft(50));

    statusLabel.setBounds(bounds.removeFromTop(20).reduced(4, 0));
    
    bounds.removeFromTop(8);
    
    // Resolution panel at bottom
    resolutionPanel.setBounds(bounds.removeFromBottom(110));
    bounds.removeFromBottom(4);
    
    // Split remaining space between expansion list and instrument list
    auto contentBounds = bounds;
    auto leftWidth = juce::jmin(280, contentBounds.getWidth() / 3);
    
    expansionList.setBounds(contentBounds.removeFromLeft(leftWidth));
    contentBounds.removeFromLeft(4);
    instrumentList.setBounds(contentBounds);
}

void ExpansionBrowserPanel::loadExpansionsFromJSON(const juce::String& json)
{
    expansions.clear();
    
    auto parsed = juce::JSON::parse(json);
    
    if (auto* expArray = parsed.getProperty("expansions", juce::var()).getArray())
    {
        for (const auto& exp : *expArray)
        {
            expansions.add(ExpansionInfo::fromJSON(exp));
        }
    }
    
    expansionList.setEmptyStateMessage("No expansions loaded. Import an expansion or scan a folder to populate this list.");
    expansionList.setExpansions(expansions);
    
    // Auto-select first expansion
    if (!expansions.isEmpty())
    {
        selectedExpansionId = expansions[0].id;
        statusLabel.setText("Loaded " + juce::String(expansions.size()) + " expansions. Select one to browse its instruments.", juce::dontSendNotification);
        statusLabel.setTooltip(statusLabel.getText());
        listeners.call(&ExpansionBrowserPanel::Listener::requestInstrumentsOSC, selectedExpansionId);
    }
    else
    {
        selectedExpansionId.clear();
        instrumentList.clearInstruments();
        instrumentList.setEmptyStateMessage("No expansion is selected yet. Import or scan expansions to browse instruments.");
        resolutionPanel.clear();
        statusLabel.setText("No expansions found. Import a pack or scan a folder; resolution cannot match anything yet.", juce::dontSendNotification);
        statusLabel.setTooltip(statusLabel.getText());
    }
}

void ExpansionBrowserPanel::loadInstrumentsFromJSON(const juce::String& json)
{
    juce::Array<ExpansionInstrumentInfo> instruments;
    
    auto parsed = juce::JSON::parse(json);
    
    if (auto* instArray = parsed.getArray())
    {
        for (const auto& inst : *instArray)
        {
            instruments.add(ExpansionInstrumentInfo::fromJSON(inst));
        }
    }
    
    if (instruments.isEmpty())
    {
        instrumentList.setEmptyStateMessage("The selected expansion has no instruments. Manual browse or another pack may be needed.");
        statusLabel.setText("Selected expansion has no instruments. Manual browse or another pack may be needed.", juce::dontSendNotification);
    }
    else
    {
        instrumentList.setEmptyStateMessage("Search this expansion or select a different one if you need another source.");
        statusLabel.setText("Loaded " + juce::String(instruments.size()) + " instruments from the selected expansion.", juce::dontSendNotification);
    }

    statusLabel.setTooltip(statusLabel.getText());
    instrumentList.setInstruments(instruments);
}

void ExpansionBrowserPanel::showResolutionResult(const juce::String& json)
{
    auto parsed = juce::JSON::parse(json);
    auto result = ResolvedInstrumentInfo::fromJSON(parsed);
    resolutionPanel.showResult(result);

    const auto matchType = result.matchType.toLowerCase();
    const bool isFallbackLike = matchType == "default" || matchType.contains("fallback");
    if (result.path.isEmpty())
        statusLabel.setText("Resolution: no match found — manual browse needed.", juce::dontSendNotification);
    else if (isFallbackLike)
        statusLabel.setText("Resolution: fallback/default suggestion returned — manual browse may still be needed.", juce::dontSendNotification);
    else
        statusLabel.setText("Resolution: matched " + result.name + " via " + result.matchType + ".", juce::dontSendNotification);

    statusLabel.setTooltip(statusLabel.getText());
}

void ExpansionBrowserPanel::showResolutionPending(const juce::String& instrument, const juce::String& genre)
{
    resolutionPanel.showPending(instrument, genre);
    statusLabel.setText("Resolving \"" + instrument + "\" for genre " + genre + "...", juce::dontSendNotification);
    statusLabel.setTooltip(statusLabel.getText());
}

void ExpansionBrowserPanel::showResolutionFailure(const juce::String& message)
{
    resolutionPanel.showFailure(message);
    statusLabel.setText("Resolution failed. See the result note for details.", juce::dontSendNotification);
    statusLabel.setTooltip(message);
}

void ExpansionBrowserPanel::requestExpansionList()
{
    listeners.call(&ExpansionBrowserPanel::Listener::requestExpansionListOSC);
}

void ExpansionBrowserPanel::requestExpansionInstruments(const juce::String& expansionId)
{
    selectedExpansionId = expansionId;
    statusLabel.setText("Loading instruments for the selected expansion...", juce::dontSendNotification);
    statusLabel.setTooltip(statusLabel.getText());
    listeners.call(&ExpansionBrowserPanel::Listener::requestInstrumentsOSC, expansionId);
}

void ExpansionBrowserPanel::expansionSelected(const ExpansionInfo& info)
{
    selectedExpansionId = info.id;
    statusLabel.setText("Selected expansion: " + info.name + ". Loading instruments...", juce::dontSendNotification);
    statusLabel.setTooltip(statusLabel.getText());
    listeners.call(&ExpansionBrowserPanel::Listener::requestInstrumentsOSC, info.id);
}

void ExpansionBrowserPanel::expansionEnableChanged(const juce::String& expansionId, bool enabled)
{
    DBG("Expansion enable changed: " + expansionId + " -> " + (enabled ? "enabled" : "disabled"));
    listeners.call(&ExpansionBrowserPanel::Listener::requestExpansionEnableOSC, expansionId, enabled);
}

void ExpansionBrowserPanel::instrumentSelected(const ExpansionInstrumentInfo& info)
{
    // Could preview the instrument here
    DBG("Instrument selected: " + info.name);
    statusLabel.setText("Manual browse selection: " + info.name + " (" + info.expansion + ")", juce::dontSendNotification);
    statusLabel.setTooltip(statusLabel.getText());
}

void ExpansionBrowserPanel::instrumentActivated(const ExpansionInstrumentInfo& info)
{
    // Could play preview or add to project
    DBG("Instrument activated: " + info.name + " at " + info.path);
    statusLabel.setText("Activated expansion instrument: " + info.name + " (manual browse)", juce::dontSendNotification);
    statusLabel.setTooltip(statusLabel.getText());
}

void ExpansionBrowserPanel::resolveRequested(const juce::String& instrument, const juce::String& genre)
{
    listeners.call(&ExpansionBrowserPanel::Listener::requestResolveOSC, instrument, genre);
}

void ExpansionBrowserPanel::onImportClicked()
{
    auto chooser = std::make_shared<juce::FileChooser>(
        "Select Expansion Folder",
        juce::File::getSpecialLocation(juce::File::userDocumentsDirectory),
        "",
        true);
    
    chooser->launchAsync(juce::FileBrowserComponent::openMode | juce::FileBrowserComponent::canSelectDirectories,
        [this, chooser](const juce::FileChooser& fc)
        {
            auto results = fc.getResults();
            if (!results.isEmpty())
            {
                auto folder = results[0];
                listeners.call(&ExpansionBrowserPanel::Listener::requestImportExpansionOSC, folder.getFullPathName());
            }
        });
}

void ExpansionBrowserPanel::onScanClicked()
{
    auto chooser = std::make_shared<juce::FileChooser>(
        "Select Expansions Directory",
        juce::File::getSpecialLocation(juce::File::userDocumentsDirectory),
        "",
        true);
    
    chooser->launchAsync(juce::FileBrowserComponent::openMode | juce::FileBrowserComponent::canSelectDirectories,
        [this, chooser](const juce::FileChooser& fc)
        {
            auto results = fc.getResults();
            if (!results.isEmpty())
            {
                auto folder = results[0];
                listeners.call(&ExpansionBrowserPanel::Listener::requestScanExpansionsOSC, folder.getFullPathName());
            }
        });
}

void ExpansionBrowserPanel::onRefreshClicked()
{
    statusLabel.setText("Refreshing expansion list...", juce::dontSendNotification);
    statusLabel.setTooltip(statusLabel.getText());
    requestExpansionList();
}

void ExpansionBrowserPanel::onSearchChanged()
{
    instrumentList.setFilter(searchBox.getText());
    if (searchBox.getText().trim().isNotEmpty())
    {
        statusLabel.setText("Filtering instruments in the selected expansion...", juce::dontSendNotification);
        statusLabel.setTooltip(statusLabel.getText());
    }
}

