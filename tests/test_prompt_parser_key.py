from multimodal_gen.prompt_parser import PromptParser


def test_key_extraction_prefers_explicit_key_over_word_fragments():
    parser = PromptParser()
    parsed = parser.parse(
        "ambient cinematic soundscape in C minor with atmospheric pads, drone, and long reverb tails"
    )
    assert parsed.key == "C"
    assert parsed.scale_type.name.lower() == "minor"


def test_drone_maps_to_pad_instrument():
    parser = PromptParser()
    parsed = parser.parse("ambient drone texture in C minor")
    assert "pad" in parsed.instruments
