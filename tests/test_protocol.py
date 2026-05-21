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
    
    def test_dependency_error_codes(self):
        """Test dependency error codes (6xx)."""
        assert ErrorCode.OPTIONAL_DEPENDENCY_MISSING == 600

    def test_analysis_error_codes(self):
        """Test analysis error codes (7xx)."""
        assert ErrorCode.ANALYZE_FAILED == 700

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
            score_plan={"schema_version": "score_plan_v1", "prompt": "x", "bpm": 120, "key": "C", "mode": "minor", "sections": [{"name": "intro", "type": "intro", "bars": 4}], "tracks": [{"role": "pad", "instrument": "pad"}]},
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
        assert kwargs["score_plan"] == request.score_plan

    def test_build_run_generation_kwargs_honors_separate_minor_mode(self):
        request = GenerationRequest(
            prompt="1990s rock in E minor",
            genre="rock",
            bpm=100,
            key="E",
            mode="minor",
            duration_bars=16,
        )

        def _progress(step: str, pct: float, msg: str):
            pass

        kwargs = build_run_generation_kwargs(
            request,
            output_dir="out",
            progress_callback=_progress,
        )

        assert kwargs["key_override"] == "Em"

    def test_build_run_generation_kwargs_honors_separate_major_mode(self):
        request = GenerationRequest(
            prompt="bright rock in E major",
            genre="rock",
            bpm=100,
            key="Em",
            mode="major",
            duration_bars=16,
        )

        def _progress(step: str, pct: float, msg: str):
            pass

        kwargs = build_run_generation_kwargs(
            request,
            output_dir="out",
            progress_callback=_progress,
        )

        assert kwargs["key_override"] == "E"
    
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

    def test_analyze_result_with_analyzer_field(self):
        """Test that analyze result includes 'analyzer' field for routing transparency."""
        for analyzer_id in ("reference_analyzer", "file_analysis"):
            result = {
                "request_id": "test-routing-001",
                "schema_version": SCHEMA_VERSION,
                "success": True,
                "source_kind": "file",
                "analyzer": analyzer_id,
                "analysis": {"bpm_estimate": 120.0},
                "prompt_hints": "120 BPM track",
                "generation_params": {"bpm": 120.0, "key": "C", "mode": "minor"},
            }
            parsed = json.loads(json.dumps(result))
            assert parsed["analyzer"] == analyzer_id
            assert "generation_params" in parsed

    def test_analyze_result_warnings_field(self):
        """Test that warnings list is present when file_analysis degrades."""
        result = {
            "request_id": "test-warnings-001",
            "schema_version": SCHEMA_VERSION,
            "success": True,
            "source_kind": "file",
            "analyzer": "file_analysis",
            "analysis": {},
            "prompt_hints": "",
            "generation_params": {"bpm": 0.0, "key": "", "mode": ""},
            "warnings": ["librosa not installed; BPM/key estimation skipped"],
        }
        parsed = json.loads(json.dumps(result))
        assert "warnings" in parsed
        assert len(parsed["warnings"]) > 0
        assert "librosa" in parsed["warnings"][0]

    def test_optional_dependency_error_format(self):
        """Test error message for missing optional dependency."""
        error = {
            "request_id": "test-dep-001",
            "code": ErrorCode.OPTIONAL_DEPENDENCY_MISSING,
            "message": "URL analysis requires librosa. Install with: pip install librosa",
            "recoverable": True,
        }
        parsed = json.loads(json.dumps(error))
        assert parsed["code"] == 600
        assert "pip install" in parsed["message"]
        assert parsed["recoverable"] is True


class TestAnalyzeRouting:
    """Tests for /analyze smart routing logic (P2)."""

    def test_file_analysis_handles_midi(self):
        """file_analysis.analyze_path works for MIDI files without librosa."""
        from multimodal_gen.file_analysis import analyze_path, AnalysisResult
        import tempfile, os
        try:
            import mido
        except ImportError:
            pytest.skip("mido not installed")

        # Create a minimal valid MIDI file
        mid = mido.MidiFile()
        track = mido.MidiTrack()
        track.append(mido.MetaMessage('set_tempo', tempo=500000, time=0))
        track.append(mido.Message('note_on', note=60, velocity=80, time=0))
        track.append(mido.Message('note_off', note=60, velocity=0, time=480))
        mid.tracks.append(track)

        with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as f:
            mid.save(f.name)
            tmp_path = f.name

        try:
            result = analyze_path(tmp_path, request_id="test-midi-route")
            assert isinstance(result, AnalysisResult)
            assert result.file_type == "midi"
            assert result.bpm_estimate == 120.0  # 500000 us/beat = 120 BPM
            assert result.request_id == "test-midi-route"
        finally:
            os.unlink(tmp_path)

    def test_file_analysis_handles_audio_without_librosa(self):
        """file_analysis.analyze_path returns loudness/peak for WAV without librosa."""
        from multimodal_gen.file_analysis import analyze_path, AnalysisResult
        import tempfile, os, struct, wave

        # Create a minimal WAV file with a 440 Hz sine
        sr = 44100
        duration = 0.1  # 100ms
        n_samples = int(sr * duration)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            tmp_path = f.name
        with wave.open(tmp_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            import math as _math
            samples = [int(16000 * _math.sin(2 * _math.pi * 440 * i / sr)) for i in range(n_samples)]
            wf.writeframes(struct.pack(f"<{n_samples}h", *samples))

        try:
            result = analyze_path(tmp_path, request_id="test-wav-route")
            assert isinstance(result, AnalysisResult)
            assert result.file_type == "audio"
            assert result.duration_seconds > 0
            assert result.loudness_rms_db < 0  # Should be negative dBFS
            assert result.peak_db < 0
        finally:
            os.unlink(tmp_path)

    def test_file_analysis_result_to_dict_replaces_nan(self):
        """AnalysisResult.to_dict() converts NaN/inf to None for JSON safety."""
        from multimodal_gen.file_analysis import AnalysisResult
        result = AnalysisResult(
            request_id="nan-test",
            file_path="/fake",
            file_type="unknown",
            loudness_rms_db=float("nan"),
            peak_db=float("inf"),
            spectral_centroid_hz=float("-inf"),
        )
        d = result.to_dict()
        assert d["loudness_rms_db"] is None
        assert d["peak_db"] is None
        assert d["spectral_centroid_hz"] is None
        # Should be JSON-serializable
        json.dumps(d)

    def test_error_code_600_is_recoverable(self):
        """ErrorCode.OPTIONAL_DEPENDENCY_MISSING should be recoverable."""
        # The _send_error method marks non-recoverable only for SHUTDOWN_IN_PROGRESS and WORKER_CRASHED
        assert ErrorCode.OPTIONAL_DEPENDENCY_MISSING == 600
        assert ErrorCode.OPTIONAL_DEPENDENCY_MISSING not in (
            ErrorCode.SHUTDOWN_IN_PROGRESS,
            ErrorCode.WORKER_CRASHED,
        )


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

    def test_render_take_request_format_accepts_live_juce_selected_render_shape(self):
        """Trackless use_comp=true directory-output requests are valid transport payloads."""
        request = {
            "request_id": str(uuid.uuid4()),
            "track": "",
            "take_id": "",
            "use_comp": True,
            "output_path": "/output",
        }

        parsed = json.loads(json.dumps(request))

        assert parsed["track"] == ""
        assert parsed["take_id"] == ""
        assert parsed["use_comp"] is True
        assert parsed["output_path"] == "/output"
    
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


def _create_test_osc_server():
    from contextlib import ExitStack
    import types
    from multimodal_gen.server import osc_server as osc_server_module

    class _FakeDispatcher:
        def map(self, *args, **kwargs):
            return None

        def set_default_handler(self, *args, **kwargs):
            return None

    with ExitStack() as stack:
        stack.enter_context(patch.object(osc_server_module, "EXPANSION_AVAILABLE", False))
        if not getattr(osc_server_module, "OSC_AVAILABLE", False):
            stack.enter_context(patch.object(osc_server_module, "OSC_AVAILABLE", True))
            stack.enter_context(
                patch.object(
                    osc_server_module,
                    "dispatcher",
                    types.SimpleNamespace(Dispatcher=_FakeDispatcher),
                    create=True,
                )
            )
        server = osc_server_module.MusicGenOSCServer()

    server._send_message = MagicMock()
    server._log = lambda *args, **kwargs: None
    return server


def _sent_payloads(server, address: str):
    payloads = []
    for call in server._send_message.call_args_list:
        if not call.args or call.args[0] != address:
            continue
        payloads.append(json.loads(call.args[1]))
    return payloads


def _write_take_render_midi(tmp_path: Path, *, include_comp: bool = False) -> Path:
    mido = pytest.importorskip("mido")
    midi_path = tmp_path / "generated_project.mid"

    mid = mido.MidiFile(ticks_per_beat=480)

    def _track(name: str, note: int, channel: int) -> "mido.MidiTrack":
        track = mido.MidiTrack()
        track.append(mido.MetaMessage("track_name", name=name, time=0))
        track.append(mido.Message("program_change", program=0, channel=channel, time=0))
        track.append(mido.Message("note_on", note=note, velocity=100, time=0, channel=channel))
        track.append(mido.Message("note_off", note=note, velocity=0, time=480, channel=channel))
        return track

    meta_track = mido.MidiTrack()
    meta_track.append(mido.MetaMessage("track_name", name="Meta", time=0))
    meta_track.append(mido.MetaMessage("set_tempo", tempo=500000, time=0))
    mid.tracks.append(meta_track)

    mid.tracks.append(_track("Pad", 72, 2))
    mid.tracks.append(_track("Drums_Take_1", 36, 9))
    mid.tracks.append(_track("Drums_Take_2", 38, 9))
    if include_comp:
        mid.tracks.append(_track("Drums_Comp", 40, 9))
    mid.tracks.append(_track("Bass_Take_1", 48, 1))
    mid.tracks.append(_track("Bass_Take_2", 50, 1))

    mid.save(midi_path)
    return midi_path


def _cache_generation_context(server, midi_path: Path, *, request_id: str = "gen-req"):
    request = GenerationRequest(
        prompt="1990s rock with takes",
        request_id=request_id,
        genre="rock",
        output_dir=str(midi_path.parent),
    )
    result = GenerationResult(
        task_id=f"task-{request_id}",
        request_id=request_id,
        success=True,
        midi_path=str(midi_path),
        metadata={"genre": "rock"},
    )

    server._pending_generation_request = request
    server._on_generation_complete(result)
    assert server._last_render_context is not None
    server._send_message.reset_mock()
    return request, result


class TestTakeRenderBackend:
    def test_render_take_without_cached_generation_sends_error_only(self, tmp_path):
        server = _create_test_osc_server()

        request_id = "render-no-cache"
        server._handle_render_take(
            OSCAddresses.RENDER_TAKE,
            json.dumps(
                {
                    "request_id": request_id,
                    "track": "",
                    "take_id": "",
                    "use_comp": True,
                    "output_path": str(tmp_path / "renders"),
                }
            ),
        )

        errors = _sent_payloads(server, OSCAddresses.ERROR)
        rendered = _sent_payloads(server, OSCAddresses.TAKE_RENDERED)

        assert len(errors) == 1
        assert errors[0]["request_id"] == request_id
        assert "No prior successful generation" in errors[0]["message"]
        assert rendered == []

    def test_render_take_renders_whole_project_selected_arrangement(self, tmp_path):
        mido = pytest.importorskip("mido")
        server = _create_test_osc_server()
        midi_path = _write_take_render_midi(tmp_path, include_comp=True)
        _cache_generation_context(server, midi_path, request_id="cached-success")
        server._selected_takes["Bass"] = "take_002"

        captured = {}

        class FakeRenderer:
            def render_midi_file(self, midi_path, output_path, parsed):
                captured["track_names"] = [track.name for track in mido.MidiFile(midi_path).tracks]
                captured["output_path"] = output_path
                Path(output_path).write_bytes(b"RIFF....WAVE")
                return True

        server._create_audio_renderer = MagicMock(return_value=FakeRenderer())

        render_dir = tmp_path / "renders"
        request_id = "render-success"
        server._handle_render_take(
            OSCAddresses.RENDER_TAKE,
            json.dumps(
                {
                    "request_id": request_id,
                    "track": "",
                    "take_id": "",
                    "use_comp": True,
                    "output_path": str(render_dir),
                }
            ),
        )

        errors = _sent_payloads(server, OSCAddresses.ERROR)
        rendered = _sent_payloads(server, OSCAddresses.TAKE_RENDERED)

        assert errors == []
        assert len(rendered) == 1
        assert rendered[0]["request_id"] == request_id
        assert Path(rendered[0]["output_path"]).is_file()
        assert Path(rendered[0]["output_path"]).suffix.lower() == ".wav"
        assert Path(rendered[0]["output_path"]).parent == render_dir
        assert captured["track_names"] == ["Meta", "Pad", "Drums_Comp", "Bass_Take_2"]

    def test_render_take_falls_back_to_take_1_for_unselected_tracks(self, tmp_path):
        mido = pytest.importorskip("mido")
        server = _create_test_osc_server()
        midi_path = _write_take_render_midi(tmp_path, include_comp=False)
        _cache_generation_context(server, midi_path, request_id="cached-fallback")
        server._selected_takes["Bass"] = "2"

        captured = {}

        class FakeRenderer:
            def render_midi_file(self, midi_path, output_path, parsed):
                captured["track_names"] = [track.name for track in mido.MidiFile(midi_path).tracks]
                Path(output_path).write_bytes(b"RIFF....WAVE")
                return True

        server._create_audio_renderer = MagicMock(return_value=FakeRenderer())

        server._handle_render_take(
            OSCAddresses.RENDER_TAKE,
            json.dumps(
                {
                    "request_id": "render-fallback",
                    "track": "",
                    "take_id": "",
                    "use_comp": False,
                    "output_path": str(tmp_path / "fallback-renders"),
                }
            ),
        )

        assert _sent_payloads(server, OSCAddresses.ERROR) == []
        assert captured["track_names"] == ["Meta", "Pad", "Drums_Take_1", "Bass_Take_2"]

    def test_render_take_invalid_requested_take_sends_error_only(self, tmp_path):
        server = _create_test_osc_server()
        midi_path = _write_take_render_midi(tmp_path, include_comp=False)
        _cache_generation_context(server, midi_path, request_id="cached-invalid")

        request_id = "render-invalid-take"
        server._handle_render_take(
            OSCAddresses.RENDER_TAKE,
            json.dumps(
                {
                    "request_id": request_id,
                    "track": "Bass",
                    "take_id": "take_999",
                    "use_comp": False,
                    "output_path": str(tmp_path / "invalid-renders"),
                }
            ),
        )

        errors = _sent_payloads(server, OSCAddresses.ERROR)
        rendered = _sent_payloads(server, OSCAddresses.TAKE_RENDERED)

        assert len(errors) == 1
        assert errors[0]["request_id"] == request_id
        assert "Requested take '999' not found for track 'Bass'" in errors[0]["message"]
        assert rendered == []

    def test_render_take_renderer_failure_sends_error_only(self, tmp_path):
        server = _create_test_osc_server()
        midi_path = _write_take_render_midi(tmp_path, include_comp=False)
        _cache_generation_context(server, midi_path, request_id="cached-render-fail")

        class FakeRenderer:
            def render_midi_file(self, midi_path, output_path, parsed):
                return False

        server._create_audio_renderer = MagicMock(return_value=FakeRenderer())

        request_id = "render-failure"
        server._handle_render_take(
            OSCAddresses.RENDER_TAKE,
            json.dumps(
                {
                    "request_id": request_id,
                    "track": "",
                    "take_id": "",
                    "use_comp": True,
                    "output_path": str(tmp_path / "failed-renders"),
                }
            ),
        )

        errors = _sent_payloads(server, OSCAddresses.ERROR)
        rendered = _sent_payloads(server, OSCAddresses.TAKE_RENDERED)

        assert len(errors) == 1
        assert errors[0]["request_id"] == request_id
        assert "Renderer failed to produce output WAV" in errors[0]["message"]
        assert rendered == []

    @pytest.mark.parametrize("take_id", ["1", "take_001"])
    def test_render_take_normalizes_take_id_formats(self, tmp_path, take_id):
        mido = pytest.importorskip("mido")
        server = _create_test_osc_server()
        midi_path = _write_take_render_midi(tmp_path, include_comp=False)
        _cache_generation_context(server, midi_path, request_id=f"cached-{take_id}")

        captured = {}

        class FakeRenderer:
            def render_midi_file(self, midi_path, output_path, parsed):
                captured["track_names"] = [track.name for track in mido.MidiFile(midi_path).tracks]
                Path(output_path).write_bytes(b"RIFF....WAVE")
                return True

        server._create_audio_renderer = MagicMock(return_value=FakeRenderer())

        server._handle_render_take(
            OSCAddresses.RENDER_TAKE,
            json.dumps(
                {
                    "request_id": f"render-{take_id}",
                    "track": "Bass",
                    "take_id": take_id,
                    "use_comp": False,
                    "output_path": str(tmp_path / f"norm-{take_id}"),
                }
            ),
        )

        assert _sent_payloads(server, OSCAddresses.ERROR) == []
        assert captured["track_names"] == ["Meta", "Pad", "Drums_Take_1", "Bass_Take_1"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
