"""Focused tests for the minimal non-rock guitar attack-sample hybrid layer.

The hybrid attack is OFF by default (opt-in): a present asset must not force
hybrid in normal renders. These cover default-off identity (even with an asset),
explicit enable mixing a bounded transient, recording so a render cannot be
reported as pure procedural, and finite/bounded/float32 output.
"""

import numpy as np
import soundfile as sf

from multimodal_gen.audio_renderer import ProceduralRenderer, SynthNote
from multimodal_gen.assets_gen import generate_guitar_tone


def _renderer(tmp_attack_dir=None, enable_hybrid=False):
    r = ProceduralRenderer(sample_rate=44100, genre="funk")  # non-rock genre
    if tmp_attack_dir is not None:
        r._attack_layer_dir = str(tmp_attack_dir)
    if enable_hybrid:
        r._hybrid_attack_on = True
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
    r = _renderer(tmp_path, enable_hybrid=True)  # enabled but no asset -> identity
    proc = generate_guitar_tone(196.0, 0.4, 0.8, 44100, drive=0.45)
    out = r._apply_attack_layer("guitar", proc, 0.8)
    assert np.array_equal(out, proc)


def test_default_off_present_asset_is_identity(tmp_path):
    # A present asset must NOT engage hybrid unless explicitly enabled.
    _write_attack(tmp_path)
    r = _renderer(tmp_path)  # hybrid off by default
    proc = generate_guitar_tone(196.0, 0.4, 0.85, 44100, drive=0.45)
    out = r._apply_attack_layer("guitar", proc, 0.85)
    assert np.array_equal(out, proc)
    assert not getattr(r, "_hybrid_attack_families", set())


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
    r = _renderer(tmp_path, enable_hybrid=True)
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
    r = _renderer(tmp_path, enable_hybrid=True)
    proc = generate_guitar_tone(196.0, 0.4, 0.0, 44100, drive=0.45)
    out = r._apply_attack_layer("guitar", proc, 0.0)
    assert np.all(np.isfinite(out))
    assert np.max(np.abs(out)) <= 1.0


# --- shipped self-owned asset: OFF by default, engages only when enabled ------

def _rms(x, lo, hi, sr=44100):
    x = np.asarray(x, dtype=np.float64)
    return float(np.sqrt(np.mean(x[int(lo * sr):int(hi * sr)] ** 2)))


def test_shipped_asset_off_by_default_is_identity():
    # Shipped asset is present, but hybrid is off by default -> pure procedural.
    r = ProceduralRenderer(sample_rate=44100, genre="funk")
    assert r._load_attack_layer("guitar") is not None  # asset exists
    proc = generate_guitar_tone(196.0, 0.4, 0.85, 44100, drive=0.72,
                                voice=r._resolve_patch_voice("guitar"))
    out = r._apply_attack_layer("guitar", proc, 0.85)
    assert np.array_equal(out, proc)
    assert not getattr(r, "_hybrid_attack_families", set())


def test_nonrock_guitar_render_default_off_no_hybrid():
    # KEY acceptance: a normal non-rock guitar render must not engage hybrid.
    r = ProceduralRenderer(sample_rate=44100, genre="funk")
    note = SynthNote(pitch=52, start_sample=0, duration_samples=int(0.4 * 44100),
                     velocity=0.8, channel=2, program=30)
    rendered = r._synthesize_note(note)
    freq = 440 * (2 ** ((52 - 69) / 12))
    expected = generate_guitar_tone(freq, note.duration_samples / 44100, 0.8, 44100,
                                    drive=0.72, voice=r._resolve_patch_voice("guitar"))
    assert np.array_equal(rendered, expected)
    assert not getattr(r, "_hybrid_attack_families", set())


def test_shipped_asset_engages_when_enabled():
    r = ProceduralRenderer(sample_rate=44100, genre="funk")
    r._hybrid_attack_on = True  # explicit opt-in
    proc = generate_guitar_tone(196.0, 0.4, 0.85, 44100, drive=0.72,
                                voice=r._resolve_patch_voice("guitar"))
    hybrid = r._apply_attack_layer("guitar", proc, 0.85)
    assert hybrid.dtype == np.float32
    assert np.all(np.isfinite(hybrid))
    assert np.max(np.abs(hybrid)) <= 1.0
    assert not np.array_equal(hybrid, proc)
    assert "guitar" in r._hybrid_attack_families
    assert _rms(hybrid, 0.0, 0.010) > _rms(proc, 0.0, 0.010)


def test_shipped_asset_when_enabled_does_not_regress_short_note_release():
    r = ProceduralRenderer(sample_rate=44100, genre="funk")
    r._hybrid_attack_on = True
    proc = generate_guitar_tone(196.0, 0.06, 0.75, 44100, drive=0.72,
                                voice=r._resolve_patch_voice("guitar"))
    hybrid = r._apply_attack_layer("guitar", proc, 0.75)
    tail = float(np.mean(np.abs(np.asarray(hybrid, np.float64)[-int(0.003 * 44100):])))
    peak = float(np.max(np.abs(hybrid))) or 1.0
    assert tail / peak < 0.05
