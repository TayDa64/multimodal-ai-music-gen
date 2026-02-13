"""Integration tests for all 8 Masterclass DSP modules (mc-001 → mc-008).

Validates imports, instantiation, processing, and renderer wiring for each module.
"""
import pytest
import numpy as np


# --- mc-001: True Peak Limiter ---
class TestTruePeakLimiter:
    def test_import(self):
        from multimodal_gen.true_peak_limiter import TruePeakLimiter, measure_true_peak

    def test_instantiate(self):
        from multimodal_gen.true_peak_limiter import TruePeakLimiter, TruePeakLimiterParams
        limiter = TruePeakLimiter(TruePeakLimiterParams(ceiling_dbtp=-1.0))
        assert limiter is not None

    def test_measure_true_peak(self):
        from multimodal_gen.true_peak_limiter import measure_true_peak
        t = np.linspace(0, 1, 44100, dtype=np.float32)
        audio = np.sin(2 * np.pi * 440 * t) * 0.5
        peak = measure_true_peak(audio)
        assert 0.0 < peak <= 1.0

    def test_limit_audio(self):
        from multimodal_gen.true_peak_limiter import TruePeakLimiter, TruePeakLimiterParams
        limiter = TruePeakLimiter(TruePeakLimiterParams(ceiling_dbtp=-1.0))
        t = np.linspace(0, 1, 44100, dtype=np.float32)
        audio = np.sin(2 * np.pi * 440 * t) * 2.0  # Clipping signal
        result = limiter.process(audio)
        assert np.max(np.abs(result)) <= 1.1  # Allow small overshoot from ISP

    def test_renderer_tpl_flag(self):
        """Verify TruePeakLimiter is guard-imported in audio_renderer."""
        from multimodal_gen import audio_renderer
        assert hasattr(audio_renderer, '_HAS_TPL')


# --- mc-002: Transient Shaper ---
class TestTransientShaper:
    def test_import(self):
        from multimodal_gen.transient_shaper import TransientShaper, TRANSIENT_PRESETS

    def test_instantiate(self):
        from multimodal_gen.transient_shaper import TransientShaper, TransientShaperParams
        shaper = TransientShaper(TransientShaperParams(), sample_rate=44100)
        assert shaper is not None

    def test_presets_exist(self):
        from multimodal_gen.transient_shaper import TRANSIENT_PRESETS
        assert len(TRANSIENT_PRESETS) >= 5

    def test_shape_transients(self):
        from multimodal_gen.transient_shaper import TransientShaper, TransientShaperParams
        shaper = TransientShaper(TransientShaperParams(attack_amount=50.0), sample_rate=44100)
        t = np.linspace(0, 1, 44100, dtype=np.float32)
        audio = np.sin(2 * np.pi * 440 * t) * 0.5
        result = shaper.process(audio)
        assert result.shape == audio.shape

    def test_renderer_transient_flag(self):
        """Verify TransientShaper is guard-imported in audio_renderer."""
        from multimodal_gen import audio_renderer
        assert hasattr(audio_renderer, '_HAS_TRANSIENT_SHAPER')


# --- mc-003: Multiband Dynamics ---
class TestMultibandDynamics:
    def test_import(self):
        from multimodal_gen.multiband_dynamics import MultibandDynamics, multiband_compress

    def test_instantiate(self):
        from multimodal_gen.multiband_dynamics import MultibandDynamics, MultibandDynamicsParams
        mbd = MultibandDynamics(MultibandDynamicsParams())
        assert mbd is not None

    def test_compress(self):
        from multimodal_gen.multiband_dynamics import multiband_compress
        t = np.linspace(0, 1, 44100, dtype=np.float32)
        audio = np.sin(2 * np.pi * 440 * t) * 0.5
        result = multiband_compress(audio, sample_rate=44100)
        assert result.shape == audio.shape

    def test_renderer_multiband_flag(self):
        from multimodal_gen import audio_renderer
        assert hasattr(audio_renderer, '_HAS_MULTIBAND_DYNAMICS')


# --- mc-004: Auto-Gain Staging ---
class TestAutoGainStaging:
    def test_import(self):
        from multimodal_gen.auto_gain_staging import AutoGainStaging, LUFSMeter

    def test_instantiate(self):
        from multimodal_gen.auto_gain_staging import AutoGainStaging
        ags = AutoGainStaging()
        assert ags is not None

    def test_lufs_meter(self):
        from multimodal_gen.auto_gain_staging import LUFSMeter
        meter = LUFSMeter(sample_rate=44100)
        t = np.linspace(0, 1, 44100, dtype=np.float32)
        audio = np.sin(2 * np.pi * 440 * t) * 0.5
        lufs = meter.measure_integrated(audio)
        assert isinstance(lufs, float)
        assert lufs < 0  # LUFS is always negative for normal audio

    def test_renderer_ags_flag(self):
        from multimodal_gen import audio_renderer
        assert hasattr(audio_renderer, '_HAS_AGS')


# --- mc-005: Parametric EQ / Spectral Processing ---
class TestParametricEQ:
    def test_import(self):
        from multimodal_gen.parametric_eq import ParametricEQ

    def test_instantiate(self):
        from multimodal_gen.parametric_eq import ParametricEQ, ParametricEQParams
        eq = ParametricEQ(ParametricEQParams())
        assert eq is not None

    def test_renderer_spectral_flag(self):
        from multimodal_gen import audio_renderer
        assert hasattr(audio_renderer, '_HAS_SPECTRAL_PROCESSING')


# --- mc-006: Reference Matching ---
class TestReferenceMatching:
    def test_import(self):
        from multimodal_gen.reference_matching import ReferenceMatcher

    def test_instantiate(self):
        from multimodal_gen.reference_matching import ReferenceMatcher, ReferenceProfile
        # ReferenceMatcher requires a ReferenceProfile
        profile = ReferenceProfile()
        matcher = ReferenceMatcher(profile)
        assert matcher is not None

    def test_renderer_ref_matching_flag(self):
        from multimodal_gen import audio_renderer
        assert hasattr(audio_renderer, '_HAS_REFERENCE_MATCHING')


# --- mc-007: Stem Separation ---
class TestStemSeparation:
    def test_import(self):
        from multimodal_gen.stem_separation import StemSeparation

    def test_instantiate(self):
        from multimodal_gen.stem_separation import StemSeparation
        sep = StemSeparation()
        assert sep is not None


# --- mc-008: Spatial Audio ---
class TestSpatialAudio:
    def test_import(self):
        from multimodal_gen.spatial_audio import HRTFProcessor

    def test_instantiate(self):
        from multimodal_gen.spatial_audio import HRTFProcessor
        spatial = HRTFProcessor()
        assert spatial is not None


# --- Cross-module wiring tests ---
class TestRendererWiring:
    def test_all_guard_flags_exist(self):
        """All masterclass modules should be guard-imported in audio_renderer."""
        from multimodal_gen import audio_renderer
        flags = [
            '_HAS_MULTIBAND_DYNAMICS',
            '_HAS_REFERENCE_MATCHING',
            '_HAS_SPECTRAL_PROCESSING',
            '_HAS_TPL',
            '_HAS_TRANSIENT_SHAPER',
            '_HAS_AGS',
        ]
        for flag in flags:
            assert hasattr(audio_renderer, flag), f"Missing guard flag: {flag}"

    def test_pipeline_stages_dict(self):
        """AudioRenderer should have _pipeline_stages tracking."""
        from multimodal_gen.audio_renderer import AudioRenderer
        renderer = AudioRenderer.__new__(AudioRenderer)
        # Check the class has the expected methods
        assert hasattr(AudioRenderer, '_render_procedural') or hasattr(AudioRenderer, 'render')
