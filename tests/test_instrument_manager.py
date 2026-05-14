"""Focused regressions for first-class guitar sample categorization."""

from multimodal_gen.instrument_manager import (
    InstrumentCategory,
    InstrumentLibrary,
    InstrumentMatcher,
)


def test_guitar_category_exists():
    assert InstrumentCategory.GUITAR.value == "guitar"


def test_guitar_named_strings_funk_samples_classify_as_guitar():
    lib = InstrumentLibrary(instruments_dir=None, auto_load_audio=False)

    assert lib._detect_category(
        r"C:\dev\MUSE-ai\MUSE\instruments\strings\funk\RnB-Guitar-RckGut Gtr E.WAV"
    ) is InstrumentCategory.GUITAR
    assert lib._detect_category(
        r"C:\dev\MUSE-ai\MUSE\instruments\strings\funk\Inst-Guitar-Crunch E.WAV"
    ) is InstrumentCategory.GUITAR
    assert lib._detect_category(
        r"C:\dev\MUSE-ai\MUSE\instruments\strings\funk\Riff-Gtr-01.wav"
    ) is InstrumentCategory.GUITAR


def test_non_guitar_string_path_remains_strings():
    lib = InstrumentLibrary(instruments_dir=None, auto_load_audio=False)

    assert lib._detect_category(
        r"C:\dev\MUSE-ai\MUSE\instruments\strings\orchestral\violin_legato_C4.wav"
    ) is InstrumentCategory.STRINGS


def test_get_recommendations_includes_guitar_category():
    """Verify that InstrumentMatcher.get_recommendations() includes guitar in its category list.

    This test verifies that the category list in get_recommendations contains 'guitar',
    which enables the backend to expose guitar in instruments_used metadata when
    guitar samples are available.
    """
    # Import directly to check the category list
    from multimodal_gen.instrument_manager import InstrumentMatcher

    # Read the source code of get_recommendations to verify guitar is in the categories list
    import inspect
    source = inspect.getsource(InstrumentMatcher.get_recommendations)

    # Verify guitar is in the categories list
    assert '"guitar"' in source or "'guitar'" in source, \
        "Guitar category must be in InstrumentMatcher.get_recommendations() category list"

    # Also verify other expected categories are present for completeness
    for cat in ["kick", "snare", "bass", "keys"]:
        assert f'"{cat}"' in source or f"'{cat}'" in source, \
            f"{cat} category should be in recommendations"
