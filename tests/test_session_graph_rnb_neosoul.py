"""Focused regressions for R&B/neo-soul session graph tracks."""

from multimodal_gen.prompt_parser import PromptParser
from multimodal_gen.session_graph import Role, SessionGraphBuilder


TASK_065_PROMPT = (
    "neo-soul R&B groove with warm electric piano, bass, laid-back drums, "
    "lush chords, 82 BPM in F minor"
)


def _track_shapes(graph):
    return [(track.name, track.role, track.channel) for track in graph.tracks]


def test_neo_soul_session_graph_matches_midi_contract_without_default_lead():
    parsed = PromptParser().parse(TASK_065_PROMPT)
    graph = SessionGraphBuilder().build_from_prompt(parsed)

    assert parsed.genre == "neo_soul"
    assert _track_shapes(graph) == [
        ("Drums", Role.DRUMS.value, 9),
        ("Bass", Role.BASS.value, 1),
        ("Rhodes", Role.CHORDS.value, 2),
    ]


def test_neo_soul_session_graph_adds_melody_only_for_explicit_cue():
    parsed = PromptParser().parse(TASK_065_PROMPT + " with a vocal chop hook")
    graph = SessionGraphBuilder().build_from_prompt(parsed)

    assert ("Melody", Role.LEAD.value, 3) in _track_shapes(graph)