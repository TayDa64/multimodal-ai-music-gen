"""Focused regressions for trap/modern-beat session graph tracks."""

from multimodal_gen.prompt_parser import PromptParser
from multimodal_gen.session_graph import Role, SessionGraphBuilder


TASK_064_PROMPT = (
    "dark trap modern beat with 808 bass, snare, hihat rolls, sparse melody, "
    "140 BPM in C minor"
)


def _track_shapes(graph):
    return [(track.name, track.role, track.channel) for track in graph.tracks]


def test_trap_modern_session_graph_matches_midi_contract():
    parsed = PromptParser().parse(TASK_064_PROMPT)
    graph = SessionGraphBuilder().build_from_prompt(parsed)

    assert parsed.genre == "trap"
    assert {"808", "bass"}.issubset(set(parsed.instruments))
    assert {"808", "snare", "hihat", "hihat_roll"}.issubset(set(parsed.drum_elements))

    tracks = _track_shapes(graph)
    assert ("Drums", Role.DRUMS.value, 9) in tracks
    assert ("Bass", Role.BASS.value, 1) in tracks
    assert ("Melody", Role.LEAD.value, 3) in tracks or ("Synth Lead", Role.LEAD.value, 3) in tracks
    assert not any(track.name == "808" and track.role == Role.LEAD.value for track in graph.tracks)


def test_trap_modern_manifest_preserves_same_tracks():
    parsed = PromptParser().parse(TASK_064_PROMPT)
    manifest = SessionGraphBuilder().build_from_prompt(parsed).to_dict()
    tracks = [(track["name"], track["role"], track["channel"]) for track in manifest["tracks"]]

    assert ("Drums", Role.DRUMS.value, 9) in tracks
    assert ("Bass", Role.BASS.value, 1) in tracks
    assert ("Melody", Role.LEAD.value, 3) in tracks or ("Synth Lead", Role.LEAD.value, 3) in tracks
    assert not any(
        track["name"] == "808" and track["role"] == Role.LEAD.value
        for track in manifest["tracks"]
    )