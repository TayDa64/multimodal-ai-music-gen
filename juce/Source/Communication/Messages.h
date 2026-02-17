/*
  ==============================================================================

    Messages.h
    
    Data structures for OSC communication with Python backend.

  ==============================================================================
*/

#pragma once

#include <juce_core/juce_core.h>

//==============================================================================
/**
    Protocol version for OSC message compatibility.
    Increment when making breaking changes to message structure.
*/
static constexpr int SCHEMA_VERSION = 1;

//==============================================================================
/**
    Request to generate music from a text prompt.
*/
struct GenerationRequest
{
    juce::String requestId;         // UUID for request/response correlation
    int schemaVersion = SCHEMA_VERSION;
    juce::String prompt;
    juce::String genre;             // Genre ID from GenreSelector (e.g., "g_funk", "trap")
    int bpm = 0;                    // 0 = auto-detect
    int bars = 8;                   // Number of bars to generate
    int numTakes = 1;               // Number of takes per track (1 = disabled)
    juce::String key;               // Empty = auto-detect
    juce::String outputDir;
    juce::StringArray instrumentPaths;
    juce::String soundfontPath;
    juce::String referenceUrl;
    juce::var options;             // Optional Phase 5.2 per-request overrides
    bool renderAudio = true;
    bool exportStems = false;
    bool exportMpc = false;
    bool verbose = false;
    
    /**
        Generate a new unique request ID using UUID.
    */
    void generateRequestId()
    {
        requestId = juce::Uuid().toString();
    }
    
    juce::String toJson() const
    {
        juce::DynamicObject::Ptr obj = new juce::DynamicObject();
        
        obj->setProperty("request_id", requestId);
        obj->setProperty("schema_version", schemaVersion);
        obj->setProperty("prompt", prompt);
        obj->setProperty("genre", genre);
        obj->setProperty("bpm", bpm);
        obj->setProperty("bars", bars);
        obj->setProperty("num_takes", numTakes);
        obj->setProperty("key", key);
        obj->setProperty("output_dir", outputDir);
        obj->setProperty("soundfont", soundfontPath);
        obj->setProperty("reference_url", referenceUrl);
        if (options.isObject() || options.isArray())
            obj->setProperty("options", options);
        obj->setProperty("render_audio", renderAudio);
        obj->setProperty("export_stems", exportStems);
        obj->setProperty("export_mpc", exportMpc);
        obj->setProperty("verbose", verbose);
        
        juce::Array<juce::var> paths;
        for (const auto& path : instrumentPaths)
            paths.add(path);
        obj->setProperty("instruments", paths);
        
        return juce::JSON::toString(juce::var(obj.get()), true);
    }
};

//==============================================================================
/**
    Request to regenerate a specific section of an existing project.
    Used for iterating on individual sections without regenerating the whole track.
*/
struct RegenerationRequest
{
    juce::String requestId;
    int schemaVersion = SCHEMA_VERSION;
    
    int startBar = 0;               // 0-indexed starting bar
    int endBar = 4;                 // 0-indexed ending bar (exclusive)
    juce::StringArray tracks;       // Empty = all tracks; otherwise specific track names
    juce::String seedStrategy = "new"; // "new" for fresh, "derived" to vary existing
    juce::String prompt;            // Optional override prompt for this section
    
    // Generation context
    int bpm = 0;
    juce::String key;
    juce::String mode;
    juce::String genre;

    // Optional Phase 5.2 per-request overrides (merged into options)
    juce::var extraOptions;
    
    void generateRequestId()
    {
        requestId = juce::Uuid().toString();
    }
    
    juce::String toJson() const
    {
        juce::DynamicObject::Ptr obj = new juce::DynamicObject();
        
        obj->setProperty("request_id", requestId);
        obj->setProperty("schema_version", schemaVersion);
        obj->setProperty("start_bar", startBar);
        obj->setProperty("end_bar", endBar);
        obj->setProperty("seed_strategy", seedStrategy);
        obj->setProperty("prompt", prompt);
        
        juce::Array<juce::var> trackList;
        for (const auto& track : tracks)
            trackList.add(track);
        obj->setProperty("tracks", trackList);
        
        // Options object for generation context
        juce::DynamicObject::Ptr options = new juce::DynamicObject();
        options->setProperty("bpm", bpm);
        options->setProperty("key", key);
        options->setProperty("mode", mode);
        options->setProperty("genre", genre);

        if (extraOptions.isObject())
        {
            if (auto* extra = extraOptions.getDynamicObject())
            {
                for (const auto& prop : extra->getProperties())
                    options->setProperty(prop.name, prop.value);
            }
        }
        obj->setProperty("options", juce::var(options.get()));
        
        return juce::JSON::toString(juce::var(obj.get()), true);
    }
};

//==============================================================================
/**
    Result of a generation request.
*/
struct GenerationResult
{
    juce::String taskId;
    juce::String requestId;         // Correlates with original request
    bool success = false;
    
    juce::String midiPath;
    juce::String audioPath;
    juce::StringArray stemPaths;
    juce::String mpcPath;
    
    // Metadata
    int bpm = 0;
    juce::String key;
    juce::String genre;
    juce::StringArray sections;
    
    // Stats
    float duration = 0.0f;
    int samplesGenerated = 0;
    
    // Instruments used (from backend)
    juce::var instrumentsUsed;

    // Takes (for TakeLanePanel)
    juce::String takesJson;  // JSON array of take data
    
    // Error info
    int errorCode = 0;
    juce::String errorMessage;
    
    static GenerationResult fromJson(const juce::String& jsonStr)
    {
        GenerationResult result;
        
        auto json = juce::JSON::parse(jsonStr);
        if (!json.isObject())
            return result;
        
        auto* obj = json.getDynamicObject();
        if (!obj)
            return result;
        
        result.taskId = obj->getProperty("task_id").toString();
        result.requestId = obj->getProperty("request_id").toString();
        result.success = obj->getProperty("success");
        
        result.midiPath = obj->getProperty("midi_path").toString();
        result.audioPath = obj->getProperty("audio_path").toString();
        result.mpcPath = obj->getProperty("mpc_path").toString();
        
        if (auto stems = obj->getProperty("stems_path"); stems.isArray())
        {
            for (int i = 0; i < stems.size(); ++i)
                result.stemPaths.add(stems[i].toString());
        }
        
        // Metadata
        if (auto metadata = obj->getProperty("metadata"); metadata.isObject())
        {
            auto* metaObj = metadata.getDynamicObject();
            if (metaObj)
            {
                result.bpm = metaObj->getProperty("bpm");
                result.key = metaObj->getProperty("key").toString();
                result.genre = metaObj->getProperty("genre").toString();
                
                if (auto sectionsArr = metaObj->getProperty("sections"); sectionsArr.isArray())
                {
                    for (int i = 0; i < sectionsArr.size(); ++i)
                    {
                        if (auto* sec = sectionsArr[i].getDynamicObject())
                            result.sections.add(sec->getProperty("name").toString());
                    }
                }
            }
        }
        
        result.duration = obj->getProperty("duration");
        result.samplesGenerated = obj->getProperty("samples_generated");
        result.errorCode = obj->getProperty("error_code");
        result.errorMessage = obj->getProperty("error_message").toString();

        if (auto instruments = obj->getProperty("instruments_used"); instruments.isArray())
            result.instrumentsUsed = instruments;
        
        // Extract takes array as JSON string for TakeLanePanel
        if (auto takesArr = obj->getProperty("takes"); takesArr.isArray())
        {
            // Build a JSON object with "tracks" key for TakeLanePanel format
            juce::DynamicObject::Ptr tracksObj = new juce::DynamicObject();
            
            // Group takes by track name
            for (int i = 0; i < takesArr.size(); ++i)
            {
                if (auto* takeObj = takesArr[i].getDynamicObject())
                {
                    juce::String trackName = takeObj->getProperty("track").toString();
                    
                    // Get or create array for this track
                    auto existingArr = tracksObj->getProperty(trackName);
                    juce::Array<juce::var> trackTakes;
                    if (existingArr.isArray())
                    {
                        for (int j = 0; j < existingArr.size(); ++j)
                            trackTakes.add(existingArr[j]);
                    }
                    trackTakes.add(takesArr[i]);
                    tracksObj->setProperty(trackName, trackTakes);
                }
            }
            
            juce::DynamicObject::Ptr rootObj = new juce::DynamicObject();
            rootObj->setProperty("tracks", juce::var(tracksObj.get()));
            result.takesJson = juce::JSON::toString(juce::var(rootObj.get()), true);
        }
        
        return result;
    }
};

//==============================================================================
/**
    Progress update from generation.
*/
struct ProgressUpdate
{
    juce::String requestId;         // Correlates with original request
    juce::String step;
    float percent = 0.0f;
    juce::String message;
    
    static ProgressUpdate fromJson(const juce::String& jsonStr)
    {
        ProgressUpdate update;
        
        auto json = juce::JSON::parse(jsonStr);
        if (auto* obj = json.getDynamicObject())
        {
            update.requestId = obj->getProperty("request_id").toString();
            update.step = obj->getProperty("step").toString();
            update.percent = obj->getProperty("percent");
            update.message = obj->getProperty("message").toString();
        }
        
        return update;
    }
};

//==============================================================================
/**
    Error response from server.
*/
struct ErrorResponse
{
    juce::String requestId;         // Correlates with original request
    int code = 0;
    juce::String message;
    bool recoverable = true;
    
    static ErrorResponse fromJson(const juce::String& jsonStr)
    {
        ErrorResponse error;
        
        auto json = juce::JSON::parse(jsonStr);
        if (auto* obj = json.getDynamicObject())
        {
            error.requestId = obj->getProperty("request_id").toString();
            error.code = obj->getProperty("code");
            error.message = obj->getProperty("message").toString();
            error.recoverable = obj->getProperty("recoverable");
        }
        
        return error;
    }
};

//==============================================================================
/**
    Request to analyze an audio reference (local file path or URL).

    This is used by the /analyze endpoint.
*/
struct AnalyzeRequest
{
    juce::String requestId;         // UUID for request/response correlation
    int schemaVersion = SCHEMA_VERSION;
    juce::String path;              // Local file path (optional)
    juce::String url;               // URL (optional)
    bool verbose = false;

    void generateRequestId()
    {
        requestId = juce::Uuid().toString();
    }

    juce::String toJson() const
    {
        juce::DynamicObject::Ptr obj = new juce::DynamicObject();

        obj->setProperty("request_id", requestId);
        obj->setProperty("schema_version", schemaVersion);
        obj->setProperty("path", path);
        obj->setProperty("url", url);
        obj->setProperty("verbose", verbose);

        return juce::JSON::toString(juce::var(obj.get()), true);
    }
};

//==============================================================================
/**
    Result from /analyze.

    The full analysis is returned in JSON; this struct extracts common fields
    for quick UI display.
*/
struct AnalyzeResult
{
    juce::String requestId;
    bool success = false;

    // Convenience fields
    float bpm = 0.0f;
    float bpmConfidence = 0.0f;
    juce::String key;
    juce::String mode;
    float keyConfidence = 0.0f;
    juce::String estimatedGenre;
    float genreConfidence = 0.0f;
    juce::String promptHints;
    juce::StringArray styleTags;

    // Full JSON for advanced UI usage
    juce::String rawJson;

    static AnalyzeResult fromJson(const juce::String& jsonStr)
    {
        AnalyzeResult result;
        result.rawJson = jsonStr;

        auto json = juce::JSON::parse(jsonStr);
        if (!json.isObject())
            return result;

        auto* obj = json.getDynamicObject();
        if (!obj)
            return result;

        result.requestId = obj->getProperty("request_id").toString();
        result.success = obj->getProperty("success");
        result.promptHints = obj->getProperty("prompt_hints").toString();

        if (auto analysis = obj->getProperty("analysis"); analysis.isObject())
        {
            auto* a = analysis.getDynamicObject();
            if (a)
            {
                result.bpm = (float) a->getProperty("bpm");
                result.bpmConfidence = (float) a->getProperty("bpm_confidence");
                result.key = a->getProperty("key").toString();
                result.mode = a->getProperty("mode").toString();
                result.keyConfidence = (float) a->getProperty("key_confidence");
                result.estimatedGenre = a->getProperty("estimated_genre").toString();
                result.genreConfidence = (float) a->getProperty("genre_confidence");

                if (auto tags = a->getProperty("style_tags"); tags.isArray())
                {
                    for (int i = 0; i < tags.size(); ++i)
                        result.styleTags.add(tags[i].toString());
                }
            }
        }

        return result;
    }
};

//==============================================================================
/**
    Represents a single take lane for a track.
*/
struct TakeLane
{
    juce::String takeId;
    juce::String track;             // Track name (e.g., "drums", "bass")
    int seed = 0;
    juce::String variationType;     // "rhythm", "pitch", "timing", "combined", etc.
    juce::String midiPath;          // Path to take MIDI file
    
    static TakeLane fromJson(const juce::var& json)
    {
        TakeLane lane;
        if (auto* obj = json.getDynamicObject())
        {
            lane.takeId = obj->getProperty("take_id").toString();
            lane.track = obj->getProperty("track").toString();
            lane.seed = obj->getProperty("seed");
            lane.variationType = obj->getProperty("variation_type").toString();
            lane.midiPath = obj->getProperty("midi_path").toString();
        }
        return lane;
    }
};

//==============================================================================
/**
    Request to select a specific take for a track.
*/
struct TakeSelectRequest
{
    juce::String requestId;
    juce::String track;
    juce::String takeId;
    
    void generateRequestId()
    {
        requestId = juce::Uuid().toString();
    }
    
    juce::String toJson() const
    {
        juce::DynamicObject::Ptr obj = new juce::DynamicObject();
        obj->setProperty("request_id", requestId);
        obj->setProperty("track", track);
        obj->setProperty("take_id", takeId);
        return juce::JSON::toString(juce::var(obj.get()), true);
    }
};

//==============================================================================
/**
    Represents a comp region (bar range mapped to a take).
*/
struct CompRegion
{
    int startBar = 0;
    int endBar = 4;
    juce::String takeId;
    
    juce::var toJson() const
    {
        juce::DynamicObject::Ptr obj = new juce::DynamicObject();
        obj->setProperty("start_bar", startBar);
        obj->setProperty("end_bar", endBar);
        obj->setProperty("take_id", takeId);
        return juce::var(obj.get());
    }
};

//==============================================================================
/**
    Request to composite takes across bar regions.
*/
struct TakeCompRequest
{
    juce::String requestId;
    juce::String track;
    std::vector<CompRegion> regions;
    
    void generateRequestId()
    {
        requestId = juce::Uuid().toString();
    }
    
    juce::String toJson() const
    {
        juce::DynamicObject::Ptr obj = new juce::DynamicObject();
        obj->setProperty("request_id", requestId);
        obj->setProperty("track", track);
        
        juce::Array<juce::var> regionsArray;
        for (const auto& region : regions)
            regionsArray.add(region.toJson());
        obj->setProperty("regions", regionsArray);
        
        return juce::JSON::toString(juce::var(obj.get()), true);
    }
};

//==============================================================================
/**
    Request to render a specific take or comp to audio.
*/
struct TakeRenderRequest
{
    juce::String requestId;
    juce::String track;
    juce::String takeId;
    bool useComp = false;           // If true, render the comp instead
    juce::String outputPath;
    
    void generateRequestId()
    {
        requestId = juce::Uuid().toString();
    }
    
    juce::String toJson() const
    {
        juce::DynamicObject::Ptr obj = new juce::DynamicObject();
        obj->setProperty("request_id", requestId);
        obj->setProperty("track", track);
        obj->setProperty("take_id", takeId);
        obj->setProperty("use_comp", useComp);
        obj->setProperty("output_path", outputPath);
        return juce::JSON::toString(juce::var(obj.get()), true);
    }
};

//==============================================================================
/**
    OSC address constants (must match Python backend).
*/
namespace OSCAddresses
{
    // Client → Server
    static constexpr const char* generate = "/generate";
    static constexpr const char* regenerate = "/regenerate";
    static constexpr const char* controlsSet = "/controls/set";
    static constexpr const char* controlsClear = "/controls/clear";
    static constexpr const char* cancel = "/cancel";
    static constexpr const char* analyze = "/analyze";
    static constexpr const char* fxChain = "/fx_chain";   // Send FX chain for render parity
    static constexpr const char* getInstruments = "/instruments";
    static constexpr const char* ping = "/ping";
    static constexpr const char* shutdown = "/shutdown";
    
    // Take management (Client → Server)
    static constexpr const char* selectTake = "/take/select";
    static constexpr const char* compTakes = "/take/comp";
    static constexpr const char* renderTake = "/take/render";
    
    // Expansion management (Client → Server)
    static constexpr const char* expansionList = "/expansion/list";
    static constexpr const char* expansionInstruments = "/expansion/instruments";
    static constexpr const char* expansionResolve = "/expansion/resolve";
    static constexpr const char* expansionImport = "/expansion/import";
    static constexpr const char* expansionScan = "/expansion/scan";
    static constexpr const char* expansionEnable = "/expansion/enable";
    
    // Server → Client
    static constexpr const char* progress = "/progress";
    static constexpr const char* complete = "/complete";
    static constexpr const char* analyzeResult = "/analyze_result";
    static constexpr const char* error = "/error";
    static constexpr const char* pong = "/pong";
    static constexpr const char* status = "/status";
    static constexpr const char* instrumentsLoaded = "/instruments_loaded";
    
    // Take responses (Server → Client)
    static constexpr const char* takesAvailable = "/takes/available";
    static constexpr const char* takeSelected = "/take/selected";
    static constexpr const char* takeRendered = "/take/rendered";
    
    // Expansion responses (Server → Client)
    static constexpr const char* expansionListResponse = "/expansion/list_response";
    static constexpr const char* expansionInstrumentsResponse = "/expansion/instruments_response";
    static constexpr const char* expansionInstrumentsChunk = "/expansion/instruments_chunk";
    static constexpr const char* expansionResolveResponse = "/expansion/resolve_response";
}
