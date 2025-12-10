/*
  ==============================================================================

    Messages.h
    
    Data structures for OSC communication with Python backend.

  ==============================================================================
*/

#pragma once

#include <JuceHeader.h>

//==============================================================================
/**
    Request to generate music from a text prompt.
*/
struct GenerationRequest
{
    juce::String prompt;
    int bpm = 0;                    // 0 = auto-detect
    juce::String key;               // Empty = auto-detect
    juce::String outputDir;
    juce::StringArray instrumentPaths;
    juce::String soundfontPath;
    juce::String referenceUrl;
    bool renderAudio = true;
    bool exportStems = false;
    bool exportMpc = false;
    bool verbose = false;
    
    juce::String toJson() const
    {
        juce::DynamicObject::Ptr obj = new juce::DynamicObject();
        
        obj->setProperty("prompt", prompt);
        obj->setProperty("bpm", bpm);
        obj->setProperty("key", key);
        obj->setProperty("output_dir", outputDir);
        obj->setProperty("soundfont", soundfontPath);
        obj->setProperty("reference_url", referenceUrl);
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
    Result of a generation request.
*/
struct GenerationResult
{
    juce::String taskId;
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
        
        return result;
    }
};

//==============================================================================
/**
    Progress update from generation.
*/
struct ProgressUpdate
{
    juce::String step;
    float percent = 0.0f;
    juce::String message;
    
    static ProgressUpdate fromJson(const juce::String& jsonStr)
    {
        ProgressUpdate update;
        
        auto json = juce::JSON::parse(jsonStr);
        if (auto* obj = json.getDynamicObject())
        {
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
    int code = 0;
    juce::String message;
    bool recoverable = true;
    
    static ErrorResponse fromJson(const juce::String& jsonStr)
    {
        ErrorResponse error;
        
        auto json = juce::JSON::parse(jsonStr);
        if (auto* obj = json.getDynamicObject())
        {
            error.code = obj->getProperty("code");
            error.message = obj->getProperty("message").toString();
            error.recoverable = obj->getProperty("recoverable");
        }
        
        return error;
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
    static constexpr const char* cancel = "/cancel";
    static constexpr const char* analyze = "/analyze";
    static constexpr const char* getInstruments = "/instruments";
    static constexpr const char* ping = "/ping";
    static constexpr const char* shutdown = "/shutdown";
    
    // Server → Client
    static constexpr const char* progress = "/progress";
    static constexpr const char* complete = "/complete";
    static constexpr const char* error = "/error";
    static constexpr const char* pong = "/pong";
    static constexpr const char* status = "/status";
    static constexpr const char* instrumentsLoaded = "/instruments_loaded";
}
