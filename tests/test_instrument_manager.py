"""Focused regressions for first-class guitar sample categorization."""

import json

from multimodal_gen.instrument_manager import (
    AnalyzedInstrument,
    InstrumentCategory,
    InstrumentLibrary,
    InstrumentMatcher,
    SonicProfile,
)
from multimodal_gen.server.worker import InstrumentScanWorker, instrument_display_name


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


def test_instrument_display_name_strips_only_leading_source_prefixes():
    assert instrument_display_name("RnB-Guitar-RckGut Gtr E.WAV") == "Guitar-RckGut Gtr E.WAV"
    assert instrument_display_name("Inst-Pad-Cloud Pad C0.WAV") == "Pad-Cloud Pad C0.WAV"
    assert instrument_display_name("rnb_inst Guitar.wav") == "Guitar.wav"
    assert instrument_display_name("Classic Guitar.wav") == "Classic Guitar.wav"
    assert instrument_display_name("Guitar-RnB-Tail.wav") == "Guitar-RnB-Tail.wav"


def test_instrument_scan_payload_adds_display_name_without_mutating_name(monkeypatch, tmp_path):
    guitar_path = r"C:\dev\MUSE-ai\MUSE\instruments\strings\funk\RnB-Guitar-RckGut Gtr E.WAV"
    pad_path = r"C:\dev\MUSE-ai\MUSE\instruments\synths\pads\Inst-Pad-Cloud Pad C0.WAV"
    plain_path = r"C:\dev\MUSE-ai\MUSE\instruments\keys\Classic Piano C4.WAV"

    guitar = AnalyzedInstrument(
        path=guitar_path,
        name="RnB-Guitar-RckGut Gtr E",
        category=InstrumentCategory.GUITAR,
        profile=SonicProfile(sample_path=guitar_path, sample_name="RnB-Guitar-RckGut Gtr E", category="guitar"),
    )
    pad = AnalyzedInstrument(
        path=pad_path,
        name="Inst-Pad-Cloud Pad C0",
        category=InstrumentCategory.SYNTH,
        profile=SonicProfile(sample_path=pad_path, sample_name="Inst-Pad-Cloud Pad C0", category="synths"),
    )
    plain = AnalyzedInstrument(
        path=plain_path,
        name="Classic Piano C4",
        category=InstrumentCategory.KEYS,
        profile=SonicProfile(sample_path=plain_path, sample_name="Classic Piano C4", category="keys"),
    )

    class FakeLibrary:
        instruments = {guitar.path: guitar, pad.path: pad, plain.path: plain}
        by_category = {
            InstrumentCategory.GUITAR: [guitar],
            InstrumentCategory.SYNTH: [pad],
            InstrumentCategory.KEYS: [plain],
        }

        def list_categories(self):
            return ["guitar", "synths", "keys"]

        def get_source_summary(self):
            return {}

    monkeypatch.setattr("multimodal_gen.load_multiple_libraries", lambda *args, **kwargs: FakeLibrary())

    completed = []
    worker = InstrumentScanWorker(completion_callback=completed.append)
    worker._execute_scan("scan-test", [r"C:\dev\MUSE-ai\MUSE\instruments"], cache_dir=str(tmp_path))
    worker.shutdown()

    result = json.loads((tmp_path / "instrument_scan_scan-test.json").read_text(encoding="utf-8"))
    assert completed[0]["manifest_path"] == str(tmp_path / "instrument_scan_scan-test.json")
    guitar_payload = result["instruments"]["guitar"][0]
    pad_payload = result["instruments"]["synth"][0]
    plain_payload = result["instruments"]["keys"][0]

    assert guitar_payload["name"] == "RnB-Guitar-RckGut Gtr E"
    assert guitar_payload["display_name"] == "Guitar-RckGut Gtr E"
    assert guitar_payload["filename"] == "RnB-Guitar-RckGut Gtr E.WAV"
    assert guitar_payload["path"] == guitar_path
    assert guitar_payload["absolute_path"] == guitar_path
    assert guitar_payload["category"] == "guitar"

    assert pad_payload["name"] == "Inst-Pad-Cloud Pad C0"
    assert pad_payload["display_name"] == "Pad-Cloud Pad C0"
    assert plain_payload["name"] == "Classic Piano C4"
    assert plain_payload["display_name"] == "Classic Piano C4"
