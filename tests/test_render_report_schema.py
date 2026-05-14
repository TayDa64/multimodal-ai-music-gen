"""Render report schema regression tests.

These tests avoid actually rendering audio (which can be environment-dependent),
but still ensure the diagnostics payload stays stable and writable.
"""

import json
import sys
import tempfile
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from multimodal_gen.audio_renderer import AudioRenderer
from multimodal_gen.prompt_parser import PromptParser
from multimodal_gen.style_policy import MixPolicy


class TestRenderReportSchema:
    def test_render_report_has_expected_fields(self):
        parsed = PromptParser().parse("g-funk beat 92 bpm in G minor")

        renderer = AudioRenderer(
            sample_rate=44100,
            use_fluidsynth=False,
            soundfont_path=None,
            require_soundfont=False,
            instrument_library=None,
            expansion_manager=None,
            genre=parsed.genre,
            mood=parsed.mood,
            use_bwf=False,
        )

        report = renderer._build_render_report(
            midi_path="dummy.mid",
            output_path="dummy.wav",
            parsed=parsed,
            renderer_path="procedural",
            fluidsynth_allowed=False,
            fluidsynth_attempted=False,
            fluidsynth_success=False,
            fluidsynth_skip_reason="disabled",
            warnings=["test warning"],
        )
        renderer._last_render_report = report

        with tempfile.TemporaryDirectory() as td:
            out_path = str(Path(td) / "render_report.json")
            assert renderer.write_last_render_report(out_path)

            data = json.loads(Path(out_path).read_text(encoding="utf-8"))

        # Top-level required keys
        assert data["schema_version"] == 1
        assert "renderer_path" in data
        assert "midi_path" in data
        assert "output_path" in data
        assert "prompt_meta" in data
        assert "fluidsynth" in data
        assert "soundfont_path" in data
        assert "instrument_library" in data
        assert "expansions" in data
        assert "warnings" in data
        assert "render_status" in data

        # Nested shapes
        assert "available" in data["fluidsynth"]
        assert "enabled" in data["fluidsynth"]
        assert "allowed" in data["fluidsynth"]
        assert "attempted" in data["fluidsynth"]
        assert "success" in data["fluidsynth"]
        assert "skip_reason" in data["fluidsynth"]
        assert "loaded" in data["instrument_library"]
        assert "loaded" in data["expansions"]
        assert "success" in data["render_status"]
        assert "current_stage" in data["render_status"]
        assert "failure" in data["render_status"]

    def test_render_report_includes_mastering_policy_fields(self):
        parsed = PromptParser().parse("neo soul beat 88 bpm in D minor")

        renderer = AudioRenderer(
            sample_rate=44100,
            use_fluidsynth=False,
            soundfont_path=None,
            require_soundfont=False,
            instrument_library=None,
            expansion_manager=None,
            genre=parsed.genre,
            mood=parsed.mood,
            use_bwf=False,
        )
        renderer.set_mix_policy(
            MixPolicy(
                target_lufs=-15.0,
                master_ceiling_db=-0.5,
                stem_headroom_db=-7.0,
                brightness_target=0.34,
                warmth_target=0.78,
            )
        )
        renderer._pipeline_stages["true_peak_limiter"] = "ceiling=-0.5dBTP"

        report = renderer._build_render_report(
            midi_path="dummy.mid",
            output_path="dummy.wav",
            parsed=parsed,
            renderer_path="procedural",
            fluidsynth_allowed=False,
            fluidsynth_attempted=False,
            fluidsynth_success=False,
            fluidsynth_skip_reason="disabled",
            warnings=[],
        )

        assert report["mix_policy"]["target_lufs"] == -15.0
        assert report["mix_policy"]["master_ceiling_db"] == -0.5
        assert report["mix_policy"]["stem_headroom_db"] == -7.0
        assert report["mix_policy"]["brightness_target"] == 0.34
        assert report["mix_policy"]["warmth_target"] == 0.78
        assert report["pipeline_stages"]["true_peak_limiter"] == "ceiling=-0.5dBTP"

    def test_render_report_round_trips_failure_metadata(self, monkeypatch):
        parsed = PromptParser().parse("neo soul beat 88 bpm in D minor")

        renderer = AudioRenderer(
            sample_rate=44100,
            use_fluidsynth=False,
            soundfont_path=None,
            require_soundfont=False,
            instrument_library=None,
            expansion_manager=None,
            genre=parsed.genre,
            mood=parsed.mood,
            use_bwf=False,
        )

        def boom(*_args, **_kwargs):
            raise RuntimeError("synthetic render failure")

        monkeypatch.setattr(renderer, "_render_procedural", boom)

        with tempfile.TemporaryDirectory() as td:
            report_path = Path(td) / "render_report_failure.json"
            success = renderer.render_midi_file("dummy.mid", str(Path(td) / "dummy.wav"), parsed)

            assert success is False
            assert renderer.write_last_render_report(str(report_path))
            data = json.loads(report_path.read_text(encoding="utf-8"))

        failure = data["render_status"]["failure"]
        assert data["render_status"]["success"] is False
        assert data["render_status"]["current_stage"] == "procedural_render"
        assert failure["reason"] == "render_exception"
        assert failure["stage"] == "procedural_render"
        assert failure["exception_type"] == "RuntimeError"
        assert "synthetic render failure" in failure["exception_message"]
        assert "Traceback" in failure["traceback"]


class TestFluidSynthDiagnostics:
    """Focused tests for FluidSynth/SoundFont diagnostics and fail-fast behavior."""

    def test_require_soundfont_fail_fast_when_no_fluidsynth_available(self, monkeypatch):
        """Verify --require-soundfont / require_soundfont=True fails immediately with expected report."""
        parsed = PromptParser().parse("g-funk beat 92 bpm in G minor")

        renderer = AudioRenderer(
            sample_rate=44100,
            use_fluidsynth=True,
            soundfont_path=None,
            require_soundfont=True,
            instrument_library=None,
            expansion_manager=None,
            genre=parsed.genre,
            mood=parsed.mood,
            use_bwf=False,
        )

        # Force FluidSynth unavailable to ensure deterministic test behavior
        renderer.fluidsynth_available = False
        renderer.fluidsynth_version = None

        with tempfile.TemporaryDirectory() as td:
            midi_path = Path(td) / "dummy.mid"
            wav_path = Path(td) / "dummy.wav"
            midi_path.write_bytes(b"MThd\x00\x00\x00\x06\x00\x00\x00\x01\x00\x60MTrk\x00\x00\x00\x04\x00\xff\x2f\x00")

            success = renderer.render_midi_file(str(midi_path), str(wav_path), parsed)

            assert success is False
            assert not wav_path.exists()
            report = renderer.get_last_render_report()
            assert report is not None
            assert report["renderer_path"] == "none"
            assert report["require_soundfont"] is True
            assert report["fluidsynth"]["available"] is False
            assert report["fluidsynth"]["skip_reason"] == "require_soundfont"
            assert report["render_status"]["success"] is False
            assert report["render_status"]["failure"] is not None
            assert report["render_status"]["failure"]["reason"] == "require_soundfont"
            assert len(report["warnings"]) > 0

    def test_fluidsynth_diagnostics_report_structure_when_disabled(self):
        """Verify FluidSynth diagnostics report even when use_fluidsynth=False."""
        parsed = PromptParser().parse("neo soul beat 88 bpm in D minor")

        renderer = AudioRenderer(
            sample_rate=44100,
            use_fluidsynth=False,
            soundfont_path=None,
            require_soundfont=False,
            instrument_library=None,
            expansion_manager=None,
            genre=parsed.genre,
            mood=parsed.mood,
            use_bwf=False,
        )

        report = renderer._build_render_report(
            midi_path="dummy.mid",
            output_path="dummy.wav",
            parsed=parsed,
            renderer_path="procedural",
            fluidsynth_allowed=False,
            fluidsynth_attempted=False,
            fluidsynth_success=False,
            fluidsynth_skip_reason="disabled",
            warnings=[],
        )

        assert report["renderer_path"] == "procedural"
        assert report["soundfont_path"] is None
        assert report["require_soundfont"] is False
        assert "fluidsynth" in report
        assert "available" in report["fluidsynth"]
        assert "version" in report["fluidsynth"]
        assert report["fluidsynth"]["enabled"] is False
        assert report["fluidsynth"]["allowed"] is False
        assert report["fluidsynth"]["attempted"] is False
        assert report["fluidsynth"]["success"] is False
        assert report["fluidsynth"]["skip_reason"] == "disabled"
