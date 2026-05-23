"""Focused regressions for the bounded InstrumentPatch backend registry."""

from multimodal_gen.instrument_patch import (
    build_track_scoped_instrument_patches,
    enrich_instrument_patches_with_resolved_samples,
    normalize_instrument_alias,
)


def test_normalize_instrument_alias_handles_bounded_current_families():
    assert normalize_instrument_alias("electric guitar") == "guitar"
    assert normalize_instrument_alias("crunchy_guitar") == "guitar"
    assert normalize_instrument_alias("piano") == "keys"
    assert normalize_instrument_alias("krar") == "krar"
    assert normalize_instrument_alias("unknown_family") is None


def test_build_track_scoped_instrument_patches_is_ordered_and_deduped():
    patches = build_track_scoped_instrument_patches(
        ["electric guitar", "krar", "crunchy_guitar", "washint", "unknown_family"],
        genre="ethio_jazz",
    )

    assert [patch.patch_id for patch in patches] == [
        "core.guitar.track.v1",
        "ethiopian.krar.track.v1",
        "ethiopian.washint.track.v1",
    ]

    krar_patch = patches[1]
    assert krar_patch.scope == "track"
    assert krar_patch.patch_profile.family == "ethiopian_string"
    assert "ethio_jazz" in krar_patch.patch_profile.genre_tags
    assert krar_patch.synthesis_voice is not None
    assert krar_patch.synthesis_voice.transient_layer is not None
    assert krar_patch.synthesis_voice.transient_layer.source == "pick"


def test_enrich_instrument_patches_adds_unique_resolved_sample_layer(tmp_path):
    guitar_sample = tmp_path / "crunch_guitar.wav"
    guitar_sample.write_bytes(b"RIFF")

    patches = build_track_scoped_instrument_patches(["electric guitar"], genre="rock")
    enriched = enrich_instrument_patches_with_resolved_samples(
        patches,
        [
            {
                "category": "guitar",
                "name": "Crunch Guitar",
                "path": str(guitar_sample),
            }
        ],
    )

    assert patches[0].sample_layers == []
    assert len(enriched[0].sample_layers) == 1
    assert enriched[0].sample_layers[0].path_hint == str(guitar_sample)
    assert enriched[0].sample_layers[0].category_hint == "guitar"


def test_enrich_instrument_patches_uses_exact_name_hints_before_broad_category_fallback(tmp_path):
    hammond_sample = tmp_path / "hammond_b3.wav"
    hammond_sample.write_bytes(b"RIFF")
    pad_sample = tmp_path / "warm_pad.wav"
    pad_sample.write_bytes(b"RIFF")

    patches = build_track_scoped_instrument_patches(["hammond organ"], genre="classic_rock")
    enriched = enrich_instrument_patches_with_resolved_samples(
        patches,
        [
            {
                "category": "keys",
                "name": "Hammond B3",
                "path": str(hammond_sample),
            },
            {
                "category": "pad",
                "name": "Warm Pad",
                "path": str(pad_sample),
            },
        ],
    )

    assert len(enriched[0].sample_layers) == 1
    assert enriched[0].sample_layers[0].path_hint == str(hammond_sample)
    assert enriched[0].sample_layers[0].category_hint == "keys"


def test_enrich_instrument_patches_leaves_ambiguous_matches_empty(tmp_path):
    guitar_a = tmp_path / "clean_guitar.wav"
    guitar_a.write_bytes(b"RIFF")
    guitar_b = tmp_path / "lead_guitar.wav"
    guitar_b.write_bytes(b"RIFF")

    patches = build_track_scoped_instrument_patches(["guitar"], genre="rock")
    enriched = enrich_instrument_patches_with_resolved_samples(
        patches,
        [
            {
                "category": "guitar",
                "name": "Clean Guitar",
                "path": str(guitar_a),
            },
            {
                "category": "guitar",
                "name": "Lead Guitar",
                "path": str(guitar_b),
            },
        ],
    )

    assert enriched[0].sample_layers == []
