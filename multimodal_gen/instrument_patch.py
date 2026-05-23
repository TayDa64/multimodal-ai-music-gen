"""Shared InstrumentPatch contract and bounded backend registry for Phase 1.

This module is intentionally conservative:
- it provides a real shared Python data contract for patch intent,
- it supports additive backend diagnostics/reporting,
- it does not change JUCE/live runtime behavior.
"""

from __future__ import annotations

import copy
import re
from pathlib import Path
from dataclasses import asdict, dataclass, field
from typing import Iterable, Literal, Optional


class SerializableDataclass:
    """Mixin for dataclass serialization."""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EnvelopeSpec(SerializableDataclass):
    attack_ms: float = 10.0
    decay_ms: float = 80.0
    sustain_level: float = 0.7
    release_ms: float = 200.0
    curve: Literal["linear", "exp"] = "exp"
    amount: float = 1.0


@dataclass
class VelocityMap(SerializableDataclass):
    amp: float = 1.0
    cutoff_delta_hz: float = 0.0
    transient_level: float = 0.0
    noise_level: float = 0.0


@dataclass
class OscillatorSpec(SerializableDataclass):
    algorithm: Literal[
        "sine",
        "triangle",
        "saw",
        "square",
        "pulse",
        "noise",
        "fm",
        "karplus_strong",
    ] = "sine"
    level: float = 1.0
    detune_cents: float = 0.0
    phase_offset: float = 0.0
    duty_cycle: float = 0.5


@dataclass
class FilterSpec(SerializableDataclass):
    mode: Literal["lowpass", "highpass", "bandpass"] = "lowpass"
    cutoff_hz: float = 18000.0
    resonance: float = 0.0
    drive: float = 0.0


@dataclass
class LfoSpec(SerializableDataclass):
    target: Literal["amp", "cutoff", "pitch", "pan"] = "amp"
    shape: Literal["sine", "triangle", "square", "sample_hold"] = "sine"
    rate_hz: float = 0.0
    depth: float = 0.0
    phase_offset: float = 0.0


@dataclass
class NoiseLayerSpec(SerializableDataclass):
    color: Literal["white", "pink", "filtered"] = "filtered"
    level: float = 0.0
    attack_ms: float = 0.0
    decay_ms: float = 20.0
    band_low_hz: float = 200.0
    band_high_hz: float = 6000.0


@dataclass
class TransientLayerSpec(SerializableDataclass):
    source: Literal["pick", "hammer", "click", "breath"] = "pick"
    level: float = 0.0
    duration_ms: float = 10.0
    band_low_hz: float = 400.0
    band_high_hz: float = 5000.0


@dataclass
class SaturationSpec(SerializableDataclass):
    model: Literal["none", "tanh", "soft_clip", "tape"] = "none"
    drive: float = 0.0
    mix: float = 0.0


@dataclass
class SampleLayerSpec(SerializableDataclass):
    source_id: str = ""
    path_hint: str = ""
    root_midi_note: Optional[int] = None
    low_velocity: int = 1
    high_velocity: int = 127
    gain_db: float = 0.0
    start_offset_ms: float = 0.0
    one_shot: bool = False
    category_hint: str = ""


@dataclass
class FallbackBinding(SerializableDataclass):
    gm_program: Optional[int] = None
    category_preferences: list[str] = field(default_factory=list)
    instrument_id_hints: list[str] = field(default_factory=list)
    sample_search_tags: list[str] = field(default_factory=list)
    allow_builtin_synth: bool = True


@dataclass
class PatchProfile(SerializableDataclass):
    family: str
    genre_tags: list[str] = field(default_factory=list)
    brightness: float = 0.5
    warmth: float = 0.5
    punch: float = 0.5
    richness: float = 0.5
    noise_level: float = 0.0
    notes: list[str] = field(default_factory=list)


@dataclass
class SynthesisVoice(SerializableDataclass):
    oscillators: list[OscillatorSpec] = field(default_factory=list)
    amp_envelope: EnvelopeSpec = field(default_factory=EnvelopeSpec)
    filter: Optional[FilterSpec] = None
    filter_envelope: Optional[EnvelopeSpec] = None
    lfos: list[LfoSpec] = field(default_factory=list)
    velocity_map: VelocityMap = field(default_factory=VelocityMap)
    noise_layer: Optional[NoiseLayerSpec] = None
    transient_layer: Optional[TransientLayerSpec] = None
    saturation: Optional[SaturationSpec] = None


@dataclass
class InstrumentPatch(SerializableDataclass):
    patch_id: str
    display_name: str
    track_role: str
    scope: Literal["track"] = "track"
    patch_profile: PatchProfile = field(
        default_factory=lambda: PatchProfile(family="unknown")
    )
    synthesis_voice: Optional[SynthesisVoice] = None
    sample_layers: list[SampleLayerSpec] = field(default_factory=list)
    fallback: FallbackBinding = field(default_factory=FallbackBinding)
    preview_subset_notes: list[str] = field(default_factory=list)
    render_notes: list[str] = field(default_factory=list)


_PHASE1_PREVIEW_NOTES = [
    "Phase 1 backend metadata only; no JUCE/live runtime adapter is applied here.",
    "Any later live preview mapping remains a subset or fallback path, not mastered parity.",
]

_PHASE1_RENDER_NOTES = [
    "Patch metadata is additive reporting only in this phase.",
    "Backend mastered render/export remains the reference audio path.",
]


def _normalize_token(value: str) -> str:
    return "_".join(
        part
        for part in re.split(r"[^a-z0-9]+", str(value or "").strip().lower())
        if part
    )


def _make_voice(
    oscillators: list[OscillatorSpec],
    *,
    amp_envelope: Optional[EnvelopeSpec] = None,
    filter: Optional[FilterSpec] = None,
    filter_envelope: Optional[EnvelopeSpec] = None,
    lfos: Optional[list[LfoSpec]] = None,
    velocity_map: Optional[VelocityMap] = None,
    noise_layer: Optional[NoiseLayerSpec] = None,
    transient_layer: Optional[TransientLayerSpec] = None,
    saturation: Optional[SaturationSpec] = None,
) -> SynthesisVoice:
    return SynthesisVoice(
        oscillators=list(oscillators),
        amp_envelope=amp_envelope or EnvelopeSpec(),
        filter=filter,
        filter_envelope=filter_envelope,
        lfos=list(lfos or []),
        velocity_map=velocity_map or VelocityMap(),
        noise_layer=noise_layer,
        transient_layer=transient_layer,
        saturation=saturation,
    )


def _make_patch(
    *,
    patch_id: str,
    display_name: str,
    track_role: str,
    family: str,
    synthesis_voice: Optional[SynthesisVoice],
    gm_program: Optional[int],
    category_preferences: list[str],
    instrument_id_hints: list[str],
    sample_search_tags: list[str],
    brightness: float,
    warmth: float,
    punch: float,
    richness: float,
    noise_level: float,
    genre_tags: Optional[list[str]] = None,
    notes: Optional[list[str]] = None,
) -> InstrumentPatch:
    profile_notes = list(notes or [])
    return InstrumentPatch(
        patch_id=patch_id,
        display_name=display_name,
        track_role=track_role,
        patch_profile=PatchProfile(
            family=family,
            genre_tags=list(genre_tags or []),
            brightness=brightness,
            warmth=warmth,
            punch=punch,
            richness=richness,
            noise_level=noise_level,
            notes=profile_notes,
        ),
        synthesis_voice=synthesis_voice,
        fallback=FallbackBinding(
            gm_program=gm_program,
            category_preferences=list(category_preferences),
            instrument_id_hints=list(instrument_id_hints),
            sample_search_tags=list(sample_search_tags),
            allow_builtin_synth=True,
        ),
        preview_subset_notes=list(_PHASE1_PREVIEW_NOTES),
        render_notes=list(_PHASE1_RENDER_NOTES),
    )


def _guitar_patch() -> InstrumentPatch:
    return _make_patch(
        patch_id="core.guitar.track.v1",
        display_name="Guitar - Procedural Pluck",
        track_role="chords",
        family="guitar",
        synthesis_voice=_make_voice(
            [
                OscillatorSpec(algorithm="karplus_strong", level=1.0),
                OscillatorSpec(algorithm="sine", level=0.14, detune_cents=1200.0),
            ],
            amp_envelope=EnvelopeSpec(attack_ms=4.0, decay_ms=110.0, sustain_level=0.28, release_ms=150.0),
            filter=FilterSpec(mode="lowpass", cutoff_hz=3200.0, resonance=0.12, drive=0.06),
            velocity_map=VelocityMap(amp=1.0, cutoff_delta_hz=180.0, transient_level=0.10, noise_level=0.04),
            noise_layer=NoiseLayerSpec(color="filtered", level=0.04, attack_ms=0.0, decay_ms=18.0, band_low_hz=300.0, band_high_hz=2800.0),
            transient_layer=TransientLayerSpec(source="pick", level=0.12, duration_ms=12.0, band_low_hz=600.0, band_high_hz=3200.0),
            saturation=SaturationSpec(model="soft_clip", drive=0.10, mix=0.18),
        ),
        gm_program=29,
        category_preferences=["guitar", "strings"],
        instrument_id_hints=["guitar"],
        sample_search_tags=["guitar", "pluck", "electric"],
        brightness=0.58,
        warmth=0.47,
        punch=0.54,
        richness=0.52,
        noise_level=0.05,
        genre_tags=["rock"],
        notes=["Bounded registry entry aligned with the existing procedural guitar family."],
    )


def _keys_patch() -> InstrumentPatch:
    return _make_patch(
        patch_id="core.keys.track.v1",
        display_name="Keys / Piano - Hybrid",
        track_role="chords",
        family="keys",
        synthesis_voice=_make_voice(
            [
                OscillatorSpec(algorithm="triangle", level=0.72),
                OscillatorSpec(algorithm="sine", level=0.28),
            ],
            amp_envelope=EnvelopeSpec(attack_ms=5.0, decay_ms=220.0, sustain_level=0.35, release_ms=280.0),
            filter=FilterSpec(mode="lowpass", cutoff_hz=5600.0, resonance=0.04, drive=0.02),
            velocity_map=VelocityMap(amp=1.0, cutoff_delta_hz=220.0, transient_level=0.08, noise_level=0.01),
            transient_layer=TransientLayerSpec(source="hammer", level=0.08, duration_ms=8.0, band_low_hz=700.0, band_high_hz=4200.0),
            saturation=SaturationSpec(model="tanh", drive=0.04, mix=0.10),
        ),
        gm_program=0,
        category_preferences=["keys", "piano"],
        instrument_id_hints=["keys", "piano"],
        sample_search_tags=["piano", "keys", "rhodes"],
        brightness=0.54,
        warmth=0.58,
        punch=0.38,
        richness=0.50,
        noise_level=0.01,
        genre_tags=["soul", "neo_soul"],
        notes=["Covers bounded piano/keys family reporting for the current backend."],
    )


def _bass_patch() -> InstrumentPatch:
    return _make_patch(
        patch_id="core.bass.track.v1",
        display_name="Bass - Focused Low-End",
        track_role="bass",
        family="bass",
        synthesis_voice=_make_voice(
            [
                OscillatorSpec(algorithm="sine", level=0.74),
                OscillatorSpec(algorithm="triangle", level=0.26),
            ],
            amp_envelope=EnvelopeSpec(attack_ms=3.0, decay_ms=90.0, sustain_level=0.82, release_ms=140.0),
            filter=FilterSpec(mode="lowpass", cutoff_hz=1400.0, resonance=0.08, drive=0.10),
            velocity_map=VelocityMap(amp=1.0, cutoff_delta_hz=120.0, transient_level=0.03, noise_level=0.0),
            saturation=SaturationSpec(model="tanh", drive=0.10, mix=0.14),
        ),
        gm_program=33,
        category_preferences=["bass"],
        instrument_id_hints=["bass"],
        sample_search_tags=["bass", "low_end", "electric_bass"],
        brightness=0.25,
        warmth=0.72,
        punch=0.64,
        richness=0.46,
        noise_level=0.0,
        genre_tags=["rock", "funk", "soul"],
        notes=["Represents the current bounded bass family rather than any live patch-switching path."],
    )


def _synth_patch() -> InstrumentPatch:
    return _make_patch(
        patch_id="core.synth.track.v1",
        display_name="Synth Lead - Bounded Core",
        track_role="melody",
        family="synth",
        synthesis_voice=_make_voice(
            [
                OscillatorSpec(algorithm="saw", level=0.64),
                OscillatorSpec(algorithm="square", level=0.36, detune_cents=5.0),
            ],
            amp_envelope=EnvelopeSpec(attack_ms=8.0, decay_ms=120.0, sustain_level=0.62, release_ms=180.0),
            filter=FilterSpec(mode="lowpass", cutoff_hz=4200.0, resonance=0.20, drive=0.08),
            lfos=[LfoSpec(target="cutoff", shape="triangle", rate_hz=2.6, depth=0.08)],
            velocity_map=VelocityMap(amp=1.0, cutoff_delta_hz=260.0, transient_level=0.04, noise_level=0.0),
            saturation=SaturationSpec(model="soft_clip", drive=0.08, mix=0.16),
        ),
        gm_program=80,
        category_preferences=["synth", "lead"],
        instrument_id_hints=["synth"],
        sample_search_tags=["synth", "lead", "analog"],
        brightness=0.66,
        warmth=0.42,
        punch=0.52,
        richness=0.62,
        noise_level=0.0,
        genre_tags=["g_funk", "house", "pop"],
        notes=["Tracks the bounded synth family used by the current backend."],
    )


def _pad_patch() -> InstrumentPatch:
    return _make_patch(
        patch_id="core.pad.track.v1",
        display_name="Pad - Slow Support Layer",
        track_role="pad",
        family="pad",
        synthesis_voice=_make_voice(
            [
                OscillatorSpec(algorithm="triangle", level=0.58),
                OscillatorSpec(algorithm="saw", level=0.42, detune_cents=7.0),
            ],
            amp_envelope=EnvelopeSpec(attack_ms=80.0, decay_ms=420.0, sustain_level=0.76, release_ms=520.0),
            filter=FilterSpec(mode="lowpass", cutoff_hz=3000.0, resonance=0.08, drive=0.02),
            lfos=[LfoSpec(target="amp", shape="sine", rate_hz=0.35, depth=0.05)],
            velocity_map=VelocityMap(amp=0.9, cutoff_delta_hz=100.0, transient_level=0.0, noise_level=0.0),
            saturation=SaturationSpec(model="tape", drive=0.04, mix=0.10),
        ),
        gm_program=88,
        category_preferences=["pad", "synth"],
        instrument_id_hints=["pad"],
        sample_search_tags=["pad", "warm", "atmospheric"],
        brightness=0.44,
        warmth=0.66,
        punch=0.18,
        richness=0.74,
        noise_level=0.0,
        genre_tags=["ambient", "house"],
        notes=["Bounded pad-family metadata only; no live multi-layer realization is implied."],
    )


def _brass_patch() -> InstrumentPatch:
    return _make_patch(
        patch_id="core.brass.track.v1",
        display_name="Brass - Section Fallback",
        track_role="melody",
        family="brass",
        synthesis_voice=_make_voice(
            [
                OscillatorSpec(algorithm="saw", level=0.70),
                OscillatorSpec(algorithm="square", level=0.30),
            ],
            amp_envelope=EnvelopeSpec(attack_ms=18.0, decay_ms=160.0, sustain_level=0.72, release_ms=220.0),
            filter=FilterSpec(mode="lowpass", cutoff_hz=2600.0, resonance=0.18, drive=0.06),
            velocity_map=VelocityMap(amp=1.0, cutoff_delta_hz=240.0, transient_level=0.05, noise_level=0.02),
            transient_layer=TransientLayerSpec(source="breath", level=0.05, duration_ms=20.0, band_low_hz=500.0, band_high_hz=2400.0),
            saturation=SaturationSpec(model="tanh", drive=0.06, mix=0.10),
        ),
        gm_program=61,
        category_preferences=["brass", "horn"],
        instrument_id_hints=["brass", "trumpet", "trombone"],
        sample_search_tags=["brass", "horn", "section"],
        brightness=0.61,
        warmth=0.46,
        punch=0.63,
        richness=0.55,
        noise_level=0.02,
        genre_tags=["funk", "cinematic"],
        notes=["Provides bounded brass-family intent for reporting and fallback hints."],
    )


def _strings_patch() -> InstrumentPatch:
    return _make_patch(
        patch_id="core.strings.track.v1",
        display_name="Strings - Ensemble Bed",
        track_role="pad",
        family="strings",
        synthesis_voice=_make_voice(
            [
                OscillatorSpec(algorithm="saw", level=0.60),
                OscillatorSpec(algorithm="triangle", level=0.40, detune_cents=4.0),
            ],
            amp_envelope=EnvelopeSpec(attack_ms=25.0, decay_ms=240.0, sustain_level=0.74, release_ms=320.0),
            filter=FilterSpec(mode="lowpass", cutoff_hz=3000.0, resonance=0.10, drive=0.03),
            lfos=[LfoSpec(target="amp", shape="sine", rate_hz=5.0, depth=0.02)],
            velocity_map=VelocityMap(amp=0.95, cutoff_delta_hz=140.0, transient_level=0.0, noise_level=0.01),
        ),
        gm_program=48,
        category_preferences=["strings"],
        instrument_id_hints=["strings", "violin", "cello"],
        sample_search_tags=["strings", "ensemble", "bowed"],
        brightness=0.48,
        warmth=0.62,
        punch=0.22,
        richness=0.78,
        noise_level=0.01,
        genre_tags=["cinematic", "classical"],
        notes=["Represents the bounded strings/orchestral family for backend metadata."],
    )


def _organ_patch() -> InstrumentPatch:
    return _make_patch(
        patch_id="core.organ.track.v1",
        display_name="Organ - Sustained Drawbar Blend",
        track_role="pad",
        family="organ",
        synthesis_voice=_make_voice(
            [
                OscillatorSpec(algorithm="sine", level=0.68),
                OscillatorSpec(algorithm="square", level=0.32),
            ],
            amp_envelope=EnvelopeSpec(attack_ms=2.0, decay_ms=0.0, sustain_level=1.0, release_ms=90.0, curve="linear"),
            filter=FilterSpec(mode="lowpass", cutoff_hz=7800.0, resonance=0.0, drive=0.02),
            lfos=[LfoSpec(target="amp", shape="sine", rate_hz=5.6, depth=0.03)],
            velocity_map=VelocityMap(amp=0.85, cutoff_delta_hz=0.0, transient_level=0.0, noise_level=0.0),
        ),
        gm_program=16,
        category_preferences=["organ", "keys"],
        instrument_id_hints=["organ", "hammond"],
        sample_search_tags=["organ", "hammond", "drawbar"],
        brightness=0.50,
        warmth=0.64,
        punch=0.30,
        richness=0.70,
        noise_level=0.0,
        genre_tags=["classic_rock", "gospel"],
        notes=["Covers the existing organ-family intent without implying live Leslie/mastering parity."],
    )


def _choir_patch() -> InstrumentPatch:
    return _make_patch(
        patch_id="core.choir.track.v1",
        display_name="Choir - Airy Ensemble",
        track_role="pad",
        family="choir",
        synthesis_voice=_make_voice(
            [
                OscillatorSpec(algorithm="triangle", level=0.64),
                OscillatorSpec(algorithm="saw", level=0.36),
            ],
            amp_envelope=EnvelopeSpec(attack_ms=40.0, decay_ms=260.0, sustain_level=0.72, release_ms=380.0),
            filter=FilterSpec(mode="lowpass", cutoff_hz=3400.0, resonance=0.10, drive=0.02),
            noise_layer=NoiseLayerSpec(color="filtered", level=0.02, attack_ms=0.0, decay_ms=70.0, band_low_hz=700.0, band_high_hz=4000.0),
            lfos=[LfoSpec(target="amp", shape="sine", rate_hz=0.45, depth=0.04)],
        ),
        gm_program=52,
        category_preferences=["choir", "pad"],
        instrument_id_hints=["choir"],
        sample_search_tags=["choir", "voices", "ahh"],
        brightness=0.46,
        warmth=0.60,
        punch=0.14,
        richness=0.76,
        noise_level=0.02,
        genre_tags=["cinematic", "ambient"],
        notes=["Bounded choir-family metadata only for reporting/fallback hints."],
    )


def _krar_patch() -> InstrumentPatch:
    return _make_patch(
        patch_id="ethiopian.krar.track.v1",
        display_name="Krar - Warm Ethio-jazz Pluck",
        track_role="melody",
        family="ethiopian_string",
        synthesis_voice=_make_voice(
            [
                OscillatorSpec(algorithm="karplus_strong", level=1.0),
                OscillatorSpec(algorithm="sine", level=0.12, detune_cents=1200.0),
            ],
            amp_envelope=EnvelopeSpec(attack_ms=15.0, decay_ms=140.0, sustain_level=0.32, release_ms=160.0),
            filter=FilterSpec(mode="lowpass", cutoff_hz=2000.0, resonance=0.15, drive=0.04),
            filter_envelope=EnvelopeSpec(attack_ms=0.0, decay_ms=120.0, sustain_level=0.55, release_ms=120.0, amount=350.0),
            velocity_map=VelocityMap(amp=1.0, cutoff_delta_hz=250.0, transient_level=0.10, noise_level=0.05),
            noise_layer=NoiseLayerSpec(color="filtered", level=0.08, attack_ms=0.0, decay_ms=15.0, band_low_hz=300.0, band_high_hz=2200.0),
            transient_layer=TransientLayerSpec(source="pick", level=0.10, duration_ms=15.0, band_low_hz=400.0, band_high_hz=2400.0),
            saturation=SaturationSpec(model="soft_clip", drive=0.08, mix=0.15),
        ),
        gm_program=None,
        category_preferences=["krar", "ethiopian_string", "strings", "guitar"],
        instrument_id_hints=["krar"],
        sample_search_tags=["ethio", "krar", "lyre", "warm_pluck"],
        brightness=0.75,
        warmth=0.60,
        punch=0.50,
        richness=0.70,
        noise_level=0.08,
        genre_tags=["ethio_jazz", "ethiopian_traditional"],
        notes=[
            "Grounded in the current krar-family procedural behavior.",
            "Backend render remains the reference path; live preview mapping is not part of Phase 1.",
        ],
    )


def _masenqo_patch() -> InstrumentPatch:
    return _make_patch(
        patch_id="ethiopian.masenqo.track.v1",
        display_name="Masenqo - Bowed Lead",
        track_role="melody",
        family="ethiopian_string",
        synthesis_voice=_make_voice(
            [
                OscillatorSpec(algorithm="saw", level=0.76),
                OscillatorSpec(algorithm="triangle", level=0.24, detune_cents=3.0),
            ],
            amp_envelope=EnvelopeSpec(attack_ms=22.0, decay_ms=180.0, sustain_level=0.78, release_ms=220.0),
            filter=FilterSpec(mode="lowpass", cutoff_hz=2600.0, resonance=0.14, drive=0.05),
            lfos=[LfoSpec(target="pitch", shape="sine", rate_hz=5.2, depth=0.01)],
            velocity_map=VelocityMap(amp=1.0, cutoff_delta_hz=200.0, transient_level=0.02, noise_level=0.06),
            noise_layer=NoiseLayerSpec(color="filtered", level=0.06, attack_ms=3.0, decay_ms=45.0, band_low_hz=250.0, band_high_hz=2400.0),
            saturation=SaturationSpec(model="tanh", drive=0.06, mix=0.12),
        ),
        gm_program=None,
        category_preferences=["masenqo", "ethiopian_string", "strings"],
        instrument_id_hints=["masenqo"],
        sample_search_tags=["ethio", "masenqo", "bowed"],
        brightness=0.60,
        warmth=0.52,
        punch=0.34,
        richness=0.68,
        noise_level=0.06,
        genre_tags=["ethio_jazz", "ethiopian_traditional"],
        notes=["Captures bounded bowed Ethiopian string intent for backend diagnostics only."],
    )


def _washint_patch() -> InstrumentPatch:
    return _make_patch(
        patch_id="ethiopian.washint.track.v1",
        display_name="Washint - Breathy Reed Flute",
        track_role="melody",
        family="ethiopian_flute",
        synthesis_voice=_make_voice(
            [
                OscillatorSpec(algorithm="sine", level=0.78),
                OscillatorSpec(algorithm="triangle", level=0.22),
            ],
            amp_envelope=EnvelopeSpec(attack_ms=20.0, decay_ms=120.0, sustain_level=0.78, release_ms=180.0),
            filter=FilterSpec(mode="lowpass", cutoff_hz=4200.0, resonance=0.06, drive=0.01),
            lfos=[LfoSpec(target="pitch", shape="sine", rate_hz=4.8, depth=0.01)],
            velocity_map=VelocityMap(amp=1.0, cutoff_delta_hz=180.0, transient_level=0.04, noise_level=0.08),
            noise_layer=NoiseLayerSpec(color="filtered", level=0.08, attack_ms=2.0, decay_ms=60.0, band_low_hz=800.0, band_high_hz=5200.0),
            transient_layer=TransientLayerSpec(source="breath", level=0.06, duration_ms=25.0, band_low_hz=900.0, band_high_hz=3800.0),
        ),
        gm_program=None,
        category_preferences=["washint", "ethiopian_flute", "brass"],
        instrument_id_hints=["washint"],
        sample_search_tags=["ethio", "washint", "flute", "reed"],
        brightness=0.70,
        warmth=0.40,
        punch=0.26,
        richness=0.52,
        noise_level=0.08,
        genre_tags=["ethio_jazz", "ethiopian_traditional"],
        notes=["Captures bounded washint-family intent without claiming a full live adapter."],
    )


def _begena_patch() -> InstrumentPatch:
    return _make_patch(
        patch_id="ethiopian.begena.track.v1",
        display_name="Begena - Resonant Drone Pluck",
        track_role="drone",
        family="ethiopian_string",
        synthesis_voice=_make_voice(
            [
                OscillatorSpec(algorithm="karplus_strong", level=0.88),
                OscillatorSpec(algorithm="sine", level=0.12, detune_cents=-1200.0),
            ],
            amp_envelope=EnvelopeSpec(attack_ms=25.0, decay_ms=260.0, sustain_level=0.48, release_ms=280.0),
            filter=FilterSpec(mode="lowpass", cutoff_hz=1500.0, resonance=0.12, drive=0.03),
            velocity_map=VelocityMap(amp=0.95, cutoff_delta_hz=120.0, transient_level=0.06, noise_level=0.03),
            noise_layer=NoiseLayerSpec(color="filtered", level=0.03, attack_ms=0.0, decay_ms=30.0, band_low_hz=180.0, band_high_hz=1200.0),
            transient_layer=TransientLayerSpec(source="pick", level=0.08, duration_ms=18.0, band_low_hz=250.0, band_high_hz=1800.0),
            saturation=SaturationSpec(model="tape", drive=0.04, mix=0.10),
        ),
        gm_program=None,
        category_preferences=["begena", "ethiopian_string", "strings"],
        instrument_id_hints=["begena"],
        sample_search_tags=["ethio", "begena", "drone", "lyre"],
        brightness=0.30,
        warmth=0.74,
        punch=0.18,
        richness=0.72,
        noise_level=0.03,
        genre_tags=["ethiopian_traditional", "ethio_jazz"],
        notes=["Represents a bounded begena-family patch for backend reporting."],
    )


_PATCH_BUILDERS = {
    "guitar": _guitar_patch,
    "keys": _keys_patch,
    "bass": _bass_patch,
    "synth": _synth_patch,
    "pad": _pad_patch,
    "brass": _brass_patch,
    "strings": _strings_patch,
    "organ": _organ_patch,
    "choir": _choir_patch,
    "krar": _krar_patch,
    "masenqo": _masenqo_patch,
    "washint": _washint_patch,
    "begena": _begena_patch,
}

_ALIAS_GROUPS = {
    "guitar": [
        "guitar",
        "guitars",
        "electric_guitar",
        "electric guitar",
        "acoustic_guitar",
        "acoustic guitar",
        "distortion_guitar",
        "distortion guitar",
        "crunchy_guitar",
        "crunchy guitar",
        "rock_guitar",
        "rock guitar",
        "gtr",
    ],
    "keys": [
        "keys",
        "piano",
        "grand_piano",
        "upright_piano",
        "keyboard",
        "electric_piano",
        "epiano",
        "rhodes",
        "clavinet",
    ],
    "bass": [
        "bass",
        "electric_bass",
        "upright_bass",
        "contrabass",
        "sub_bass",
        "synth_bass",
    ],
    "synth": [
        "synth",
        "synth_lead",
        "lead",
        "lead_synth",
        "hook_synth",
    ],
    "pad": [
        "pad",
        "pads",
        "synth_pad",
        "ambient_pad",
        "warm_pad",
    ],
    "brass": [
        "brass",
        "horn",
        "trumpet",
        "trombone",
        "french_horn",
        "saxophone",
        "sax",
    ],
    "strings": [
        "strings",
        "string_section",
        "violin",
        "cello",
        "harp",
    ],
    "organ": [
        "organ",
        "hammond",
        "hammond_organ",
        "hammond organ",
        "drawbar_organ",
        "church_organ",
    ],
    "choir": [
        "choir",
        "voice",
        "voices",
        "vocal_pad",
        "ahh_choir",
    ],
    "krar": ["krar"],
    "masenqo": ["masenqo"],
    "washint": ["washint"],
    "begena": ["begena"],
}

_ALIAS_TO_FAMILY = {
    _normalize_token(alias): family
    for family, aliases in _ALIAS_GROUPS.items()
    for alias in aliases
}

_DISPLAY_HINT_STOPWORDS = {
    "bounded",
    "core",
    "procedural",
    "hybrid",
    "focused",
    "slow",
    "support",
    "layer",
    "section",
    "fallback",
    "warm",
    "airy",
    "ensemble",
    "blend",
    "sustained",
    "resonant",
    "bed",
    "track",
    "low",
    "end",
}

_BROAD_FAMILY_HINTS = {
    "unknown",
    "ethiopian_string",
    "ethiopian_flute",
}


def _display_name_hints(display_name: str) -> set[str]:
    return {
        token
        for token in _normalize_token(display_name).split("_")
        if token and token not in _DISPLAY_HINT_STOPWORDS
    }


def _candidate_name_matches_hint(candidate_name_token: str, hint: str) -> bool:
    if not candidate_name_token or not hint:
        return False

    padded_name = f"_{candidate_name_token}_"
    return f"_{hint}_" in padded_name


def _iter_resolved_sample_candidates(
    instruments_used: Optional[Iterable[dict]],
) -> list[dict]:
    candidates: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    for entry in instruments_used or []:
        if not isinstance(entry, dict):
            continue

        path = str(entry.get("path") or "").strip()
        if not path:
            continue

        category = _normalize_token(str(entry.get("category") or ""))
        name = str(entry.get("name") or "").strip()
        name_token = _normalize_token(name)
        if not category and not name_token:
            continue

        key = (path, category, name_token)
        if key in seen:
            continue
        seen.add(key)

        stem_token = _normalize_token(Path(path).stem)
        source_id_token = name_token or stem_token or category or "sample"
        source_id_parts = [part for part in (category or "resolved_sample", source_id_token) if part]

        candidates.append(
            {
                "path": path,
                "category": category,
                "name": name,
                "name_token": name_token,
                "source_id": ".".join(source_id_parts),
            }
        )

    return candidates


def _dedupe_candidates_by_path(candidates: Iterable[dict]) -> list[dict]:
    unique_by_path: dict[str, dict] = {}
    for candidate in candidates:
        path = str(candidate.get("path") or "")
        if path and path not in unique_by_path:
            unique_by_path[path] = candidate
    return list(unique_by_path.values())


def _choose_resolved_sample_for_patch(
    patch: InstrumentPatch,
    resolved_candidates: list[dict],
) -> Optional[dict]:
    category_preferences = [
        _normalize_token(value)
        for value in list(getattr(patch.fallback, "category_preferences", []) or [])
    ]
    category_preferences = [value for value in category_preferences if value]
    primary_category = category_preferences[0] if category_preferences else ""

    exact_hints = {
        _normalize_token(value)
        for value in list(getattr(patch.fallback, "instrument_id_hints", []) or [])
        if _normalize_token(value)
    }
    if primary_category:
        exact_hints.add(primary_category)

    family_hint = _normalize_token(getattr(patch.patch_profile, "family", ""))
    if family_hint and family_hint not in _BROAD_FAMILY_HINTS:
        exact_hints.add(family_hint)

    exact_hints.update(_display_name_hints(getattr(patch, "display_name", "")))

    exact_matches = _dedupe_candidates_by_path(
        candidate
        for candidate in resolved_candidates
        if any(
            candidate.get("category") == hint
            or _candidate_name_matches_hint(str(candidate.get("name_token") or ""), hint)
            for hint in exact_hints
        )
    )
    if len(exact_matches) == 1:
        return exact_matches[0]
    if len(exact_matches) > 1:
        return None

    if primary_category:
        primary_matches = _dedupe_candidates_by_path(
            candidate
            for candidate in resolved_candidates
            if candidate.get("category") == primary_category
        )
        if len(primary_matches) == 1:
            return primary_matches[0]

    return None


def normalize_instrument_alias(name: str) -> Optional[str]:
    """Normalize an instrument name into a bounded registry family."""
    token = _normalize_token(name)
    if not token:
        return None
    return _ALIAS_TO_FAMILY.get(token)


def get_registered_patch_families() -> list[str]:
    """Return the bounded set of canonical patch families."""
    return list(_PATCH_BUILDERS.keys())


def get_instrument_patch(name: str, genre: Optional[str] = None) -> Optional[InstrumentPatch]:
    """Return a fresh InstrumentPatch for a canonical family or known alias."""
    family = normalize_instrument_alias(name) or _normalize_token(name)
    builder = _PATCH_BUILDERS.get(family)
    if builder is None:
        return None

    patch = builder()
    normalized_genre = _normalize_token(genre) if genre else ""
    if normalized_genre and normalized_genre not in patch.patch_profile.genre_tags:
        patch.patch_profile.genre_tags.append(normalized_genre)
    return patch


def build_track_scoped_instrument_patches(
    instrument_names: Iterable[str],
    genre: Optional[str] = None,
) -> list[InstrumentPatch]:
    """Build a deduped, ordered list of track-scoped InstrumentPatch objects."""
    patches: list[InstrumentPatch] = []
    seen_families: set[str] = set()

    for name in instrument_names or []:
        family = normalize_instrument_alias(name)
        if not family or family in seen_families:
            continue

        patch = get_instrument_patch(family, genre=genre)
        if patch is None:
            continue

        patches.append(patch)
        seen_families.add(family)

    return patches


def enrich_instrument_patches_with_resolved_samples(
    patches: Iterable[InstrumentPatch],
    instruments_used: Optional[Iterable[dict]],
) -> list[InstrumentPatch]:
    """Attach at most one truthful sample-layer hint from resolved sample metadata.

    This helper is intentionally conservative:
    - it only considers already-resolved instruments_used entries with real path values,
    - it matches on primary fallback categories plus exact-safe hint/name/category signals,
    - it leaves sample_layers empty when multiple resolved candidates remain plausible.
    """

    resolved_candidates = _iter_resolved_sample_candidates(instruments_used)
    enriched: list[InstrumentPatch] = []

    for patch in patches or []:
        if not isinstance(patch, InstrumentPatch):
            continue

        patch_copy = copy.deepcopy(patch)
        patch_copy.sample_layers = []

        resolved_sample = _choose_resolved_sample_for_patch(
            patch_copy,
            resolved_candidates,
        )
        if resolved_sample is not None:
            patch_copy.sample_layers.append(
                SampleLayerSpec(
                    source_id=str(resolved_sample.get("source_id") or "resolved_sample"),
                    path_hint=str(resolved_sample.get("path") or ""),
                    category_hint=str(resolved_sample.get("category") or ""),
                )
            )

        enriched.append(patch_copy)

    return enriched


__all__ = [
    "EnvelopeSpec",
    "VelocityMap",
    "OscillatorSpec",
    "FilterSpec",
    "LfoSpec",
    "NoiseLayerSpec",
    "TransientLayerSpec",
    "SaturationSpec",
    "SampleLayerSpec",
    "FallbackBinding",
    "PatchProfile",
    "SynthesisVoice",
    "InstrumentPatch",
    "normalize_instrument_alias",
    "get_registered_patch_families",
    "get_instrument_patch",
    "build_track_scoped_instrument_patches",
    "enrich_instrument_patches_with_resolved_samples",
]
