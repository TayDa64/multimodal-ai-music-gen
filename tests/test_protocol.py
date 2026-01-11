"""
Protocol Tests for OSC Communication

Tests the OSC message parsing, validation, and request_id correlation
between JUCE client and Python server.
"""

import json
import pytest
import uuid
from unittest.mock import MagicMock, patch

# Add parent directory to path for imports
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from multimodal_gen.server.config import (
    OSCAddresses,
    ErrorCode,
    SCHEMA_VERSION,
    GenerationStep,
)
from multimodal_gen.server.worker import (
    GenerationRequest,
    GenerationResult,
    TaskStatus,
    build_run_generation_kwargs,
)


class TestGenerationRequest:
    """Tests for GenerationRequest dataclass."""
    
    def test_request_creation_with_defaults(self):
        """Test creating a request with default values."""
        request = GenerationRequest(prompt="test beat")
        
        assert request.prompt == "test beat"
        assert request.request_id == ""
        assert request.schema_version == 1
        assert request.bpm == 0
        assert request.key == ""
        assert request.render_audio == True
    
    def test_request_with_request_id(self):
        """Test creating a request with explicit request_id."""
        req_id = str(uuid.uuid4())
        request = GenerationRequest(
            prompt="G-Funk beat",
            request_id=req_id,
            bpm=92,
            key="Cminor"
        )
        
        assert request.request_id == req_id
        assert request.bpm == 92
        assert request.key == "Cminor"
    
    def test_request_to_dict(self):
        """Test serialization to dict."""
        request = GenerationRequest(
            prompt="trap beat",
            request_id="test-123",
            genre="trap",
            bpm=140,
        )
        
        d = request.to_dict()
        
        assert d["prompt"] == "trap beat"
        assert d["request_id"] == "test-123"
        assert d["genre"] == "trap"
        assert d["bpm"] == 140


class TestGenerationResult:
    """Tests for GenerationResult dataclass."""
    
    def test_result_success(self):
        """Test successful result creation."""
        result = GenerationResult(
            task_id="task-001",
            request_id="req-001",
            success=True,
            midi_path="/output/test.mid",
            audio_path="/output/test.wav",
            duration=5.5,
        )
        
        assert result.success == True
        assert result.request_id == "req-001"
        assert result.error_code == 0
    
    def test_result_failure(self):
        """Test failed result creation."""
        result = GenerationResult(
            task_id="task-002",
            request_id="req-002",
            success=False,
            error_code=ErrorCode.GENERATION_FAILED,
            error_message="Test error",
        )
        
        assert result.success == False
        assert result.error_code == ErrorCode.GENERATION_FAILED
        assert result.error_message == "Test error"
    
    def test_result_to_dict_includes_request_id(self):
        """Test that serialization includes request_id for correlation."""
        result = GenerationResult(
            task_id="task-003",
            request_id="req-003",
            success=True,
            midi_path="/test.mid",
        )
        
        d = result.to_dict()
        
        assert "request_id" in d
        assert d["request_id"] == "req-003"
        assert "task_id" in d


class TestSchemaVersion:
    """Tests for schema version handling."""
    
    def test_schema_version_constant_exists(self):
        """Test that SCHEMA_VERSION is defined."""
        assert SCHEMA_VERSION >= 1
    
    def test_generate_payload_schema_version(self):
        """Test that generated payloads include schema_version."""
        request = GenerationRequest(
            prompt="test",
            schema_version=SCHEMA_VERSION
        )
        
        d = request.to_dict()
        assert "schema_version" in d
        assert d["schema_version"] == SCHEMA_VERSION


class TestOSCAddresses:
    """Tests for OSC address constants."""
    
    def test_client_to_server_addresses(self):
        """Test that client->server addresses are defined."""
        assert OSCAddresses.GENERATE == "/generate"
        assert OSCAddresses.REGENERATE == "/regenerate"
        assert OSCAddresses.CANCEL == "/cancel"
        assert OSCAddresses.ANALYZE == "/analyze"
        assert OSCAddresses.FX_CHAIN == "/fx_chain"
        assert OSCAddresses.CONTROLS_SET == "/controls/set"
        assert OSCAddresses.CONTROLS_CLEAR == "/controls/clear"
        assert OSCAddresses.PING == "/ping"
        assert OSCAddresses.SHUTDOWN == "/shutdown"
    
    def test_server_to_client_addresses(self):
        """Test that server->client addresses are defined."""
        assert OSCAddresses.PROGRESS == "/progress"
        assert OSCAddresses.COMPLETE == "/complete"
        assert OSCAddresses.ANALYZE_RESULT == "/analyze_result"
        assert OSCAddresses.ERROR == "/error"
        assert OSCAddresses.PONG == "/pong"
        assert OSCAddresses.STATUS == "/status"
    
    def test_expansion_addresses(self):
        """Test expansion-related addresses."""
        assert OSCAddresses.EXPANSION_LIST == "/expansion/list"
        assert OSCAddresses.EXPANSION_ENABLE == "/expansion/enable"
        assert OSCAddresses.EXPANSION_LIST_RESPONSE == "/expansion/list_response"
    
    def test_take_addresses(self):
        """Test take management addresses."""
        # Client -> Server
        assert OSCAddresses.SELECT_TAKE == "/take/select"
        assert OSCAddresses.COMP_TAKES == "/take/comp"
        assert OSCAddresses.RENDER_TAKE == "/take/render"
        
        # Server -> Client
        assert OSCAddresses.TAKES_AVAILABLE == "/takes/available"
        assert OSCAddresses.TAKE_SELECTED == "/take/selected"
        assert OSCAddresses.TAKE_RENDERED == "/take/rendered"


class TestErrorCodes:
    """Tests for error code constants."""
    
    def test_general_error_codes(self):
        """Test general error codes (1xx)."""
        assert ErrorCode.UNKNOWN == 100
        assert ErrorCode.INVALID_MESSAGE == 101
        assert ErrorCode.MISSING_PARAMETER == 102
        assert ErrorCode.SCHEMA_VERSION_MISMATCH == 103
    
    def test_generation_error_codes(self):
        """Test generation error codes (2xx)."""
        assert ErrorCode.GENERATION_FAILED == 200
        assert ErrorCode.GENERATION_TIMEOUT == 201
        assert ErrorCode.GENERATION_CANCELLED == 202
        assert ErrorCode.INVALID_PROMPT == 203
    
    def test_server_error_codes(self):
        """Test server error codes (9xx)."""
        assert ErrorCode.SERVER_BUSY == 900
        assert ErrorCode.WORKER_CRASHED == 901
        assert ErrorCode.SHUTDOWN_IN_PROGRESS == 902


class TestGenerationSteps:
    """Tests for generation step constants."""
    
    def test_step_names_defined(self):
        """Test that all step names are defined."""
        assert GenerationStep.INITIALIZING == "initializing"
        assert GenerationStep.PARSING == "parsing"
        assert GenerationStep.ARRANGING == "arranging"
        assert GenerationStep.GENERATING_MIDI == "generating_midi"
        assert GenerationStep.RENDERING_AUDIO == "rendering_audio"
        assert GenerationStep.COMPLETE == "complete"
    
    def test_progress_map_values(self):
        """Test that progress map has valid values (0-1)."""
        for step, progress in GenerationStep.PROGRESS_MAP.items():
            assert 0.0 <= progress <= 1.0, f"Progress for {step} out of range"
        
        # Complete should be 1.0
        assert GenerationStep.PROGRESS_MAP[GenerationStep.COMPLETE] == 1.0
        
        # Initializing should be 0.0
        assert GenerationStep.PROGRESS_MAP[GenerationStep.INITIALIZING] == 0.0


class TestRequestIdCorrelation:
    """Tests for request_id correlation across messages."""
    
    def test_progress_message_format(self):
        """Test that progress messages include request_id."""
        progress_json = json.dumps({
            "request_id": "test-req",
            "step": "generating_midi",
            "percent": 0.5,
            "message": "Generating MIDI...",
        })
        
        data = json.loads(progress_json)
        assert "request_id" in data
        assert data["request_id"] == "test-req"


class TestPhase52OptionForwarding:
    def test_build_run_generation_kwargs_includes_controls(self):
        request = GenerationRequest(
            prompt="test",
            genre="g_funk",
            bpm=92,
            key="A",
            duration_bars=8,
            export_mpc=True,
            export_stems=False,
            options={
                "preset": "legendary",
                "style_preset": "g_funk_90s",
                "production_preset": "wide_modern",
                "tension_arc_shape": "linear_build",
                "tension_intensity": 0.75,
                "motif_mode": "on",
                "num_motifs": 3,
                "seed": 123,
            },
        )

        def _progress(step: str, pct: float, msg: str):
            pass

        kwargs = build_run_generation_kwargs(request, output_dir="out", progress_callback=_progress)

        assert kwargs["genre_override"] == "g_funk"
        assert kwargs["bpm_override"] == 92
        assert kwargs["key_override"] == "A"
        assert kwargs["duration_bars"] == 8
        assert kwargs["preset"] == "legendary"
        assert kwargs["style_preset"] == "g_funk_90s"
        assert kwargs["production_preset"] == "wide_modern"
        assert kwargs["tension_arc_shape"] == "linear_build"
        assert kwargs["tension_intensity"] == 0.75
        assert kwargs["motif_mode"] == "on"
        assert kwargs["num_motifs"] == 3
        assert kwargs["seed"] == 123
    
    def test_error_message_format(self):
        """Test that error messages include request_id."""
        error_json = json.dumps({
            "request_id": "test-req",
            "code": ErrorCode.GENERATION_FAILED,
            "message": "Test error",
            "recoverable": True,
        })
        
        data = json.loads(error_json)
        assert "request_id" in data
        assert data["code"] == ErrorCode.GENERATION_FAILED
    
    def test_status_message_format(self):
        """Test that status messages include request_id."""
        status_json = json.dumps({
            "status": "cancelled",
            "task_id": "task-001",
            "request_id": "req-001",
        })
        
        data = json.loads(status_json)
        assert "request_id" in data
        assert data["status"] == "cancelled"


class TestAnalyzeMessages:
    """Tests for analyze request/result format."""
    
    def test_analyze_request_format(self):
        """Test analyze request JSON structure."""
        request = {
            "request_id": str(uuid.uuid4()),
            "schema_version": SCHEMA_VERSION,
            "path": "/path/to/file.wav",
            "url": "",
            "verbose": False,
        }
        
        # Should be valid JSON
        json_str = json.dumps(request)
        parsed = json.loads(json_str)
        
        assert "request_id" in parsed
        assert "schema_version" in parsed
    
    def test_analyze_result_format(self):
        """Test analyze result JSON structure."""
        result = {
            "request_id": "test-analyze-123",
            "schema_version": SCHEMA_VERSION,
            "success": True,
            "source_kind": "file",
            "analysis": {
                "bpm": 120.0,
                "bpm_confidence": 0.85,
                "key": "C",
                "mode": "major",
                "key_confidence": 0.75,
            },
            "prompt_hints": "upbeat electronic track at 120 BPM",
        }
        
        json_str = json.dumps(result)
        parsed = json.loads(json_str)
        
        assert parsed["request_id"] == "test-analyze-123"
        assert parsed["success"] == True
        assert "analysis" in parsed
        assert parsed["analysis"]["bpm"] == 120.0


class TestTakeMessages:
    """Tests for take management message formats."""
    
    def test_select_take_request_format(self):
        """Test take select request JSON structure."""
        request = {
            "request_id": str(uuid.uuid4()),
            "track": "drums",
            "take_id": "take_001",
        }
        
        json_str = json.dumps(request)
        parsed = json.loads(json_str)
        
        assert "request_id" in parsed
        assert "track" in parsed
        assert "take_id" in parsed
    
    def test_comp_takes_request_format(self):
        """Test take comp request JSON structure."""
        request = {
            "request_id": str(uuid.uuid4()),
            "track": "drums",
            "regions": [
                {"start_bar": 0, "end_bar": 4, "take_id": "take_001"},
                {"start_bar": 4, "end_bar": 8, "take_id": "take_002"},
            ],
        }
        
        json_str = json.dumps(request)
        parsed = json.loads(json_str)
        
        assert "request_id" in parsed
        assert "track" in parsed
        assert "regions" in parsed
        assert len(parsed["regions"]) == 2
        assert parsed["regions"][0]["start_bar"] == 0
        assert parsed["regions"][0]["take_id"] == "take_001"
    
    def test_render_take_request_format(self):
        """Test take render request JSON structure."""
        request = {
            "request_id": str(uuid.uuid4()),
            "track": "bass",
            "take_id": "take_003",
            "use_comp": False,
            "output_path": "/output/bass_take.wav",
        }
        
        json_str = json.dumps(request)
        parsed = json.loads(json_str)
        
        assert "request_id" in parsed
        assert "track" in parsed
        assert "take_id" in parsed
        assert "use_comp" in parsed
        assert "output_path" in parsed
    
    def test_take_selected_response_format(self):
        """Test take selected response JSON structure."""
        response = {
            "request_id": "test-req-123",
            "track": "drums",
            "take_id": "take_001",
            "success": True,
        }
        
        json_str = json.dumps(response)
        parsed = json.loads(json_str)
        
        assert parsed["success"] == True
        assert parsed["track"] == "drums"
        assert parsed["take_id"] == "take_001"
    
    def test_takes_available_format(self):
        """Test takes available message format."""
        message = {
            "request_id": "test-req-456",
            "tracks": {
                "drums": [
                    {"take_id": "take_001", "seed": 12345, "variation_type": "rhythm"},
                    {"take_id": "take_002", "seed": 67890, "variation_type": "rhythm"},
                ],
                "bass": [
                    {"take_id": "take_001", "seed": 11111, "variation_type": "pitch"},
                ],
            },
        }
        
        json_str = json.dumps(message)
        parsed = json.loads(json_str)
        
        assert "tracks" in parsed
        assert "drums" in parsed["tracks"]
        assert len(parsed["tracks"]["drums"]) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
