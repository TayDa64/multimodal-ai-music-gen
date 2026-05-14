"""Genre normalization regression tests.

These are intentionally small and deterministic.
They protect against subtle fallbacks where variant genre spellings
(e.g. 'gfunk') don't match internal keys (e.g. 'g_funk'), causing
downstream modules to behave like a different default genre.
"""

# Add parent directory to path for imports
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from multimodal_gen.utils import GENRE_DEFAULTS, normalize_genre
from multimodal_gen.prompt_parser import PromptParser


def test_normalize_genre_gfunk_variants():
    assert normalize_genre("gfunk") == "g_funk"
    assert normalize_genre("g-funk") == "g_funk"
    assert normalize_genre("g funk") == "g_funk"
    assert normalize_genre("G Funk") == "g_funk"


def test_prompt_parser_detects_gfunk():
    parsed = PromptParser().parse("gfunk west coast beat at 92 bpm in C minor")
    assert parsed.genre == "g_funk"


def test_normalize_genre_neo_soul_variants():
    assert normalize_genre("neo_soul") == "neo_soul"
    assert normalize_genre("neo-soul") == "neo_soul"
    assert normalize_genre("neo soul") == "neo_soul"
    assert normalize_genre("NeoSoul") == "neo_soul"


def test_neo_soul_has_first_class_defaults():
    assert "neo_soul" in GENRE_DEFAULTS
    assert GENRE_DEFAULTS["neo_soul"]["hihat_rolls"] is False
    assert GENRE_DEFAULTS["neo_soul"]["emphasis"] == "chords"


def test_normalize_genre_rock_family_variants():
    assert normalize_genre("rock") == "rock"
    assert normalize_genre("90s rock") == "rock"
    assert normalize_genre("1990s rock") == "rock"
    assert normalize_genre("classic rock") == "classic_rock"
    assert normalize_genre("classic-rock") == "classic_rock"
    assert normalize_genre("classic_rock") == "classic_rock"
    assert normalize_genre("alternative rock") == "alternative_rock"
    assert normalize_genre("alternative-rock") == "alternative_rock"
    assert normalize_genre("alternative_rock") == "alternative_rock"
    assert normalize_genre("alt rock") == "alternative_rock"
    assert normalize_genre("alt-rock") == "alternative_rock"
    assert normalize_genre("grunge") == "grunge"
    assert normalize_genre("punk rock") == "punk_rock"
    assert normalize_genre("punk-rock") == "punk_rock"
    assert normalize_genre("punk_rock") == "punk_rock"
    assert normalize_genre("indie rock") == "indie_rock"
    assert normalize_genre("indie-rock") == "indie_rock"
    assert normalize_genre("indie_rock") == "indie_rock"


def test_rock_family_parses_to_modular_keys_and_has_defaults():
    parser = PromptParser()
    cases = [
        ("rock band with electric guitar and live drums", "rock"),
        ("classic rock band with guitar and live drums", "classic_rock"),
        ("alternative rock song with guitars", "alternative_rock"),
        ("alt rock live drums and distorted guitars", "alternative_rock"),
        ("grunge band with crunchy guitar", "grunge"),
        ("punk rock song with fast live drums", "punk_rock"),
    ]

    for prompt, expected in cases:
        assert parser.parse(prompt).genre == expected
        assert expected in GENRE_DEFAULTS
        assert GENRE_DEFAULTS[expected]["hihat_rolls"] is False
        assert GENRE_DEFAULTS[expected]["emphasis"] == "guitar_band"
