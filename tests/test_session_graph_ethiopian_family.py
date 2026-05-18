"""Focused regressions for Ethiopian-family session graph tracks."""

from multimodal_gen.prompt_parser import PromptParser
from multimodal_gen.session_graph import Role, SessionGraphBuilder


TASK_068_PROMPT = (
    "Ethiopian jazz inspired groove with pentatonic melody, bass, "
    "hand percussion feel, 104 BPM in G minor"
)


def _track_shapes(graph):
    return [(track.name, track.role, track.channel) for track in graph.tracks]


def test_ethio_jazz_session_graph_matches_midi_contract_with_explicit_melody():
    parsed = PromptParser().parse(TASK_068_PROMPT)
    graph = SessionGraphBuilder().build_from_prompt(parsed)

    assert parsed.genre == "ethio_jazz"
    assert _track_shapes(graph) == [
        ("Drums", Role.DRUMS.value, 9),
        ("Bass", Role.BASS.value, 1),
        ("Melody", Role.LEAD.value, 3),
    ]
    assert _track_shapes(graph).count(("Bass", Role.LEAD.value, 2)) == 0


def test_ethiopian_family_preserves_explicit_instrument_roles_conservatively():
    parsed = PromptParser().parse(
        "ethiopian traditional groove with krar, washint, kebero, bass, 104 BPM in G minor"
    )
    graph = SessionGraphBuilder().build_from_prompt(parsed)

    assert ("Drums", Role.DRUMS.value, 9) in _track_shapes(graph)
    assert ("Bass", Role.BASS.value, 1) in _track_shapes(graph)
    assert ("Krar", Role.ETHIOPIAN_STRING.value, 2) in _track_shapes(graph)
    assert ("Washint", Role.ETHIOPIAN_WIND.value, 3) in _track_shapes(graph)
    assert ("Kebero", Role.ETHIOPIAN_DRUM.value, 4) in _track_shapes(graph)