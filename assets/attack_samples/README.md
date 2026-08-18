# Attack-sample hybrid layer (opt-in)

Drop a short recorded **attack transient** here to enrich the procedural
fallback onset for a family. This is an optional hybrid layer: when no asset is
present, rendering is pure procedural and byte-identical.

## Layout
```
assets/attack_samples/<family>/<anything>.wav
```
Currently consumed: `guitar` (non-rock procedural fallback only).

## Sample requirements
- Short pick/pluck transient (the renderer caps it to ~60 ms).
- Any sample rate (auto-resampled to the render rate) and any channel count
  (downmixed to mono). It is unit-normalized on load.
- The first `*.wav` in the family folder is used.

## Shipped assets
- `guitar/guitar_pick_transient_v1.wav` -- self-owned, generated in-repo
  (deterministic) by `scripts/generate_guitar_attack_sample.py`. It is derived
  from the guitar physical-model onset (`generate_guitar_tone` KS pluck + pick
  transient), windowed and fast-faded to keep only the attack (~99% of energy in
  the first 30 ms, near-zero tail, no sustained note), peak-normalized.

## Behavior / fallback
- No folder or no `*.wav` -> `None` -> pure procedural (no change).
- Present -> mixed onto the procedural onset with a velocity-scaled gain, and the
  family is recorded in the renderer's hybrid-usage set so a hybrid render is
  never reported as pure procedural.

## Licensing
Only add samples you are licensed to redistribute (or CC0). The shipped
`guitar_pick_transient_v1.wav` is self-owned (procedurally generated in-repo),
so it is safe to redistribute offline.

## Scope
Rock guitar (`_synthesize_rock_electric_guitar`) and all other families are not
affected by this layer in the current spike.
