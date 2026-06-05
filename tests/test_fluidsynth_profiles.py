"""Tests for the FluidSynth renderer profile registry."""

from multimodal_gen.fluidsynth_profiles import (
    ROCK_FAMILY_GENRES,
    get_contextual_fluidsynth_profile,
    get_fluidsynth_profile,
    normalize_genre,
    profile_diagnostic,
    profile_tone_shelves_diagnostic,
)
from multimodal_gen.prompt_parser import PromptParser


def test_normalize_genre_handles_common_lookup_aliases():
    assert normalize_genre(" Alt Rock ") == "alternative_rock"
    assert normalize_genre("alternative-rock") == "alternative_rock"
    assert normalize_genre("1990s Rock") == "rock"
    assert normalize_genre("Trap-Soul") == "trap_soul"
    assert normalize_genre("R&B") == "rnb"
    assert normalize_genre(None) == ""


ROCK_TONE_DIAGNOSTIC = "high_shelf=-10.0dB@4000Hz;low_shelf=-4.0dB@90Hz"
LYRICAL_CINEMATIC_TONE_DIAGNOSTIC = "high_shelf=-3.0dB@3500Hz"

LYRICAL_CINEMATIC_PIANO_PROMPT = (
    "cinematic orchestral score with lyrical piano, warm strings, flute, oboe, "
    "harp, and soft choir, emotional rising theme, 78 BPM in G major"
)


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


def test_house_ambient_pop_profile_is_explicit_noop():
    for genre in ["house", "ambient", "pop", "dance pop", "dance_pop", "electro pop", "electropop"]:
        profile = get_fluidsynth_profile(genre)
        assert profile.name == "house_ambient_pop"
        assert profile.genre_family == "house"
        assert profile_diagnostic(profile) == "house_ambient_pop:house"
        assert profile.tone_shelves == ()
        assert profile_tone_shelves_diagnostic(profile) == ""


def test_ethiopian_family_profile_is_explicit_noop():
    for genre in ["ethiopian", "ethio jazz", "ethio_jazz", "ethiopian traditional", "eskista"]:
        profile = get_fluidsynth_profile(genre)
        assert profile.name == "ethiopian_family"
        assert profile.genre_family == "ethio_jazz"
        assert profile_diagnostic(profile) == "ethiopian_family:ethio_jazz"
        assert profile.tone_shelves == ()
        assert profile_tone_shelves_diagnostic(profile) == ""


def test_jazz_aliases_resolve_to_measured_brightness_shelf():
    for genre in ["jazz", "smooth jazz", "bebop"]:
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


def test_lyrical_cinematic_piano_prompt_uses_narrow_contextual_classical_profile():
    parsed = PromptParser().parse(LYRICAL_CINEMATIC_PIANO_PROMPT)

    profile = get_contextual_fluidsynth_profile(parsed.genre, parsed)

    assert profile.name == "classical_lyrical_piano"
    assert profile.genre_family == "classical"
    assert profile_diagnostic(profile) == "classical_lyrical_piano:classical"
    assert profile_tone_shelves_diagnostic(profile) == LYRICAL_CINEMATIC_TONE_DIAGNOSTIC


def test_dark_and_heroic_cinematic_prompts_keep_base_classical_profile():
    prompts = [
        "dark cinematic orchestral film score with sweeping strings, brass, french horn, choir, harp, and timpani, 72 BPM in D minor",
        "heroic cinematic orchestral swell with strings, brass, choir, french horn, and timpani, triumphant rising theme, 96 BPM in D minor",
    ]

    for prompt in prompts:
        parsed = PromptParser().parse(prompt)
        profile = get_contextual_fluidsynth_profile(parsed.genre, parsed)
        assert profile.name == "classical"
        assert profile.genre_family == "classical"
        assert profile_diagnostic(profile) == "classical:classical"
        assert profile_tone_shelves_diagnostic(profile) == ""