"""Focused regressions for first-class guitar sample categorization."""

from multimodal_gen.instrument_manager import InstrumentCategory, InstrumentLibrary


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
