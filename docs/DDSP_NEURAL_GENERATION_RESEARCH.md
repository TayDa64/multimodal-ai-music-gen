# DDSP / Neural Audio Generation Research (bounded) — 2026-05-22

This document is a **research note** for adding DDSP / neural audio generation to the MUSE repo.
It does **not** claim that DDSP/neural generation is implemented today.

## 1) Current repo state (grounded)

**What exists today (Python backend):**
- `multimodal_gen/audio_renderer.py` supports:
  - FluidSynth + SoundFont rendering (external `fluidsynth` binary)
  - procedural synthesis fallback (`multimodal_gen/assets_gen.py`)
  - optional expansion/sample routing (`ExpansionManager` + `InstrumentResolutionService`)
  - post-FluidSynth **file-level mastering** path for parity (`_apply_file_level_mastering(..., stage_prefix="fluidsynth_file_mastering")`)
- DSP / mix presets exist in `multimodal_gen/mix_chain.py` (now includes a bounded wow/flutter stage for lo-fi).

**What does *not* exist today:**
- No neural audio synthesis engine integrated into the runtime pipeline.
- No model weights are vendored.
- No GPU/accelerated inference stack is wired.

## 2) Candidate libraries / model families

### A) Google Magenta / DDSP
- **DDSP** (Differentiable Digital Signal Processing) models often target:
  - monophonic instruments (violin, flute, voice)
  - timbre transfer (audio-to-audio)
  - controllable synthesis via F0 + loudness + latent controls
- Practical reality:
  - many reference implementations are research-grade
  - training/inference can be heavy

### B) Neural vocoders / diffusion-based audio (general)
- Examples (ecosystem-level, not repo-committed):
  - diffusion vocoders / audio diffusion models
  - text-to-audio models (often large, GPU-first)
- Risk for this repo:
  - dependency weight, GPU requirements, model licensing
  - reproducibility and offline-first constraints

### C) Lightweight neural timbre models (bounded)
- Small model approach:
  - on-device inference for a **single** target instrument family
  - treat as an *optional renderer* behind feature flags

## 3) Natural integration points in this codebase

### Renderer seam (lowest risk)
- Add a new optional synthesizer backend under `multimodal_gen/synthesizers/`.
- Keep `AudioRenderer` selection logic unchanged by default:
  - FluidSynth when available and allowed
  - procedural fallback otherwise
  - **neural backend only when explicitly enabled**

### File-level post-processing seam
- Neural render output would still be routed through existing mastering:
  - reuse `_apply_file_level_mastering()` and report stages via `pipeline_stages.*`.

### Dataset / prompts seam
- Training/eval data candidates already flow through:
  - prompt parsing (`PromptParser`)
  - generation outputs (`project_metadata.json`, render reports)
  - golden prompt suites under `tests/` + `output_cli_golden*`

## 4) Prerequisites / operational constraints

- **Compute:** GPU strongly recommended for most neural audio models.
- **Dependencies:** typically `torch`, sometimes `jax`, plus model-specific deps.
- **Artifacts:** model weights are often 100s of MB to many GB.
- **Licensing:** must validate redistribution rights for weights and training data.

Repo-specific constraints to respect:
- “Offline-first” and “bounded changes” are core principles.
- Tests should remain runnable without a GPU.

## 5) Phased proposal (bounded, additive)

### Phase 0 — Observability only (safe)
- Add a *diagnostic capability report* for a future neural backend:
  - "available": False (unless deps detected)
  - version fields
  - selected renderer path

### Phase 1 — Optional inference backend stub
- Add `NeuralSynthesizer` interface implementation returning:
  - `success=False` with a clear skip reason when deps/weights missing
- Ensure the render report records:
  - `renderer_path="neural"` only when it truly ran
  - otherwise it must remain FluidSynth/procedural

### Phase 2 — One bounded target instrument
- Choose a single family (e.g., monophonic bass or lead)
- Route only a narrow MIDI program range through the neural backend
- Keep procedural fallback on failure

### Phase 3 — Eval + acceptance gates
- Add a small eval dataset:
  - fixed seeds, short duration, controlled program ranges
  - measured via existing file analysis + render report diagnostics

## 6) No-overclaim note

Neural generation is a large surface area.
This repo can integrate it safely only as an **explicitly opt-in**, **bounded**,
**fail-open** renderer backend with clear diagnostics and without breaking the
existing FluidSynth/procedural workflows.
