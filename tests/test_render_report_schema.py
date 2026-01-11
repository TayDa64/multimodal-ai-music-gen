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

        # Nested shapes
        assert "available" in data["fluidsynth"]
        assert "enabled" in data["fluidsynth"]
        assert "allowed" in data["fluidsynth"]
        assert "attempted" in data["fluidsynth"]
        assert "success" in data["fluidsynth"]
        assert "skip_reason" in data["fluidsynth"]
        assert "loaded" in data["instrument_library"]
        assert "loaded" in data["expansions"]
