"""FluidSynth renderer profile registry.

Profiles in this module are descriptive policy for file-level FluidSynth
post-processing only.  They must not select the renderer backend, require a
SoundFont, or change procedural/custom/expansion fallback behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Sequence, Tuple


@dataclass(frozen=True)
class ToneShelf:
    """A deterministic shelf-EQ move used by a FluidSynth profile."""

    frequency_hz: float
    gain_db: float
    shelf_type: str

    def __post_init__(self) -> None:
        shelf_type = str(self.shelf_type or "").strip().lower().replace("-", "_").replace(" ", "_")
        if shelf_type.endswith("_shelf"):
            shelf_type = shelf_type[: -len("_shelf")]
        object.__setattr__(self, "frequency_hz", float(self.frequency_hz))
        object.__setattr__(self, "gain_db", float(self.gain_db))
        object.__setattr__(self, "shelf_type", shelf_type)


@dataclass(frozen=True)
class FluidSynthRendererProfile:
    """Genre-scoped FluidSynth file-rendering policy."""

    name: str
    genre_family: str
    aliases: Sequence[str]
    tone_shelves: Sequence[ToneShelf]
    preferred_soundfonts: Sequence[str] = ()
    renderer_scope: str = "full_mix"
    mastering_profile: str = "neutral"
    analyzer_profile: str = "default"

    def __post_init__(self) -> None:
        aliases = tuple(dict.fromkeys(
            normalized for alias in self.aliases if (normalized := normalize_genre(alias))
        ))
        object.__setattr__(self, "aliases", aliases)
        object.__setattr__(self, "tone_shelves", tuple(self.tone_shelves or ()))
        object.__setattr__(self, "preferred_soundfonts", tuple(self.preferred_soundfonts or ()))


ROCK_FAMILY_GENRES = frozenset({
    "rock",
    "classic_rock",
    "alternative_rock",
    "grunge",
    "punk_rock",
    "indie_rock",
})

CLASSICAL_FAMILY_GENRES = frozenset({
    "classical",
    "orchestral",
    "cinematic",
    "film_score",
})

JAZZ_FAMILY_GENRES = frozenset({
    "jazz",
    "smooth_jazz",
    "bebop",
})

ETHIOPIAN_FAMILY_GENRES = frozenset({
    "ethiopian",
    "ethio_jazz",
    "ethiopian_traditional",
    "eskista",
})

TRAP_MODERN_BEAT_FAMILY_GENRES = frozenset({
    "trap",
    "drill",
    "hip_hop",
    "modern_beat",
})

LOFI_BOOM_BAP_FAMILY_GENRES = frozenset({
    "lofi",
    "lo_fi",
    "boom_bap",
    "g_funk",
})

HOUSE_AMBIENT_POP_FAMILY_GENRES = frozenset({
    "house",
    "ambient",
    "pop",
    "dance_pop",
    "electropop",
})

RNB_NEOSOUL_FAMILY_GENRES = frozenset({
    "rnb",
    "r_and_b",
    "neo_soul",
    "trap_soul",
})

_GENRE_ALIASES: Dict[str, str] = {
    # Rock family
    "rock": "rock",
    "rock_song": "rock",
    "rock_band": "rock",
    "90s_rock": "rock",
    "90's_rock": "rock",
    "1990s_rock": "rock",
    "1990's_rock": "rock",
    "classic_rock": "classic_rock",
    "alt_rock": "alternative_rock",
    "altrock": "alternative_rock",
    "alternative_rock": "alternative_rock",
    "grunge": "grunge",
    "punk_rock": "punk_rock",
    "indie_rock": "indie_rock",
    # Classical / orchestral no-op family
    "classical": "classical",
    "orchestral": "orchestral",
    "orchestra": "orchestral",
    "cinematic": "cinematic",
    "film_score": "film_score",
    "soundtrack": "film_score",
    # Jazz family
    "jazz": "jazz",
    "smooth_jazz": "smooth_jazz",
    "bebop": "bebop",
    # Ethiopian family no-op profile
    "ethiopian": "ethiopian",
    "ethio_jazz": "ethio_jazz",
    "ethiopian_traditional": "ethiopian_traditional",
    "eskista": "eskista",
    # R&B / neo-soul no-op family
    "rnb": "rnb",
    "r_and_b": "rnb",
    "randb": "rnb",
    "neo_soul": "neo_soul",
    "neosoul": "neo_soul",
    "trap_soul": "trap_soul",
    "trapsoul": "trap_soul",
    # Lofi / boom-bap / G-Funk no-op family
    "lofi": "lofi",
    "lo_fi": "lofi",
    "lo-fi": "lofi",
    "boom_bap": "boom_bap",
    "boombap": "boom_bap",
    "g_funk": "g_funk",
    "gfunk": "g_funk",
    "west_coast": "g_funk",
    # House / ambient / pop no-op family
    "house": "house",
    "ambient": "ambient",
    "pop": "pop",
    "dance_pop": "dance_pop",
    "dancepop": "dance_pop",
    "electropop": "electropop",
    "electro_pop": "electropop",
    # Trap / modern beat no-op family
    "trap": "trap",
    "drill": "drill",
    "hip_hop": "hip_hop",
    "hiphop": "hip_hop",
    "modern_beat": "modern_beat",
    "modern_beats": "modern_beat",
}


def normalize_genre(genre) -> str:
    """Normalize genre text to deterministic registry lookup keys."""
    if genre is None:
        return ""

    key = str(genre).strip().lower()
    if not key:
        return ""
    key = key.replace("&", "and")
    key = key.replace("-", "_").replace(" ", "_")
    while "__" in key:
        key = key.replace("__", "_")
    return _GENRE_ALIASES.get(key, key)


ROCK_TONE_SHELVES: Tuple[ToneShelf, ...] = (
    ToneShelf(frequency_hz=4000.0, gain_db=-10.0, shelf_type="high"),
    ToneShelf(frequency_hz=90.0, gain_db=-4.0, shelf_type="low"),
)

JAZZ_TONE_SHELVES: Tuple[ToneShelf, ...] = (
    ToneShelf(frequency_hz=4000.0, gain_db=-5.0, shelf_type="high"),
)

CLASSICAL_LYRICAL_PIANO_TONE_SHELVES: Tuple[ToneShelf, ...] = (
    ToneShelf(frequency_hz=3500.0, gain_db=-3.0, shelf_type="high"),
)

DEFAULT_FLUIDSYNTH_PROFILE = FluidSynthRendererProfile(
    name="default",
    genre_family="default",
    aliases=(),
    tone_shelves=(),
)

ROCK_FLUIDSYNTH_PROFILE = FluidSynthRendererProfile(
    name="rock",
    genre_family="rock",
    aliases=tuple(sorted(ROCK_FAMILY_GENRES | {
        "90s_rock",
        "1990s_rock",
        "alt_rock",
        "altrock",
        "rock_song",
        "rock_band",
    })),
    tone_shelves=ROCK_TONE_SHELVES,
    mastering_profile="rock_strict_8f84e45",
    analyzer_profile="rock_strict",
)

CLASSICAL_FLUIDSYNTH_PROFILE = FluidSynthRendererProfile(
    name="classical",
    genre_family="classical",
    aliases=tuple(sorted(CLASSICAL_FAMILY_GENRES)),
    tone_shelves=(),
)

CLASSICAL_LYRICAL_PIANO_FLUIDSYNTH_PROFILE = FluidSynthRendererProfile(
    name="classical_lyrical_piano",
    genre_family="classical",
    aliases=(),
    tone_shelves=CLASSICAL_LYRICAL_PIANO_TONE_SHELVES,
)

JAZZ_FLUIDSYNTH_PROFILE = FluidSynthRendererProfile(
    name="jazz",
    genre_family="jazz",
    aliases=tuple(sorted(JAZZ_FAMILY_GENRES)),
    tone_shelves=JAZZ_TONE_SHELVES,
)

ETHIOPIAN_FAMILY_FLUIDSYNTH_PROFILE = FluidSynthRendererProfile(
    name="ethiopian_family",
    genre_family="ethio_jazz",
    aliases=tuple(sorted(ETHIOPIAN_FAMILY_GENRES)),
    tone_shelves=(),
)

TRAP_MODERN_BEAT_FLUIDSYNTH_PROFILE = FluidSynthRendererProfile(
    name="trap_modern_beat",
    genre_family="modern_beat",
    aliases=tuple(sorted(TRAP_MODERN_BEAT_FAMILY_GENRES)),
    tone_shelves=(),
)

RNB_NEOSOUL_FLUIDSYNTH_PROFILE = FluidSynthRendererProfile(
    name="rnb_neosoul",
    genre_family="neo_soul",
    aliases=tuple(sorted(RNB_NEOSOUL_FAMILY_GENRES | {"r&b"})),
    tone_shelves=(),
)

LOFI_BOOM_BAP_FLUIDSYNTH_PROFILE = FluidSynthRendererProfile(
    name="lofi_boom_bap",
    genre_family="boom_bap",
    aliases=tuple(sorted(LOFI_BOOM_BAP_FAMILY_GENRES | {"boombap", "gfunk", "west_coast"})),
    tone_shelves=(),
)

HOUSE_AMBIENT_POP_FLUIDSYNTH_PROFILE = FluidSynthRendererProfile(
    name="house_ambient_pop",
    genre_family="house",
    aliases=tuple(sorted(HOUSE_AMBIENT_POP_FAMILY_GENRES | {"dancepop", "electro_pop"})),
    tone_shelves=(),
)

FLUIDSYNTH_RENDERER_PROFILES: Tuple[FluidSynthRendererProfile, ...] = (
    ROCK_FLUIDSYNTH_PROFILE,
    CLASSICAL_FLUIDSYNTH_PROFILE,
    JAZZ_FLUIDSYNTH_PROFILE,
    ETHIOPIAN_FAMILY_FLUIDSYNTH_PROFILE,
    RNB_NEOSOUL_FLUIDSYNTH_PROFILE,
    LOFI_BOOM_BAP_FLUIDSYNTH_PROFILE,
    HOUSE_AMBIENT_POP_FLUIDSYNTH_PROFILE,
    TRAP_MODERN_BEAT_FLUIDSYNTH_PROFILE,
)

_PROFILE_BY_GENRE: Dict[str, FluidSynthRendererProfile] = {}
for _profile in FLUIDSYNTH_RENDERER_PROFILES:
    for _key in (_profile.name, _profile.genre_family, *_profile.aliases):
        _normalized = normalize_genre(_key)
        if _normalized:
            _PROFILE_BY_GENRE[_normalized] = _profile


def get_fluidsynth_profile(genre) -> FluidSynthRendererProfile:
    """Return the FluidSynth renderer profile for ``genre`` or a no-op default."""
    return _PROFILE_BY_GENRE.get(normalize_genre(genre), DEFAULT_FLUIDSYNTH_PROFILE)


def is_classical_family_genre(genre) -> bool:
    """Return True when ``genre`` belongs to the cinematic/classical family."""
    return normalize_genre(genre) in CLASSICAL_FAMILY_GENRES


def _normalize_prompt_fragment(value: Any) -> str:
    return str(value or "").strip().lower().replace("-", " ").replace("_", " ")


def _parsed_prompt_search_blob(parsed: Any) -> str:
    if parsed is None:
        return ""

    fragments = [
        _normalize_prompt_fragment(getattr(parsed, "raw_prompt", "")),
        _normalize_prompt_fragment(getattr(parsed, "mood", "")),
    ]
    for attribute in ("style_modifiers", "sonic_adjectives", "instruments"):
        for value in getattr(parsed, attribute, ()) or ():
            fragments.append(_normalize_prompt_fragment(value))
    return " ".join(fragment for fragment in fragments if fragment)


def _has_explicit_piano_request(parsed: Any) -> bool:
    if parsed is None:
        return False

    piano_aliases = {
        "piano",
        "grand piano",
        "grand_piano",
        "acoustic piano",
        "acoustic_piano",
        "acoustic grand",
        "acoustic_grand",
        "acoustic grand piano",
        "acoustic_grand_piano",
    }
    instruments = {
        _normalize_prompt_fragment(instrument)
        for instrument in getattr(parsed, "instruments", ()) or ()
        if str(instrument or "").strip()
    }
    if instruments & piano_aliases:
        return True

    raw_prompt = _normalize_prompt_fragment(getattr(parsed, "raw_prompt", ""))
    return any(phrase in raw_prompt for phrase in piano_aliases)


def is_lyrical_orchestral_piano_prompt(parsed: Any, genre=None) -> bool:
    """Return True only for narrow lyrical/warm/soft orchestral piano contexts."""
    if parsed is None:
        return False

    resolved_genre = genre or getattr(parsed, "genre", None)
    if not is_classical_family_genre(resolved_genre):
        return False
    if not _has_explicit_piano_request(parsed):
        return False

    searchable = _parsed_prompt_search_blob(parsed)
    lyrical_emotion_cues = (
        "lyrical",
        "emotional",
        "heartfelt",
        "soulful",
        "expressive",
        "intimate",
    )
    softness_cues = (
        "warm",
        "soft",
        "gentle",
        "delicate",
        "muted",
        "tender",
    )
    has_lyrical_emotion = getattr(parsed, "mood", None) == "emotional" or any(
        cue in searchable for cue in lyrical_emotion_cues
    )
    has_softness = any(cue in searchable for cue in softness_cues)
    return has_lyrical_emotion and has_softness


def get_contextual_fluidsynth_profile(
    genre,
    parsed: Any = None,
) -> FluidSynthRendererProfile:
    """Return a prompt-aware FluidSynth profile while preserving base genre defaults."""
    resolved_genre = getattr(parsed, "genre", None) or genre
    profile = get_fluidsynth_profile(resolved_genre)

    if (
        parsed is not None
        and profile.genre_family == "classical"
        and is_lyrical_orchestral_piano_prompt(parsed, resolved_genre)
    ):
        return CLASSICAL_LYRICAL_PIANO_FLUIDSYNTH_PROFILE

    return profile


def _format_gain_db(gain_db: float) -> str:
    gain = float(gain_db)
    if gain.is_integer():
        return f"{gain:.1f}"
    return f"{gain:g}"


def _format_frequency_hz(frequency_hz: float) -> str:
    frequency = float(frequency_hz)
    if frequency.is_integer():
        return str(int(frequency))
    return f"{frequency:g}"


def format_tone_shelf_diagnostic(shelf: ToneShelf) -> str:
    """Format one shelf using the existing render-report diagnostic style."""
    shelf_type = shelf.shelf_type if shelf.shelf_type.endswith("_shelf") else f"{shelf.shelf_type}_shelf"
    return (
        f"{shelf_type}={_format_gain_db(shelf.gain_db)}dB@"
        f"{_format_frequency_hz(shelf.frequency_hz)}Hz"
    )


def profile_tone_shelves_diagnostic(profile: FluidSynthRendererProfile) -> str:
    """Return the semicolon-separated shelf diagnostic for a profile."""
    return ";".join(format_tone_shelf_diagnostic(shelf) for shelf in profile.tone_shelves)


def profile_diagnostic(profile: FluidSynthRendererProfile) -> str:
    """Return a compact profile/family diagnostic for render reports."""
    return f"{profile.name}:{profile.genre_family}"