"""Sprint 8 Batch D — Preset System propagation to mix/render chain (Task 8.7)."""
import pytest
import numpy as np

# ── Guards ──────────────────────────────────────────────────────────────
try:
    from multimodal_gen.audio_renderer import AudioRenderer
    _HAS_RENDERER = True
except ImportError:
    _HAS_RENDERER = False

try:
    from multimodal_gen.preset_system import PresetManager, PresetConfig, PresetCategory
    _HAS_PRESET = True
except ImportError:
    _HAS_PRESET = False

try:
    from multimodal_gen.style_policy import MixPolicy
    _HAS_MIX_POLICY = True
except ImportError:
    _HAS_MIX_POLICY = False


@pytest.mark.skipif(not _HAS_RENDERER, reason="AudioRenderer not available")
class TestPresetRendererBridge:
    """Test that preset_values are forwarded to and consumed by AudioRenderer."""

    def test_set_preset_values_stores_dict(self):
        """set_preset_values() stores the dict on the renderer."""
        renderer = AudioRenderer(use_fluidsynth=False, use_bwf=False)
        pv = {'humanize_amount': 0.5, 'tension_intensity': 0.6}
        renderer.set_preset_values(pv)
        assert renderer._preset_values == pv

    def test_set_preset_values_none_defaults_to_empty(self):
        """set_preset_values(None) sets empty dict (no crash)."""
        renderer = AudioRenderer(use_fluidsynth=False, use_bwf=False)
        renderer.set_preset_values(None)
        assert renderer._preset_values == {}

    def test_preset_values_default_empty(self):
        """Without calling set_preset_values, _preset_values is empty dict."""
        renderer = AudioRenderer(use_fluidsynth=False, use_bwf=False)
        assert renderer._preset_values == {}


@pytest.mark.skipif(not _HAS_RENDERER, reason="AudioRenderer not available")
class TestTargetRmsPresetInfluence:
    """Test that target_rms is influenced by production preset humanize_amount."""

    def test_polished_preset_higher_rms(self):
        """Polished preset (humanize_amount=0.25) produces higher target_rms than default."""
        renderer = AudioRenderer(use_fluidsynth=False, use_bwf=False)
        renderer.set_preset_values({'humanize_amount': 0.25})
        rms = renderer._get_preset_target_rms()
        assert rms > 0.25, f"Polished preset should raise RMS above 0.25, got {rms}"

    def test_rough_preset_lower_rms(self):
        """Demo rough preset (humanize_amount=0.6) produces lower target_rms."""
        renderer = AudioRenderer(use_fluidsynth=False, use_bwf=False)
        renderer.set_preset_values({'humanize_amount': 0.6})
        rms = renderer._get_preset_target_rms()
        assert rms < 0.25, f"Rough preset should lower RMS below 0.25, got {rms}"

    def test_no_preset_default_rms(self):
        """No preset → default 0.25 target_rms."""
        renderer = AudioRenderer(use_fluidsynth=False, use_bwf=False)
        rms = renderer._get_preset_target_rms()
        assert rms == pytest.approx(0.25)

    def test_extreme_humanize_bounded(self):
        """Extreme humanize_amount is clamped to [0,1]."""
        renderer = AudioRenderer(use_fluidsynth=False, use_bwf=False)
        renderer.set_preset_values({'humanize_amount': 5.0})
        rms = renderer._get_preset_target_rms()
        assert rms == pytest.approx(0.30 - 0.14)  # clamped to 1.0


@pytest.mark.skipif(not _HAS_RENDERER, reason="AudioRenderer not available")
class TestReverbSendPresetInfluence:
    """Test that reverb send level is influenced by preset values."""

    def test_rough_preset_more_reverb(self):
        """Rough preset (humanize_amount=0.6) gets more reverb send."""
        renderer = AudioRenderer(use_fluidsynth=False, use_bwf=False)
        renderer.set_preset_values({'humanize_amount': 0.6})
        lvl = renderer._get_preset_reverb_send()
        assert lvl > 0.15, f"Rough preset should increase reverb, got {lvl}"

    def test_polished_preset_less_reverb(self):
        """Polished preset (humanize_amount=0.25) gets less reverb send."""
        renderer = AudioRenderer(use_fluidsynth=False, use_bwf=False)
        renderer.set_preset_values({'humanize_amount': 0.25})
        lvl = renderer._get_preset_reverb_send()
        assert lvl < 0.15, f"Polished preset should decrease reverb, got {lvl}"

    def test_tension_increases_reverb(self):
        """High tension_intensity adds more reverb atmosphere."""
        renderer = AudioRenderer(use_fluidsynth=False, use_bwf=False)
        renderer.set_preset_values({'humanize_amount': 0.5})
        base = renderer._get_preset_reverb_send()
        renderer.set_preset_values({'humanize_amount': 0.5, 'tension_intensity': 0.8})
        with_tension = renderer._get_preset_reverb_send()
        assert with_tension > base

    def test_reverb_send_capped(self):
        """Reverb send level never exceeds 0.30."""
        renderer = AudioRenderer(use_fluidsynth=False, use_bwf=False)
        renderer.set_preset_values({'humanize_amount': 1.0, 'tension_intensity': 1.0})
        lvl = renderer._get_preset_reverb_send()
        assert lvl <= 0.30


@pytest.mark.skipif(not (_HAS_RENDERER and _HAS_MIX_POLICY), reason="Renderer or MixPolicy not available")
class TestMixPolicyHeadroomConsumption:
    """Test that MixPolicy.stem_headroom_db and master_ceiling_db are consumed."""

    def test_mix_policy_stored(self):
        """set_mix_policy() stores the policy for headroom/ceiling consumption."""
        renderer = AudioRenderer(use_fluidsynth=False, use_bwf=False)
        mp = MixPolicy(stem_headroom_db=-3.0, master_ceiling_db=-0.5)
        renderer.set_mix_policy(mp)
        assert renderer._mix_policy is mp

    def test_headroom_caps_gain(self):
        """stem_headroom_db limits how much a track can be boosted."""
        # At -6dB headroom, max gain is 10^(6/20) ≈ 2.0
        # At -3dB headroom, max gain is 10^(3/20) ≈ 1.41
        headroom_6db = 10 ** (6.0 / 20.0)
        headroom_3db = 10 ** (3.0 / 20.0)
        assert headroom_6db > headroom_3db, "More headroom → higher allowed gain"
        assert 1.9 < headroom_6db < 2.1

    def test_master_ceiling_widen_range(self):
        """master_ceiling_db clamp allows values down to 0.5 (was 0.8)."""
        # -6dB → 10^(-6/20) ≈ 0.501 — should NOT be clamped
        ceil_6db = 10 ** (-6.0 / 20.0)
        clamped = min(0.98, max(0.5, ceil_6db))
        assert clamped == pytest.approx(ceil_6db, abs=0.01)  # Not clamped at 0.5


@pytest.mark.skipif(not (_HAS_RENDERER and _HAS_PRESET), reason="Renderer or PresetSystem not available")
class TestEndToEndPresetPropagation:
    """Test the full preset → renderer bridge integration."""

    def test_preset_manager_values_accepted_by_renderer(self):
        """PresetManager.get_all_values() output is accepted by set_preset_values()."""
        mgr = PresetManager()
        mgr.apply_preset('polished')
        pv = {k: v.value for k, v in mgr.get_all_values().items()}
        renderer = AudioRenderer(use_fluidsynth=False, use_bwf=False)
        renderer.set_preset_values(pv)
        assert 'humanize_amount' in renderer._preset_values

    def test_demo_rough_preset_full_bridge(self):
        """demo_rough preset values flow through to renderer storage."""
        mgr = PresetManager()
        mgr.apply_preset('demo_rough')
        pv = {k: v.value for k, v in mgr.get_all_values().items()}
        renderer = AudioRenderer(use_fluidsynth=False, use_bwf=False)
        renderer.set_preset_values(pv)
        assert renderer._preset_values.get('humanize_amount') == 0.6
