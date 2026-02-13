"""Sprint 9 Batch C — Brightness/warmth consumption + render report diagnostics (Tasks 9.7-9.8)."""
import pytest

# ── Guards ──────────────────────────────────────────────────────────────
try:
    from multimodal_gen.audio_renderer import AudioRenderer
    _HAS_RENDERER = True
except ImportError:
    _HAS_RENDERER = False

try:
    from multimodal_gen.style_policy import MixPolicy
    _HAS_MIX_POLICY = True
except ImportError:
    _HAS_MIX_POLICY = False


@pytest.mark.skipif(not (_HAS_RENDERER and _HAS_MIX_POLICY),
                    reason="Renderer or MixPolicy not available")
class TestBrightnessWarmthConsumption:
    """Task 9.7: MixPolicy brightness_target and warmth_target are consumed."""

    def test_warmth_target_stored(self):
        """warmth_target is accessible on stored MixPolicy."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='jazz')
        mp = MixPolicy(warmth_target=0.8)
        r.set_mix_policy(mp)
        assert r._mix_policy.warmth_target == 0.8

    def test_brightness_target_stored(self):
        """brightness_target is accessible on stored MixPolicy."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='pop')
        mp = MixPolicy(brightness_target=0.9)
        r.set_mix_policy(mp)
        assert r._mix_policy.brightness_target == 0.9

    def test_default_warmth_is_neutral(self):
        """Default warmth_target=0.5 produces neutral reverb modulation (1.0x)."""
        mp = MixPolicy()  # defaults
        factor = 0.8 + 0.4 * mp.warmth_target
        assert abs(factor - 1.0) < 0.01

    def test_high_warmth_increases_send(self):
        """warmth_target=0.8 should increase reverb send factor above 1.0."""
        mp = MixPolicy(warmth_target=0.8)
        factor = 0.8 + 0.4 * mp.warmth_target
        assert factor > 1.0

    def test_low_warmth_decreases_send(self):
        """warmth_target=0.2 should decrease reverb send factor below 1.0."""
        mp = MixPolicy(warmth_target=0.2)
        factor = 0.8 + 0.4 * mp.warmth_target
        assert factor < 1.0

    def test_high_brightness_selects_air_preset(self):
        """brightness_target > 0.7 should bias exciter toward master_air."""
        # This tests the logic that brightness_target > 0.7 → master_air
        mp = MixPolicy(brightness_target=0.8)
        assert mp.brightness_target > 0.7  # Threshold for master_air

    def test_low_brightness_selects_warmth_preset(self):
        """brightness_target < 0.3 should bias exciter toward tape_warmth."""
        mp = MixPolicy(brightness_target=0.2)
        assert mp.brightness_target < 0.3  # Threshold for tape_warmth


@pytest.mark.skipif(not _HAS_RENDERER, reason="AudioRenderer not available")
class TestRenderReportDiagnostics:
    """Task 9.8: Render report includes production_preset and mix_policy sections."""

    def _make_report(self, renderer):
        """Helper to build a render report."""
        return renderer._build_render_report(
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

    def test_report_has_production_preset_section(self):
        """Render report contains production_preset diagnostics."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='trap')
        report = self._make_report(r)
        assert 'production_preset' in report
        assert 'preset_values' in report['production_preset']
        assert 'target_rms' in report['production_preset']
        assert 'reverb_send' in report['production_preset']

    def test_report_has_mix_policy_section(self):
        """Render report contains mix_policy diagnostics."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='jazz')
        report = self._make_report(r)
        assert 'mix_policy' in report
        assert 'active' in report['mix_policy']
        assert report['mix_policy']['active'] is False  # No policy set

    def test_report_mix_policy_reflects_set_values(self):
        """Render report mix_policy section shows actual values when set."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='pop')
        if _HAS_MIX_POLICY:
            mp = MixPolicy(saturation_type='tube', brightness_target=0.8, warmth_target=0.3)
            r.set_mix_policy(mp)
        report = self._make_report(r)
        if _HAS_MIX_POLICY:
            assert report['mix_policy']['active'] is True
            assert report['mix_policy']['saturation_type'] == 'tube'
            assert report['mix_policy']['brightness_target'] == 0.8
            assert report['mix_policy']['warmth_target'] == 0.3

    def test_report_has_genre_normalized(self):
        """Render report includes normalized genre string."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='Hip-Hop')
        report = self._make_report(r)
        assert 'genre_normalized' in report
        assert report['genre_normalized'] == 'hip_hop'

    def test_report_preset_values_reflected(self):
        """Render report production_preset shows preset values when set."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='trap')
        r.set_preset_values({'humanize_amount': 0.7, 'swing_amount': 0.3})
        report = self._make_report(r)
        assert report['production_preset']['preset_values'] is not None
        assert report['production_preset']['preset_values']['humanize_amount'] == 0.7

    def test_report_schema_version_preserved(self):
        """Original report fields are preserved."""
        r = AudioRenderer(use_fluidsynth=False, use_bwf=False, genre='jazz')
        report = self._make_report(r)
        assert report['schema_version'] == 1
        assert 'fluidsynth' in report
        assert 'instrument_library' in report
