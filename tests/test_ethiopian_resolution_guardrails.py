import pytest

from multimodal_gen.expansion_manager import (
    ExpansionInstrument,
    ExpansionManager,
    ExpansionPack,
    InstrumentRole,
    MatchType as ExpansionMatchType,
)
from multimodal_gen.instrument_resolution import InstrumentResolutionService


def _funk_only_manager() -> ExpansionManager:
    pack = ExpansionPack(
        id="funk_o_rama",
        name="Funk O Rama",
        path="C:/synthetic/funk_o_rama",
        target_genres=["funk"],
    )
    pack.instruments = {
        "wah_guitar": ExpansionInstrument(
            id="wah_guitar",
            name="Wah Guitar",
            path="C:/synthetic/funk_o_rama/wah_guitar.wav",
            expansion_id=pack.id,
            category="melodic",
            subcategory="guitar",
            role=InstrumentRole.MELODIC_STRING,
            tags=["funk", "guitar", "wah"],
        ),
        "horn_stabs": ExpansionInstrument(
            id="horn_stabs",
            name="Horn Stabs",
            path="C:/synthetic/funk_o_rama/horn_stabs.wav",
            expansion_id=pack.id,
            category="melodic",
            subcategory="horns",
            role=InstrumentRole.MELODIC_WIND,
            tags=["funk", "horn", "brass"],
        ),
        "clav_keys": ExpansionInstrument(
            id="clav_keys",
            name="Clav Keys",
            path="C:/synthetic/funk_o_rama/clav_keys.wav",
            expansion_id=pack.id,
            category="melodic",
            subcategory="keys",
            role=InstrumentRole.MELODIC_KEYS,
            tags=["funk", "keys", "clav"],
        ),
    }

    manager = ExpansionManager()
    manager.expansions[pack.id] = pack
    manager._rebuild_matcher()
    return manager


@pytest.mark.parametrize(
    ("requested", "expected_program"),
    [
        ("krar", 110),
        ("masenqo", 111),
        ("washint", 112),
        ("brass", 61),
    ],
)
def test_ethiopian_family_semantic_guardrails_fall_back_to_builtins(
    requested: str,
    expected_program: int,
):
    manager = _funk_only_manager()

    expansion_result = manager.resolve_instrument(requested, genre="ethio_jazz")

    assert expansion_result.match_type == ExpansionMatchType.DEFAULT
    assert expansion_result.path == ""
    assert expansion_result.source == "none"
    assert "built-ins" in expansion_result.note.lower()

    service = InstrumentResolutionService(
        expansion_manager=manager,
        auto_register_expansions=False,
    )
    resolved = service.resolve_instrument(requested, genre="ethio_jazz")

    assert resolved.source == "builtin"
    assert resolved.match_type == "default"
    assert resolved.program == expected_program
    assert resolved.name == requested
