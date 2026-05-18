"""Focused regressions for lofi/boom-bap session graph tracks."""

from multimodal_gen.prompt_parser import PromptParser
from multimodal_gen.session_graph import Role, SessionGraphBuilder


TASK_066_PROMPT = (
    "lofi boom bap groove with dusty drums, warm bass, mellow keys, "
    "vinyl texture, 88 BPM in C minor"
)


def _track_shapes(graph):
    return [(track.name, track.role, track.channel) for track in graph.tracks]


def test_boom_bap_session_graph_matches_stable_lofi_contract_without_default_lead():
    parsed = PromptParser().parse(TASK_066_PROMPT)
    graph = SessionGraphBuilder().build_from_prompt(parsed)

    assert parsed.genre == "boom_bap"
    assert _track_shapes(graph) == [
        ("Drums", Role.DRUMS.value, 9),
        ("Bass", Role.BASS.value, 1),
        ("Keys", Role.CHORDS.value, 2),
        ("Vinyl", Role.TEXTURE.value, 4),
    ]


def test_boom_bap_session_graph_adds_melody_only_for_explicit_cue():
    parsed = PromptParser().parse(TASK_066_PROMPT + " with a hook melody")
    graph = SessionGraphBuilder().build_from_prompt(parsed)

    assert ("Melody", Role.LEAD.value, 3) in _track_shapes(graph)