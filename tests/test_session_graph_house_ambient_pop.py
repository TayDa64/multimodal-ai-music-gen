"""Focused regressions for house/ambient/pop session graph tracks."""

from multimodal_gen.prompt_parser import PromptParser
from multimodal_gen.session_graph import Role, SessionGraphBuilder


TASK_067_PROMPT = (
    "atmospheric house pop track with pads, four-on-floor drums, bass, "
    "hook synth, 124 BPM in A minor"
)


def _track_shapes(graph):
    return [(track.name, track.role, track.channel) for track in graph.tracks]


def test_house_pop_session_graph_matches_midi_contract_with_pad_and_hook_synth():
    parsed = PromptParser().parse(TASK_067_PROMPT)
    graph = SessionGraphBuilder().build_from_prompt(parsed)

    assert parsed.genre == "house"
    assert _track_shapes(graph) == [
        ("Drums", Role.DRUMS.value, 9),
        ("Bass", Role.BASS.value, 1),
        ("Pad", Role.PAD.value, 2),
        ("Hook Synth", Role.LEAD.value, 3),
    ]


def test_house_session_graph_uses_chords_without_pad_cue_and_no_default_lead():
    parsed = PromptParser().parse("house groove with drums, bass, 124 BPM in A minor")
    graph = SessionGraphBuilder().build_from_prompt(parsed)

    assert _track_shapes(graph) == [
        ("Drums", Role.DRUMS.value, 9),
        ("Bass", Role.BASS.value, 1),
        ("Chords", Role.CHORDS.value, 2),
    ]