# Copilot Models Integration Phase Plan (Grounded)

## Objective
Integrate GitHub Copilot model orchestration into the chat-driven generation flow while preserving current architecture:
- Electron chat UI + agent orchestrator (`copilot-Liku-cli`)
- Python generation gateway + JSON-RPC/OSC (`MUSE/multimodal_gen/server`)
- JUCE C++ audio engine as render/performance target (`MUSE/juce`)

## Source-of-Truth Constraints
- Chat UI is custom Electron DOM, not JUCE chat bubbles.
- `ai-service.js` already routes premium Copilot models.
- `python-bridge.js` already provides stable JSON-RPC transport.
- `reference_analyzer.py` already does yt-dlp/librosa/chord/spectral extraction.
- JUCE protocol boundary remains structured JSON via `Messages.h` / `PROTOCOL.md`.

## Optimized Synthesis of Option 1 + Option 2
Use a **hybrid control plane**:
1. **Director/Producer orchestration in Electron** (Option 1).
2. **Acoustic bridge in Python for reference inputs** (Option 2), then feed extracted profile to LLM planning.

This avoids duplicating analyzers, avoids JUCE-side HTTP/model complexity, and keeps provider flexibility.

---

## Phase 0 — Baseline & Guardrails
- Confirm no protocol break for existing generate/produce flow.
- Add a compatibility matrix (no-reference vs reference URL/file).
- Define rollback: disable reference grounding via feature toggle.

Exit Criteria:
- Existing `/produce` and standard generation still pass smoke checks.

## Phase 1 — Reference Grounding (Implemented)
- Add JSON-RPC method `analyze_reference` in Python server.
- Wire Producer agent to optionally call `analyze_reference` before score-plan generation.
- Pass optional `referenceUrl` from chat route into producer options.

Exit Criteria:
- With reference URL/path: producer receives profile (`bpm/key/mode/style_tags/generation_params`).
- Without reference: behavior unchanged.

## Phase 2 — Multi-Agent Model Specialization
- Director model: premium conversational model for creative plan framing.
- Producer model: premium structured-output model for strict score-plan JSON.
- Add explicit model selection policy in producer prompts and telemetry metadata.

Exit Criteria:
- Distinct role prompts and model selection are visible in logs/metadata.

Implementation Notes (Completed):
- Producer now resolves role models via `modelPolicy` (`director`, `producer`) with premium defaults.
- Initial planning now runs a Director guidance pass, then Producer JSON pass.
- Planning telemetry now returns selected role models and reference-grounding usage in producer results.

## Phase 3 — Protocol-Aligned Structured Handoff
- Introduce stable producer output schema subset aligned with Python generation params.
- Add strict validation and fallback normalization in producer.
- Keep JUCE protocol unchanged; only feed valid current fields.

Exit Criteria:
- Invalid producer JSON never reaches generation worker unvalidated.

Implementation Notes (Completed):
- Producer now sanitizes score plans to a stable schema-aligned subset before handoff.
- Strict validation checks required fields, enums, bounds, and nested structures (`sections`, `tracks`, `cue_points`, `constraints`).
- Invalid plans auto-fallback to a guaranteed-valid baseline score plan, then re-validate.
- Validation telemetry is returned per stage/attempt (`validBefore`, `validAfter`, `fallbackApplied`, error arrays).

## Phase 4 — Verification Pipeline (Premium Verifier)
- Add verifier pass for plan validity and critic pre-check before generation run.
- Add post-run verification summary in chat response (critics + output analyzer).

Exit Criteria:
- Producer response includes plan validation + generation quality summary.

Implementation Notes (Completed):
- Producer now invokes Verifier preflight gate before each generation attempt.
- Preflight combines deterministic checks with premium-model review and blocks invalid plans.
- Failed preflight triggers refinement retries (when attempts remain) instead of unsafe generation.
- Post-run verification now includes both MIDI critics and rendered output analysis.
- Producer response text now surfaces preflight status, critic summary, and output-analysis score.

## Phase 5 — JUCE UX Bridging (Non-invasive)
- Surface phase states to JUCE-compatible status channels (no new render-thread logic).
- Keep JUCE focused on audio/MIDI and transport status only.

Exit Criteria:
- Users see clear progression states; no JUCE thread or transport regressions.

Implementation Notes (Completed):
- Added producer phase-state timeline in Electron producer results using JUCE-compatible fields: `step`, `percent`, `message`, `timestamp`.
- Added `status_updates` timeline to Python `produce_sync` JSON-RPC response using the same progress-shape fields.
- No changes made to JUCE render/audio threads or DSP paths; all updates are control-plane metadata only.

---

## Premium Model Usage Policy
- Research/analysis: premium reasoning model.
- Planning/director: premium conversational model.
- Structured producer output: premium model with strict JSON discipline.
- Verification: premium verifier model for pre/post checks.

(Exact model IDs remain configurable in `ai-service.js` / provider settings.)

## Verification Checklist Per Phase
1. Backward compatibility with no-reference prompts.
2. JSON-RPC method contract stability and error semantics.
3. Producer output schema validity and fallback behavior.
4. Critic/analyzer results still populate expected fields.
5. No JUCE render-path or protocol break.
