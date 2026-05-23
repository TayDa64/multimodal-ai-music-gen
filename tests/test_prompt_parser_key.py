from multimodal_gen.prompt_parser import PromptParser
from multimodal_gen.utils import ScaleType


EXACT_1990S_ROCK_PROMPT = (
    "1990's era rock song with crunchy electric guitar, live drums, "
    "bass guitar, verse chorus bridge, energetic band performance, "
    "100 BPM in E minor"
)

GENERIC_JAZZ_PROMPT = (
    "small-combo jazz quartet with walking bass, ride cymbal, "
    "piano comping, 120 BPM in Bb major"
)

WARM_SAX_JAZZ_PROMPT = (
    "small-combo jazz quartet with walking upright bass, ride cymbal swing, "
    "acoustic piano comping, warm saxophone lead, 120 BPM in Bb major"
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


def test_generic_jazz_prompt_parses_as_combo_defaults_without_trap_fallbacks():
    parsed = PromptParser().parse(GENERIC_JAZZ_PROMPT)

    assert parsed.genre == "jazz"
    assert parsed.bpm == 120
    assert parsed.key == "Bb"
    assert parsed.scale_type.name.lower() == "major"

    assert "piano" in parsed.instruments
    assert "bass" in parsed.instruments
    assert not {"krar", "masenqo", "washint", "begena", "kebero", "atamo"} & set(parsed.instruments)

    for element in ["kick", "snare", "hihat", "ride"]:
        assert element in parsed.drum_elements
    assert "crash" not in parsed.drum_elements
    assert "808" not in parsed.drum_elements
    assert "hihat_roll" not in parsed.drum_elements


def test_warm_saxophone_jazz_prompt_preserves_explicit_sax_not_generic_brass():
    parsed = PromptParser().parse(WARM_SAX_JAZZ_PROMPT)

    assert parsed.genre == "jazz"
    assert parsed.bpm == 120
    assert parsed.key == "Bb"
    assert parsed.scale_type.name.lower() == "major"
    assert "sax" in parsed.instruments or "saxophone" in parsed.instruments
    assert "brass" not in parsed.instruments


def test_classic_rock_hammond_prompt_preserves_organ_cue():
    parsed = PromptParser().parse(
        "classic rock anthem with crunchy electric guitar, Hammond organ, "
        "melodic bass guitar, live drums, verse chorus bridge, 108 BPM in A minor"
    )

    assert parsed.genre == "classic_rock"
    assert parsed.bpm == 108
    assert parsed.key == "A"
    assert parsed.scale_type.name.lower() == "minor"
    assert "guitar" in parsed.instruments
    assert "bass" in parsed.instruments
    assert "organ" in parsed.instruments
    assert "choir" not in parsed.instruments
    assert "808" not in parsed.drum_elements


def test_explicit_jazz_horns_stay_distinct_while_brass_section_stays_generic():
    parser = PromptParser()

    trumpet = parser.parse("jazz quartet with trumpet lead and walking bass")
    trombone = parser.parse("jazz quartet with trombone lead and walking bass")
    brass_section = parser.parse("jazz quartet with brass section hits and horns")

    assert trumpet.genre == "jazz"
    assert "trumpet" in trumpet.instruments
    assert "brass" not in trumpet.instruments

    assert trombone.genre == "jazz"
    assert "trombone" in trombone.instruments
    assert "brass" not in trombone.instruments

    assert brass_section.genre == "jazz"
    assert "brass" in brass_section.instruments
    assert not {"sax", "saxophone", "trumpet", "trombone"} & set(brass_section.instruments)


def test_generic_jazz_combo_defaults_honor_excluded_drums():
    parser = PromptParser()

    for prompt, excluded in [
        ("jazz quartet --no kick", "kick"),
        ("jazz quartet --no hihat", "hihat"),
    ]:
        parsed = parser.parse(prompt)

        assert parsed.genre == "jazz"
        assert excluded in parsed.excluded_drums
        assert excluded not in parsed.drum_elements
        assert "808" not in parsed.drum_elements
        assert "hihat_roll" not in parsed.drum_elements


def test_ethio_jazz_priority_survives_generic_jazz_keywords():
    parser = PromptParser()

    for prompt in [
        "ethio-jazz groove with krar comping and ride cymbal",
        "ethiopian jazz in Addis with Mulatu Astatke brass lines",
        "Ethiopiques style jazz with swinging Addis nightlife energy",
    ]:
        parsed = parser.parse(prompt)
        assert parsed.genre == "ethio_jazz"
        assert parsed.time_signature == (6, 8)


def test_ethio_jazz_traditional_key_prefers_ethiopian_scale_and_defaults():
    parsed = PromptParser().parse(
        "generate a modern ethiopian jazzy song 16 bars, in traditional key"
    )

    assert parsed.genre == "ethio_jazz"
    assert parsed.time_signature == (6, 8)
    assert parsed.scale_type == ScaleType.ETHIO_JAZZ
    assert {"krar", "washint"} & set(parsed.instruments)
    assert "piano" in parsed.instruments
    assert "bass" in parsed.instruments


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
