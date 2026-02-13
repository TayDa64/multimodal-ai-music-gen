"""Sprint 7.5 wiring tests — verify 7 orphaned modules are integrated.

Tests use the same patterns as Sprint 6-7:
  - Import-flag verification: check _HAS_X is True when module exists
  - Instance verification: check wired objects are not None on parent class
  - Monkeypatch spy: verify the wired function IS CALLED during generation
  - Functional proof: process audio to show the wiring does real work

Modules under test:
  7.5.1  file_analysis       → main.py
  7.5.2  multiband_dynamics  → audio_renderer.py
  7.5.3  spectral_processing → audio_renderer.py
  7.5.4  reference_matching  → audio_renderer.py
  7.5.5  performance_models + microtiming → midi_generator.py
  7.5.6  stem_separation     → main.py + reference_analyzer.py
"""

import pytest
import random
import numpy as np


# ---------------------------------------------------------------------------
# Helper: 1-second 440 Hz sine wave at 44100 Hz
# ---------------------------------------------------------------------------

def _sine_wave(duration_s: float = 1.0, freq: float = 440.0, sr: int = 44100) -> np.ndarray:
    """Return a mono float32 sine wave."""
    return np.sin(2 * np.pi * freq * np.arange(int(sr * duration_s)) / sr).astype(np.float32)


# ===================================================================
# 7.5.1  file_analysis → main.py
# ===================================================================

class TestFileAnalysisWiring:

    def test_file_analysis_flag(self):
        """main._HAS_FILE_ANALYSIS must be True AND file_analyze_path callable."""
        import main as main_module
        assert hasattr(main_module, '_HAS_FILE_ANALYSIS')
        assert main_module._HAS_FILE_ANALYSIS is True, (
            "file_analysis module must be importable — _HAS_FILE_ANALYSIS should be True"
        )
        # Verify the imported function is actually callable
        assert hasattr(main_module, 'file_analyze_path'), (
            "main must import file_analyze_path when _HAS_FILE_ANALYSIS is True"
        )
        assert callable(main_module.file_analyze_path), (
            "file_analyze_path must be callable"
        )


# ===================================================================
# 7.5.2  multiband_dynamics → audio_renderer.py
# ===================================================================

class TestMultibandDynamicsWiring:

    def test_multiband_dynamics_called_in_renderer(self, monkeypatch):
        """multiband_compress() must be called during procedural render."""
        from multimodal_gen import audio_renderer as ar

        if not ar._HAS_MULTIBAND_DYNAMICS:
            pytest.skip("multiband_dynamics not available")

        calls = []
        original_fn = ar.multiband_compress

        def spy(audio, *a, **kw):
            calls.append({"shape": audio.shape, "preset": kw.get("preset", a[0] if a else None)})
            return original_fn(audio, *a, **kw)

        monkeypatch.setattr(ar, "multiband_compress", spy)

        # Build a minimal MIDI and render it
        import mido, tempfile, os
        mid = mido.MidiFile()
        track = mido.MidiTrack()
        mid.tracks.append(track)
        track.append(mido.Message('note_on', note=60, velocity=80, time=0))
        track.append(mido.Message('note_off', note=60, velocity=0, time=480))
        with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
            mid.save(f.name)
            midi_path = f.name
        wav_path = midi_path.replace('.mid', '.wav')
        try:
            renderer = ar.AudioRenderer(use_fluidsynth=False, genre='trap')
            renderer._render_procedural(midi_path, wav_path)
            assert len(calls) > 0, "multiband_compress was never called in render pipeline"
            assert calls[0]["shape"] is not None
        finally:
            for p in [midi_path, wav_path]:
                if os.path.exists(p):
                    os.unlink(p)

    def test_multiband_dynamics_processes_audio(self):
        """MultibandDynamics.process() must return same-shape, non-zero output."""
        from multimodal_gen.multiband_dynamics import MultibandDynamics, MultibandDynamicsParams

        params = MultibandDynamicsParams()
        processor = MultibandDynamics(params, sample_rate=44100)

        sine = _sine_wave()
        output = processor.process(sine)

        assert output is not None, "MultibandDynamics output should not be None"
        assert output.shape == sine.shape, (
            f"Output shape {output.shape} must match input shape {sine.shape}"
        )
        assert not np.allclose(output, 0), "Output must not be all zeros"


# ===================================================================
# 7.5.3  spectral_processing → audio_renderer.py
# ===================================================================

class TestSpectralProcessingWiring:

    def test_spectral_processing_called_in_renderer(self, monkeypatch):
        """apply_spectral_preset() must be called during procedural render."""
        from multimodal_gen import audio_renderer as ar

        if not ar._HAS_SPECTRAL_PROCESSING:
            pytest.skip("spectral_processing not available")

        calls = []
        original_fn = ar.apply_spectral_preset

        def spy(audio, preset_name, *a, **kw):
            calls.append({"preset": preset_name, "shape": audio.shape})
            return original_fn(audio, preset_name, *a, **kw)

        monkeypatch.setattr(ar, "apply_spectral_preset", spy)

        import mido, tempfile, os
        mid = mido.MidiFile()
        track = mido.MidiTrack()
        mid.tracks.append(track)
        track.append(mido.Message('note_on', note=60, velocity=80, time=0))
        track.append(mido.Message('note_off', note=60, velocity=0, time=480))
        with tempfile.NamedTemporaryFile(suffix='.mid', delete=False) as f:
            mid.save(f.name)
            midi_path = f.name
        wav_path = midi_path.replace('.mid', '.wav')
        try:
            renderer = ar.AudioRenderer(use_fluidsynth=False, genre='trap')
            renderer._render_procedural(midi_path, wav_path)
            assert len(calls) > 0, "apply_spectral_preset was never called in render pipeline"
            assert calls[0]["preset"] is not None, "preset name must be passed"
        finally:
            for p in [midi_path, wav_path]:
                if os.path.exists(p):
                    os.unlink(p)

    def test_resonance_suppressor_wired_in_renderer(self):
        """AudioRenderer must instantiate _resonance_suppressor."""
        from multimodal_gen.audio_renderer import AudioRenderer, _HAS_SPECTRAL_PROCESSING
        assert _HAS_SPECTRAL_PROCESSING is True
        renderer = AudioRenderer()
        assert renderer._resonance_suppressor is not None, (
            "AudioRenderer._resonance_suppressor must be set"
        )

    def test_harmonic_exciter_processes_audio(self):
        """HarmonicExciter.process() must add harmonics — output differs from input."""
        from multimodal_gen.spectral_processing import HarmonicExciter, HarmonicExciterParams

        params = HarmonicExciterParams()
        exciter = HarmonicExciter(params, sample_rate=44100)

        sine = _sine_wave()
        output = exciter.process(sine)

        assert output is not None, "HarmonicExciter output should not be None"
        assert output.shape == sine.shape, (
            f"Output shape {output.shape} must match input shape {sine.shape}"
        )
        # Harmonics added → output must differ from input
        assert not np.allclose(output, sine, atol=1e-6), (
            "HarmonicExciter must change the signal (add harmonics)"
        )


# ===================================================================
# 7.5.4  reference_matching → audio_renderer.py
# ===================================================================

class TestReferenceMatchingWiring:

    def test_reference_matching_dormant_by_default(self):
        """_reference_matcher must be None until set_reference_profile() is called."""
        from multimodal_gen.audio_renderer import AudioRenderer, _HAS_REFERENCE_MATCHING
        assert _HAS_REFERENCE_MATCHING is True, (
            "reference_matching module must be importable"
        )
        renderer = AudioRenderer()
        assert renderer._reference_matcher is None, (
            "_reference_matcher must be None by default (dormant until profile set)"
        )

    def test_reference_matching_set_profile(self):
        """After set_reference_profile(), _reference_matcher must be created."""
        from multimodal_gen.audio_renderer import AudioRenderer
        from multimodal_gen.reference_matching import ReferenceProfile

        renderer = AudioRenderer()
        profile = ReferenceProfile(name="test_reference")
        renderer.set_reference_profile(profile)

        assert renderer._reference_matcher is not None, (
            "_reference_matcher must be set after set_reference_profile()"
        )


# ===================================================================
# 7.5.5  performance_models + microtiming → midi_generator.py
# ===================================================================

class TestPerformanceModelsWiring:

    def test_performance_models_flag(self):
        """midi_generator._HAS_PERFORMANCE_MODELS must be True and imports callable."""
        import multimodal_gen.midi_generator as mg
        assert hasattr(mg, '_HAS_PERFORMANCE_MODELS')
        assert mg._HAS_PERFORMANCE_MODELS is True, (
            "performance_models module must be importable"
        )
        # Verify the imported functions are callable
        assert callable(mg.apply_performance_model), (
            "apply_performance_model must be callable"
        )
        assert callable(mg.get_profile_for_genre), (
            "get_profile_for_genre must be callable"
        )

    def test_performance_humanization_called(self, monkeypatch):
        """apply_performance_model must be called multiple times with valid args."""
        import multimodal_gen.midi_generator as mg
        if not mg._HAS_PERFORMANCE_MODELS:
            pytest.skip("performance_models not available")

        calls = []
        original_fn = mg.apply_performance_model

        def spy(notes, profile, *a, **kw):
            calls.append((len(notes), profile))
            return original_fn(notes, profile, *a, **kw)

        # Patch on the consuming module where the name is bound
        monkeypatch.setattr(mg, "apply_performance_model", spy)

        from multimodal_gen.prompt_parser import PromptParser
        from multimodal_gen.arranger import Arranger
        from multimodal_gen.performance_models import PlayerProfile

        parsed = PromptParser().parse("trap beat 140 bpm")
        arr = Arranger(target_duration_seconds=15.0).create_arrangement(parsed)

        random.seed(42)
        gen = mg.MidiGenerator()
        gen.generate(arr, parsed)

        assert len(calls) > 0, (
            "apply_performance_model was never called — wiring is broken"
        )
        # Must pass non-empty notes
        assert calls[0][0] > 0, (
            "First call to apply_performance_model had 0 notes"
        )
        # Profile must be a PlayerProfile instance
        assert isinstance(calls[0][1], PlayerProfile), (
            f"Profile arg must be PlayerProfile, got {type(calls[0][1])}"
        )
        # Should be called for multiple tracks (drums, bass, chords, lead)
        assert len(calls) >= 2, (
            f"Expected ≥2 calls (multiple tracks), got {len(calls)}"
        )

    def test_microtiming_flag(self):
        """midi_generator._HAS_MICROTIMING must be True and apply_microtiming callable."""
        import multimodal_gen.midi_generator as mg
        assert hasattr(mg, '_HAS_MICROTIMING')
        assert mg._HAS_MICROTIMING is True, (
            "microtiming module must be importable"
        )
        assert callable(mg.apply_microtiming), (
            "apply_microtiming must be callable"
        )


# ===================================================================
# 7.5.6  stem_separation → main.py + reference_analyzer.py
# ===================================================================

class TestStemSeparationWiring:

    def test_stem_separation_flag(self):
        """main._HAS_STEM_SEPARATION must be True and separate_stems callable."""
        import main as main_module
        assert hasattr(main_module, '_HAS_STEM_SEPARATION')
        assert main_module._HAS_STEM_SEPARATION is True, (
            "stem_separation module must be importable — _HAS_STEM_SEPARATION should be True"
        )
        assert callable(main_module.separate_stems), (
            "separate_stems must be importable and callable in main"
        )

    def test_stem_separation_in_analyzer(self):
        """reference_analyzer must gate stem separation inside analyze_file()."""
        import multimodal_gen.reference_analyzer as ra
        assert hasattr(ra, '_HAS_STEM_SEPARATION')
        assert ra._HAS_STEM_SEPARATION is True, (
            "stem_separation must be importable by reference_analyzer"
        )
        # Verify analyze_file exists and references stem separation
        import inspect
        src = inspect.getsource(ra.ReferenceAnalyzer.analyze_file)
        assert '_HAS_STEM_SEPARATION' in src, (
            "analyze_file() must check _HAS_STEM_SEPARATION flag"
        )
