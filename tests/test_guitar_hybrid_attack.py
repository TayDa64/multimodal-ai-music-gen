"""Focused tests for the minimal non-rock guitar attack-sample hybrid layer.

Covers the spike acceptance points: absent asset is a byte-identical no-op
(pure procedural stays the reference of truth), present asset mixes a bounded
transient and is recorded so the render cannot be reported as pure procedural,
and outputs stay finite/bounded/float32.
"""

import numpy as np
import soundfile as sf

from multimodal_gen.audio_renderer import ProceduralRenderer, SynthNote
from multimodal_gen.assets_gen import generate_guitar_tone


def _renderer(tmp_attack_dir=None):
    r = ProceduralRenderer(sample_rate=44100, genre="funk")  # non-rock genre
    if tmp_attack_dir is not None:
        r._attack_layer_dir = str(tmp_attack_dir)
    return r


def _write_attack(tmp_path, family="guitar"):
    d = tmp_path / family
    d.mkdir(parents=True, exist_ok=True)
    sr = 44100
    n = int(0.02 * sr)
    t = np.arange(n) / sr
    transient = (np.random.default_rng(0).standard_normal(n) * np.exp(-t / 0.004)).astype(np.float32)
    sf.write(str(d / "pick.wav"), transient, sr)
    return tmp_path


# --- absent asset: pure procedural, byte-identical -----------------------------

def test_load_attack_layer_absent_returns_none(tmp_path):
    r = _renderer(tmp_path)  # empty dir, no family subfolder
    assert r._load_attack_layer("guitar") is None


def test_apply_attack_layer_is_identity_without_asset(tmp_path):
    r = _renderer(tmp_path)
    proc = generate_guitar_tone(196.0, 0.4, 0.8, 44100, drive=0.45)
    out = r._apply_attack_layer("guitar", proc, 0.8)
    assert np.array_equal(out, proc)


def test_nonrock_guitar_render_unchanged_without_asset(tmp_path):
    r = _renderer(tmp_path)
    note = SynthNote(pitch=52, start_sample=0, duration_samples=int(0.4 * 44100),
                     velocity=0.8, channel=2, program=30)
    rendered = r._synthesize_note(note)
    freq = 440 * (2 ** ((52 - 69) / 12))
    expected = generate_guitar_tone(freq, note.duration_samples / 44100, 0.8, 44100,
                                    drive=0.72, voice=r._resolve_patch_voice("guitar"))
    assert np.array_equal(rendered, expected)
    assert not getattr(r, "_hybrid_attack_families", set())


# --- present asset: hybrid mix, recorded, valid --------------------------------

def test_load_attack_layer_present_is_normalized_and_capped(tmp_path):
    _write_attack(tmp_path)
    r = _renderer(tmp_path)
    layer = r._load_attack_layer("guitar")
    assert layer is not None
    assert layer.ndim == 1
    assert layer.size <= int(0.06 * 44100)
    assert np.max(np.abs(layer)) <= 1.0 + 1e-9


def test_apply_attack_layer_mixes_and_records(tmp_path):
    _write_attack(tmp_path)
    r = _renderer(tmp_path)
    proc = generate_guitar_tone(196.0, 0.4, 0.85, 44100, drive=0.45)
    out = r._apply_attack_layer("guitar", proc, 0.85)
    assert out.dtype == np.float32
    assert out.shape == proc.shape
    assert np.all(np.isfinite(out))
    assert np.max(np.abs(out)) <= 1.0
    assert not np.array_equal(out, proc)  # transient changed the onset
    assert "guitar" in r._hybrid_attack_families


def test_attack_layer_is_cached(tmp_path):
    _write_attack(tmp_path)
    r = _renderer(tmp_path)
    a = r._load_attack_layer("guitar")
    b = r._load_attack_layer("guitar")
    assert a is b  # cached identity


def test_zero_velocity_still_valid_with_asset(tmp_path):
    _write_attack(tmp_path)
    r = _renderer(tmp_path)
    proc = generate_guitar_tone(196.0, 0.4, 0.0, 44100, drive=0.45)
    out = r._apply_attack_layer("guitar", proc, 0.0)
    assert np.all(np.isfinite(out))
    assert np.max(np.abs(out)) <= 1.0
