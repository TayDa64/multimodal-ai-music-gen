"""Sprint 8 Batch A tests: sidechain ducking wiring (8.1) + TrackProcessor per-stem (8.2)."""

import os
import sys
import tempfile
import numpy as np
import pytest

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ---------------------------------------------------------------------------
# Test 8.2: _HAS_TRACK_PROCESSOR flag and TRACK_PRESETS importable
# ---------------------------------------------------------------------------

def test_track_processor_initialized():
    """AudioRenderer must have _track_processor as a TrackProcessor instance."""
    from multimodal_gen.audio_renderer import AudioRenderer, _HAS_TRACK_PROCESSOR, TRACK_PRESETS
    from multimodal_gen.track_processor import TrackProcessor

    assert _HAS_TRACK_PROCESSOR is True
    assert len(TRACK_PRESETS) > 10
    renderer = AudioRenderer(use_fluidsynth=False, genre='trap')
    assert hasattr(renderer, '_track_processor')
    assert renderer._track_processor is not None
    assert isinstance(renderer._track_processor, TrackProcessor)


# ---------------------------------------------------------------------------
# Test 8.1: apply_sidechain_ducking handles mono and stereo
# ---------------------------------------------------------------------------

def test_sidechain_handles_mono_stereo():
    """apply_sidechain_ducking should preserve shape for both mono and stereo."""
    from multimodal_gen.audio_renderer import apply_sidechain_ducking

    sr = 44100
    n = sr  # 1 second

    # Mono
    mono = np.random.randn(n).astype(np.float32) * 0.5
    trigger = np.random.randn(n).astype(np.float32) * 0.5
    out_mono = apply_sidechain_ducking(mono, trigger, sample_rate=sr)
    assert out_mono.shape == mono.shape, f"Mono shape mismatch: {out_mono.shape} vs {mono.shape}"

    # Stereo (process per-channel, as the wiring does)
    stereo = np.random.randn(n, 2).astype(np.float32) * 0.5
    for ch in range(2):
        out_ch = apply_sidechain_ducking(stereo[:, ch], trigger, sample_rate=sr)
        assert out_ch.shape == stereo[:, ch].shape


# ---------------------------------------------------------------------------
# Test 8.2: preset selection logic
# ---------------------------------------------------------------------------

def test_track_processor_preset_selection():
    """Verify production genre→preset mapping via monkeypatch spy."""
    from unittest.mock import patch
    from multimodal_gen.audio_renderer import AudioRenderer
    from multimodal_gen.track_processor import TrackProcessor, TRACK_PRESETS

    call_log = []
    _original = TrackProcessor.process_with_preset

    def _spy(self_tp, audio, preset_name):
        call_log.append(preset_name)
        return _original(self_tp, audio, preset_name)

    with patch.object(TrackProcessor, 'process_with_preset', _spy):
        renderer = AudioRenderer(use_fluidsynth=False, genre='trap')
        with tempfile.TemporaryDirectory() as td:
            midi_path = os.path.join(td, 'test.mid')
            out_path = os.path.join(td, 'out.wav')
            _make_test_midi(midi_path, [('Drums', True), ('808 Bass', False)])
            try:
                renderer._render_procedural(midi_path, out_path, parsed=None)
            except Exception:
                pass  # Render may fail; wiring is what matters

    assert len(call_log) > 0, 'TrackProcessor.process_with_preset never called for trap'
    # Production mapping for trap: drums→punchy_kick, bass→trap_808
    assert any(p in ('punchy_kick', 'trap_808') for p in call_log), (
        f'Expected punchy_kick or trap_808 in presets, got {call_log}'
    )
    for preset in call_log:
        assert preset in TRACK_PRESETS, f'Unknown preset {preset!r} used'


# ---------------------------------------------------------------------------
# Helper: build a minimal MIDI with mido for render tests
# ---------------------------------------------------------------------------

def _make_test_midi(path, track_names=None):
    """Create a minimal MIDI with drum + bass tracks."""
    import mido

    if track_names is None:
        track_names = [("Drums", True), ("Bass", False)]

    mid = mido.MidiFile(ticks_per_beat=480)
    for tname, is_drums in track_names:
        trk = mido.MidiTrack()
        mid.tracks.append(trk)
        trk.append(mido.MetaMessage('track_name', name=tname, time=0))
        ch = 9 if is_drums else 0
        note = 36 if is_drums else 40
        trk.append(mido.Message('note_on', note=note, velocity=100, time=0, channel=ch))
        trk.append(mido.Message('note_off', note=note, velocity=0, time=480, channel=ch))
    mid.save(path)


# ---------------------------------------------------------------------------
# Test 8.1: sidechain ducking called for trap
# ---------------------------------------------------------------------------

def test_sidechain_ducking_called_for_trap():
    """Sidechain ducking must be called during _render_procedural for genre=trap."""
    import multimodal_gen.audio_renderer as ar_mod
    from multimodal_gen.audio_renderer import AudioRenderer

    call_log = []
    _original = ar_mod.apply_sidechain_ducking

    def _spy(*args, **kwargs):
        call_log.append((args, kwargs))
        return _original(*args, **kwargs)

    ar_mod.apply_sidechain_ducking = _spy
    try:
        renderer = AudioRenderer(use_fluidsynth=False, genre='trap')
        with tempfile.TemporaryDirectory() as td:
            midi_path = os.path.join(td, "test.mid")
            out_path = os.path.join(td, "out.wav")
            _make_test_midi(midi_path, [("Drums", True), ("808 Bass", False)])
            try:
                renderer._render_procedural(midi_path, out_path, parsed=None)
            except Exception:
                pass  # Render may fail (no soundfont etc), wiring is what matters
        assert len(call_log) > 0, "apply_sidechain_ducking was never called for genre=trap"
    finally:
        ar_mod.apply_sidechain_ducking = _original


# ---------------------------------------------------------------------------
# Test 8.1: sidechain NOT called for jazz
# ---------------------------------------------------------------------------

def test_sidechain_not_called_for_jazz():
    """Sidechain ducking must NOT be called for genre=jazz, and render must succeed."""
    import multimodal_gen.audio_renderer as ar_mod
    from multimodal_gen.audio_renderer import AudioRenderer, apply_sidechain_ducking

    call_log = []
    _original = apply_sidechain_ducking

    def _spy(*args, **kwargs):
        call_log.append(1)
        return _original(*args, **kwargs)

    ar_mod.apply_sidechain_ducking = _spy
    try:
        renderer = AudioRenderer(use_fluidsynth=False, genre='jazz')
        with tempfile.TemporaryDirectory() as td:
            midi_path = os.path.join(td, 'test.mid')
            out_path = os.path.join(td, 'out.wav')
            _make_test_midi(midi_path, [('Drums', True), ('Bass', False)])
            result = renderer._render_procedural(midi_path, out_path, parsed=None)
        assert result is True, 'Render must succeed for test to be valid'
        assert len(call_log) == 0, 'Sidechain should not be called for jazz'
    finally:
        ar_mod.apply_sidechain_ducking = _original


# ---------------------------------------------------------------------------
# Test 8.2: TrackProcessor.process_with_preset called in renderer
# ---------------------------------------------------------------------------

def test_track_processor_called_in_renderer():
    """TrackProcessor.process_with_preset must be called during render."""
    from unittest.mock import patch, MagicMock
    from multimodal_gen.audio_renderer import AudioRenderer
    from multimodal_gen.track_processor import TrackProcessor, TRACK_PRESETS

    call_log = []
    _original = TrackProcessor.process_with_preset

    def _spy(self_tp, audio, preset_name):
        call_log.append(preset_name)
        return _original(self_tp, audio, preset_name)

    with patch.object(TrackProcessor, 'process_with_preset', _spy):
        renderer = AudioRenderer(use_fluidsynth=False, genre='trap')
        with tempfile.TemporaryDirectory() as td:
            midi_path = os.path.join(td, "test.mid")
            out_path = os.path.join(td, "out.wav")
            _make_test_midi(midi_path, [("Drums", True), ("Bass", False)])
            try:
                renderer._render_procedural(midi_path, out_path, parsed=None)
            except Exception:
                pass

    assert len(call_log) > 0, "TrackProcessor.process_with_preset was never called"
    for preset in call_log:
        assert preset in TRACK_PRESETS, f"Unknown preset {preset!r} used"
