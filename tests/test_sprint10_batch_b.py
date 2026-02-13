"""Sprint 10 Batch B — LUFS in render report + pipeline stage tracking (Tasks 10.4-10.6)."""
import pytest

# ── Guards ──────────────────────────────────────────────────────────────
try:
    from multimodal_gen.audio_renderer import AudioRenderer, estimate_lufs
    _HAS_RENDERER = True
except ImportError:
    _HAS_RENDERER = False

try:
    from multimodal_gen.style_policy import MixPolicy
    _HAS_MIX_POLICY = True
except ImportError:
    _HAS_MIX_POLICY = False

try:
    import numpy as np
    _HAS_NP = True
except ImportError:
    _HAS_NP = False


@pytest.mark.skipif(not (_HAS_RENDERER and _HAS_NP), reason="Renderer or numpy not available")
class TestEstimateLufs:
    """Task 10.4: estimate_lufs() function works and is wired into report."""

    def test_estimate_lufs_sine(self):
        """Sine wave at 0dBFS should estimate LUFS around -3."""
        # 1kHz sine at full scale
        sr = 44100
        t = np.linspace(0, 1, sr)
        audio = np.sin(2 * np.pi * 1000 * t).astype(np.float64)
        lufs = estimate_lufs(audio, sr)
        assert -10 < lufs < 0  # Should be around -3dBFS for a pure sine

    def test_estimate_lufs_silence(self):
        """Silent audio returns very low LUFS."""
        audio = np.zeros(44100, dtype=np.float64)
        lufs = estimate_lufs(audio, 44100)
        assert lufs <= -60

    def test_estimate_lufs_quiet(self):
        """Quiet audio returns low LUFS."""
        sr = 44100
        t = np.linspace(0, 1, sr)
        audio = np.sin(2 * np.pi * 1000 * t).astype(np.float64) * 0.01
        lufs = estimate_lufs(audio, sr)
        assert lufs < -30


@pytest.mark.skipif(not _HAS_RENDERER, reason="AudioRenderer not available")
class TestPipelineStageTracking:
    """Task 10.5: Pipeline stages tracked in _pipeline_stages dict."""

    def test_pipeline_stages_initialized(self):
        """AudioRenderer has _pipeline_stages attribute."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='trap')
        assert hasattr(r, '_pipeline_stages')
        assert isinstance(r._pipeline_stages, dict)

    def test_render_report_has_pipeline_stages(self):
        """Render report includes pipeline_stages section."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='trap')
        report = r._build_render_report(
            midi_path="test.mid",
            output_path="test.wav",
            parsed=None,
            renderer_path="procedural",
            fluidsynth_allowed=False,
            fluidsynth_attempted=False,
            fluidsynth_success=False,
            fluidsynth_skip_reason="test",
            warnings=[],
        )
        assert 'pipeline_stages' in report
        assert isinstance(report['pipeline_stages'], dict)

    def test_render_report_preserves_existing_sections(self):
        """Sprint 9.8 sections still present after Sprint 10 additions."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='trap')
        report = r._build_render_report(
            midi_path="test.mid",
            output_path="test.wav",
            parsed=None,
            renderer_path="procedural",
            fluidsynth_allowed=False,
            fluidsynth_attempted=False,
            fluidsynth_success=False,
            fluidsynth_skip_reason="test",
            warnings=[],
        )
        # Sprint 9.8 fields
        assert 'production_preset' in report
        assert 'mix_policy' in report
        assert 'genre_normalized' in report
        # Sprint 10.5 fields
        assert 'pipeline_stages' in report
        # Original fields
        assert 'schema_version' in report
        assert report['schema_version'] == 1


@pytest.mark.skipif(not _HAS_RENDERER, reason="AudioRenderer not available")
class TestLufsInReport:
    """Task 10.4: estimate_lufs wired into render report."""

    def test_report_without_file_has_no_lufs(self):
        """Report for non-existent output file has no estimated_lufs."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='trap')
        report = r._build_render_report(
            midi_path="test.mid",
            output_path="nonexistent.wav",
            parsed=None,
            renderer_path="procedural",
            fluidsynth_allowed=False,
            fluidsynth_attempted=False,
            fluidsynth_success=False,
            fluidsynth_skip_reason="test",
            warnings=[],
        )
        # LUFS should not be present (file doesn't exist)
        assert 'estimated_lufs' not in report
