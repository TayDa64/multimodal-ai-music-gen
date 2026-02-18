from multimodal_gen.intelligence.auto_producer import auto_score_plan_v1


def test_auto_producer_ambient_avoids_drums_when_not_requested():
    plan = auto_score_plan_v1(
        "ambient cinematic soundscape in C minor with atmospheric pads and drone",
        seed=123,
        duration_bars=16,
        genre_hint="ambient",
    )
    assert plan["schema_version"] == "score_plan_v1"
    assert all(track["role"] != "drums" for track in plan["tracks"])
    constraints = plan.get("constraints", {})
    assert "avoid_drums" in constraints


def test_auto_producer_includes_drums_when_requested():
    plan = auto_score_plan_v1(
        "ambient with drums and soft percussion",
        seed=321,
        duration_bars=8,
        genre_hint="ambient",
    )
    assert any(track["role"] == "drums" for track in plan["tracks"])
