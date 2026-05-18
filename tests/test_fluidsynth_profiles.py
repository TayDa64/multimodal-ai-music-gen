"""Tests for the FluidSynth renderer profile registry."""

from multimodal_gen.fluidsynth_profiles import (
    ROCK_FAMILY_GENRES,
    get_fluidsynth_profile,
    normalize_genre,
    profile_diagnostic,
    profile_tone_shelves_diagnostic,
)


def test_normalize_genre_handles_common_lookup_aliases():
    assert normalize_genre(" Alt Rock ") == "alternative_rock"
    assert normalize_genre("alternative-rock") == "alternative_rock"
    assert normalize_genre("1990s Rock") == "rock"
    assert normalize_genre("Trap-Soul") == "trap_soul"
    assert normalize_genre("R&B") == "rnb"
    assert normalize_genre(None) == ""


ROCK_TONE_DIAGNOSTIC = "high_shelf=-10.0dB@4000Hz;low_shelf=-4.0dB@90Hz"


def test_unknown_genre_returns_default_noop_profile():
    profile = get_fluidsynth_profile("space polka")

    assert profile.name == "default"
    assert profile.genre_family == "default"
    assert profile.tone_shelves == ()
    assert profile_diagnostic(profile) == "default:default"
    assert profile_tone_shelves_diagnostic(profile) == ""


def test_rock_aliases_resolve_to_exact_strict_tone_shelves():
    aliases = [
        "rock",
        "classic rock",
        "classic_rock",
        "grunge",
        "punk rock",
        "punk_rock",
        "indie rock",
        "indie_rock",
        "alternative rock",
        "alternative_rock",
        "alt rock",
        "alternative-rock",
        "90s rock",
        "90's rock",
        "1990s rock",
        "1990's rock",
    ]

    for genre in aliases:
        profile = get_fluidsynth_profile(genre)
        assert profile.name == "rock"
        assert profile.genre_family == "rock"
        assert profile_tone_shelves_diagnostic(profile) == ROCK_TONE_DIAGNOSTIC

    assert "alternative_rock" in ROCK_FAMILY_GENRES
    shelves = get_fluidsynth_profile("rock").tone_shelves
    assert shelves[0].shelf_type == "high"
    assert shelves[0].frequency_hz == 4000.0
    assert shelves[0].gain_db == -10.0
    assert shelves[1].shelf_type == "low"
    assert shelves[1].frequency_hz == 90.0
    assert shelves[1].gain_db == -4.0


def test_classical_and_trap_profiles_remain_discoverable_noops():
    expected = {
        "classical": ("classical", "classical"),
        "orchestral": ("classical", "classical"),
        "trap": ("trap_modern_beat", "modern_beat"),
        "modern beat": ("trap_modern_beat", "modern_beat"),
    }

    for genre, (name, family) in expected.items():
        profile = get_fluidsynth_profile(genre)
        assert profile.name == name
        assert profile.genre_family == family
        assert profile.tone_shelves == ()
        assert profile_tone_shelves_diagnostic(profile) == ""


def test_rnb_neosoul_profile_is_explicit_noop():
    for genre in ["rnb", "R&B", "neo soul", "neo_soul", "trap soul", "trap_soul"]:
        profile = get_fluidsynth_profile(genre)
        assert profile.name == "rnb_neosoul"
        assert profile.genre_family == "neo_soul"
        assert profile_diagnostic(profile) == "rnb_neosoul:neo_soul"
        assert profile.tone_shelves == ()
        assert profile_tone_shelves_diagnostic(profile) == ""


def test_lofi_boom_bap_profile_is_explicit_noop():
    for genre in ["lofi", "lo-fi", "lo fi", "boom bap", "boom_bap", "g funk", "g_funk"]:
        profile = get_fluidsynth_profile(genre)
        assert profile.name == "lofi_boom_bap"
        assert profile.genre_family == "boom_bap"
        assert profile_diagnostic(profile) == "lofi_boom_bap:boom_bap"
        assert profile.tone_shelves == ()
        assert profile_tone_shelves_diagnostic(profile) == ""


def test_jazz_aliases_resolve_to_measured_brightness_shelf():
    for genre in ["jazz", "smooth jazz", "bebop", "ethio jazz"]:
        profile = get_fluidsynth_profile(genre)
        assert profile.name == "jazz"
        assert profile.genre_family == "jazz"
        assert profile_diagnostic(profile) == "jazz:jazz"
        assert profile_tone_shelves_diagnostic(profile) == "high_shelf=-5.0dB@4000Hz"

    shelves = get_fluidsynth_profile("jazz").tone_shelves
    assert len(shelves) == 1
    assert shelves[0].shelf_type == "high"
    assert shelves[0].frequency_hz == 4000.0
    assert shelves[0].gain_db == -5.0