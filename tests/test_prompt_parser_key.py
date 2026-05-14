from multimodal_gen.prompt_parser import PromptParser


EXACT_1990S_ROCK_PROMPT = (
    "1990's era rock song with crunchy electric guitar, live drums, "
    "bass guitar, verse chorus bridge, energetic band performance, "
    "100 BPM in E minor"
)


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


def test_neo_soul_parses_as_first_class_genre():
    parser = PromptParser()
    parsed = parser.parse("neo soul groove in D minor with rhodes, bass, and laid back drums")
    assert parsed.genre == "neo_soul"


def test_exact_1990s_rock_prompt_parses_as_band_defaults_without_trap_fallbacks():
    parsed = PromptParser().parse(EXACT_1990S_ROCK_PROMPT)

    assert parsed.genre == "rock"
    assert parsed.bpm == 100
    assert parsed.key == "E"
    assert parsed.scale_type.name.lower() == "minor"

    assert "guitar" in parsed.instruments
    assert "bass" in parsed.instruments
    assert "choir" not in parsed.instruments

    for element in ["kick", "snare", "hihat", "hihat_open", "crash", "ride"]:
        assert element in parsed.drum_elements
    assert "808" not in parsed.drum_elements
    assert "clap" not in parsed.drum_elements

    assert "verse" in parsed.section_hints
    assert "drop" in parsed.section_hints  # chorus is currently represented as a drop/hook hint
    assert "breakdown" in parsed.section_hints  # bridge maps to the breakdown hint


def test_90s_boom_bap_and_hip_hop_still_route_to_boom_bap():
    parser = PromptParser()

    assert parser.parse("90s boom bap hip hop with dusty drums").genre == "boom_bap"
    assert parser.parse("90s hip hop beat with dusty drums").genre == "boom_bap"


def test_soul_family_priority_survives_rock_additions():
    parser = PromptParser()

    assert parser.parse("neo soul groove in D minor with rhodes and bass").genre == "neo_soul"
    assert parser.parse("trap soul ballad with 808 and rhodes").genre == "trap_soul"
    assert parser.parse("rnb slow jam with guitar and live drums").genre == "rnb"


def test_chorus_is_section_hint_not_choir_without_explicit_voice_language():
    parser = PromptParser()

    explicit_choir = parser.parse("choir voices over rock guitars")
    assert explicit_choir.genre == "rock"
    assert "choir" in explicit_choir.instruments
    assert "guitar" in explicit_choir.instruments

    section_only = parser.parse("verse chorus bridge rock song")
    assert section_only.genre == "rock"
    assert "choir" not in section_only.instruments
    assert "verse" in section_only.section_hints
    assert "drop" in section_only.section_hints
    assert "breakdown" in section_only.section_hints


def test_unknown_genre_still_fails_open_to_safe_default():
    parsed = PromptParser().parse("unrecognized shimmer texture with no style markers")
    assert parsed.genre == "trap_soul"
