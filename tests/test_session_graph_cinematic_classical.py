"""Focused regressions for cinematic/classical session graph tracks."""

from multimodal_gen.prompt_parser import PromptParser
from multimodal_gen.session_graph import Role, SessionGraphBuilder


TASK_063_PROMPT = (
    "cinematic orchestral film score with strings, brass, choir, timpani, "
    "evolving sections, 96 BPM in D minor"
)


def _track_shapes(graph):
    return [(track.name, track.role, track.channel) for track in graph.tracks]


def test_cinematic_classical_session_graph_preserves_orchestral_sections():
    parsed = PromptParser().parse(TASK_063_PROMPT)
    graph = SessionGraphBuilder().build_from_prompt(parsed)

    assert parsed.genre == "cinematic"
    assert {"strings", "brass", "choir", "timpani"}.issubset(set(parsed.instruments))

    tracks = _track_shapes(graph)
    assert ("Drums", Role.DRUMS.value, 9) in tracks
    assert ("Strings", Role.PAD.value, 2) in tracks
    assert ("Brass", Role.LEAD.value, 5) in tracks
    assert ("Choir", Role.PAD.value, 6) in tracks
    assert ("Timpani", Role.PERCUSSION.value, 8) in tracks
    assert not any(track.name == "Bass" for track in graph.tracks)


def test_cinematic_classical_manifest_preserves_orchestral_sections():
    parsed = PromptParser().parse(TASK_063_PROMPT)
    manifest = SessionGraphBuilder().build_from_prompt(parsed).to_dict()
    tracks = [(track["name"], track["role"], track["channel"]) for track in manifest["tracks"]]

    assert ("Drums", Role.DRUMS.value, 9) in tracks
    assert ("Strings", Role.PAD.value, 2) in tracks
    assert ("Brass", Role.LEAD.value, 5) in tracks
    assert ("Choir", Role.PAD.value, 6) in tracks
    assert ("Timpani", Role.PERCUSSION.value, 8) in tracks
    assert not any(track["name"] == "Bass" for track in manifest["tracks"])
