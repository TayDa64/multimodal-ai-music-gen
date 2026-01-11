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

from multimodal_gen.utils import normalize_genre
from multimodal_gen.prompt_parser import PromptParser


def test_normalize_genre_gfunk_variants():
    assert normalize_genre("gfunk") == "g_funk"
    assert normalize_genre("g-funk") == "g_funk"
    assert normalize_genre("g funk") == "g_funk"
    assert normalize_genre("G Funk") == "g_funk"


def test_prompt_parser_detects_gfunk():
    parsed = PromptParser().parse("gfunk west coast beat at 92 bpm in C minor")
    assert parsed.genre == "g_funk"
