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
    assert normalize_genre(None) == ""


def test_unknown_genre_returns_default_noop_profile():
    profile = get_fluidsynth_profile("space polka")

    assert profile.name == "default"
    assert profile.genre_family == "default"
    assert profile.tone_shelves == ()
    assert profile_diagnostic(profile) == "default:default"
    assert profile_tone_shelves_diagnostic(profile) == ""


def test_rock_aliases_resolve_to_exact_strict_tone_shelves():
    for genre in ["rock", "alt rock", "alternative-rock", "grunge", "1990s rock"]:
        profile = get_fluidsynth_profile(genre)
        assert profile.name == "rock"
        assert profile.genre_family == "rock"
        assert profile_tone_shelves_diagnostic(profile) == (
            "high_shelf=-6.0dB@5000Hz;low_shelf=-0.75dB@90Hz"
        )

    assert "alternative_rock" in ROCK_FAMILY_GENRES
    shelves = get_fluidsynth_profile("rock").tone_shelves
    assert shelves[0].shelf_type == "high"
    assert shelves[0].frequency_hz == 5000.0
    assert shelves[0].gain_db == -6.0
    assert shelves[1].shelf_type == "low"
    assert shelves[1].frequency_hz == 90.0
    assert shelves[1].gain_db == -0.75


def test_initial_non_rock_profiles_are_discoverable_noops():
    expected = {
        "classical": ("classical", "classical"),
        "orchestral": ("classical", "classical"),
        "jazz": ("jazz", "jazz"),
        "trap": ("trap_modern_beat", "modern_beat"),
        "trap soul": ("trap_modern_beat", "modern_beat"),
        "modern beat": ("trap_modern_beat", "modern_beat"),
    }

    for genre, (name, family) in expected.items():
        profile = get_fluidsynth_profile(genre)
        assert profile.name == name
        assert profile.genre_family == family
        assert profile.tone_shelves == ()
        assert profile_tone_shelves_diagnostic(profile) == ""