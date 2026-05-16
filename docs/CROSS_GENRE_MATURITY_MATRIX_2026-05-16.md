# Task 057 — Cross-Genre Maturity Matrix and Baseline Validation Plan

Date: 2026-05-16  
Task ID: `cross-genre-maturity-matrix-baseline-plan-057`

## Scope

This document is a docs/planning baseline only. It does not implement, tune, render, parse, profile, or analyze anything, and it is not runtime proof for any new genre or subgenre. Its purpose is to capture the conservative current maturity state, define evidence gates, and provide a measured baseline plan for the next runtime task.

Task 057 therefore makes no source, profile, analyzer, renderer, parser, strategy, test, script, asset, SoundFont, WAV, MIDI, or output-diagnostic changes. Runtime measurement starts in Task 058.

## Current status

- Exact 1990s rock is stable v1 / `PASS-WATCH` based on Task 056.
- Task 056 re-rendered the exact 1990s rock control across seeds `199001`, `199002`, and `199003` with direct `main.py`, 16 bars, isolated defaults/expansions, `FluidR3Mono_GM.sf3`, `renderer_path=fluidsynth`, `profile=rock:rock`, and tone `high_shelf=-6.0dB@5000Hz;low_shelf=-0.75dB@90Hz`.
- All three exact-rock runs passed with empty issues, but the worst margins are boundary-close: centroid margin `38.9 Hz` under the `4500 Hz` ceiling and sub-bass margin `0.0015` under the `0.16` ceiling.
- This is not full rock-family masterclass completion. It proves one exact rock control is green and repeatable enough to avoid speculative tuning, while broader rock-family idioms still need measured baselines.

## Existing coverage inventory

- `docs/UPGRADE_PLAN_2026-05-14_1990S_ROCK_QUALITY_UI.md` records Tasks 046-056, including the exact rock FluidSynth isolation, strict audio quality, renderer profiles, matrix proofs, generic jazz closure, paired rock/jazz validation, and Task 056 repeatability checkpoint.
- `scripts/smoke_1990s_rock.ps1` fixed the exact rock smoke path for explicit SoundFont/FluidSynth proof.
- `scripts/smoke_fluidsynth_profile_matrix.ps1` provides the current profile matrix harness for rock, cinematic/classical, trap/modern beat, and generic jazz baselines.
- Existing source supports rock-family keys: `rock`, `classic_rock`, `alternative_rock`, `grunge`, `punk_rock`, and `indie_rock`.
- `hard rock` currently routes to canonical `rock`; there is no separate implemented `hard_rock` genre key to claim in this plan.
- FluidSynth rock-family profile coverage uses `rock:rock` with tone `high_shelf=-6.0dB@5000Hz;low_shelf=-0.75dB@90Hz`.
- Current analyzer targets exist for rock-family keys, but Task 057 does not relax targets and does not claim those targets are robust for every rock subgenre without Task 058 measurements.

## Maturity dimensions

| Dimension | What it asks | Evidence required before raising maturity |
| --- | --- | --- |
| Parser/default route | Does the prompt parse to the intended canonical genre with sensible defaults? | Parser/default evidence and no fallback to unrelated genres. |
| Strategy/arrangement route | Does the genre select the intended strategy and arrangement template? | Strategy registry/template proof plus section structure matching the prompt. |
| MIDI/instrument semantics | Do MIDI tracks use appropriate instruments, ranges, velocities, articulations, and drum parts? | MIDI inspection showing expected guitar/bass/drum or genre-specific semantics. |
| Renderer/profile proof | Does FluidSynth render through the expected profile and tone policy with required SoundFont? | Render report with `renderer_path=fluidsynth`, expected profile, attempted/success true, and no skip reason. |
| Analyzer target coverage | Are measurable analyzer targets present for the parsed genre? | Current target bounds listed and applied without relaxation. |
| Runtime audio baseline | Is there a concrete WAV/MIDI/render-report baseline for the prompt and seed? | Stored ignored diagnostic artifacts and summary paths, not just source inspection. |
| Repeatability/margin health | Does the result stay green across fresh seeds with healthy margins? | Multi-seed proof, margins summarized, and WATCH flags for boundary-close results. |
| Listening/artifact evidence | Is there an auditionable artifact for qualitative review? | WAV path plus notes from listening review; analyzer pass alone is not masterclass quality. |
| Regression coverage | Is the behavior locked by tests or repeatable smoke scripts? | Focused tests or smoke harness evidence that detects regressions without broad side effects. |
| Masterclass idiom coverage | Does the output convincingly express genre idioms beyond passing gates? | Reference-style comparisons, idiom-specific checks, and listening evidence across sections/eras. |

## Maturity levels

| Level | Name | Definition |
| --- | --- | --- |
| L0 | Unsupported/unknown | No reliable route or current evidence; behavior may fall back or be unknown. |
| L1 | Static route | Parser/default/strategy metadata or aliases exist, but renderer/profile/audio quality proof is missing or stale. |
| L2 | Renderer baseline | The genre has a renderer/profile path or matrix harness baseline, but analyzer-green quality and idiom evidence are not established. |
| L3 | Analyzer-green baseline | At least one current runtime baseline is green against current targets with expected metadata and artifacts. |
| L4 | Repeatable robust baseline | Multi-seed runtime proof is green with comfortable margins and no WATCH flags. |
| L5 | Masterclass-ready | Robust runtime proof plus idiom/reference/listening evidence across representative prompts and arrangements. |

Exact 1990s rock is marked `L3 / PASS-WATCH`, not L4, because Task 056 repeated the green result but the centroid and sub-bass margins are boundary-close.

## Current maturity snapshot

| Area | Current maturity | Conservative status | Evidence and caveats |
| --- | --- | --- | --- |
| Exact 1990s rock | L3 / `PASS-WATCH` | Stable v1, not robust L4 | Task 056 three-seed proof passed with `rock:rock`, exact tone, guitar/bass/live drums, and empty issues; boundary-close margins keep it on watch. |
| `classic_rock` | L2 planned baseline | Route/profile/targets exist, dedicated quality baseline pending | Existing key participates in rock-family routing/profile/targets; Task 058 must measure the dedicated prompt before any quality claim. |
| `grunge` | L2 planned baseline | Route/profile/targets exist, dedicated quality baseline pending | Existing key exists; Seattle/grunge idioms and mix behavior are unproven until measured. |
| `punk_rock` | L2 planned baseline | Route/profile/targets exist, dedicated quality baseline pending | Existing key exists; fast power-chord behavior, live drums, and analyzer margins need baseline proof. |
| `indie_rock` | L2 planned baseline | Route/profile/targets exist, dedicated quality baseline pending | Existing key exists; jangly guitar/indie arrangement quality is not proven by exact-rock control. |
| Hard rock as `rock` | L1/L2 canonical-rock route | Must be expected as `rock`, not `hard_rock` | Prompt keyword currently routes to canonical `rock`; Task 058 should measure a hard-rock-as-rock case without claiming a separate implemented key. |
| Generic jazz sax | L3 baseline | Green single-slice quality proof, not broad jazz masterclass | Task 054 proved integrated `jazz:jazz` with `high_shelf=-5.0dB@4000Hz`, sax source controls, and empty issues; broader jazz and repeatability are separate work. |
| Cinematic/classical | L2 matrix baseline | Profile matrix route exists, quality masterclass unproven | Existing profile matrix has a no-op classical profile baseline; orchestration realism and analyzer-green quality need dedicated baselines. |
| Trap/modern beat | L2 matrix baseline | Profile matrix route exists, quality masterclass unproven | Existing profile matrix has a no-op modern-beat baseline; 808/drum quality and margins need priority measurement. |
| R&B / neo-soul / trap-soul | L1 planned | Static route family likely needs fresh SoundFont baseline | Do not infer quality from trap or jazz proofs; measure warm keys, bass, pocket, and vocal-adjacent arrangement cues separately. |
| Lofi / boom_bap / g_funk | L1 planned | Static route family needs baseline | Needs groove, low-pass/noise texture, swing, sample-like drums, and bass evidence before quality claims. |
| House / ambient / pop | L1 planned | Static route family needs baseline | Needs separate electronic drum, pad, sidechain/space, and pop hook evidence; no Task 057 runtime proof. |
| Ethiopian family | L1 planned | GM baseline only until custom-instrument proof exists | Ethiopian or Ethio-jazz GM SoundFont baselines can measure routing, but they are not equal to custom krar/masenqo/kebero or regional masterclass quality. |

## Rock-family masterclass gap decomposition

### Subgenre behavior gaps

| Subgenre case | Desired behavior to measure | Current risk |
| --- | --- | --- |
| Classic rock | Crunchy guitars with organ/piano support, mid-tempo band pocket, verse/chorus/bridge clarity, less sub-bass than generic rock. | May sound like generic rock with insufficient era/style identity. |
| Grunge | Darker distorted guitars, heavier downbeat feel, bass-guitar support, live kit intensity, Seattle/90s contour. | May share generic rock arrangement without grunge-specific density or tone. |
| Punk rock | Fast power-chord drive, high-energy straight drums, short fills, tight bass lock, minimal ornamentation. | Fast prompt may stress drum/onset targets or lose guitar audibility. |
| Indie rock | Jangly or cleaner guitar color, bass movement, live drums, less aggressive mix, song-form clarity. | May overuse generic distorted rock tone or miss jangly articulation. |
| Hard rock as rock | Heavier distorted guitar and arena-band energy while still parsing as canonical `rock`. | Must not be treated as separate `hard_rock`; quality must be judged against current `rock` route/targets. |

### Idiom and quality gaps

- Guitar idioms: riffs, palm muting, power chords, bends, solos, amp/cab tone, guitar-front mix balance, and audible riff presence across sections.
- Drum behavior: fills, section transitions, humanization, crash/ride choices, live kick/snare/hi-hat consistency, and avoiding trap-kit or 808 leakage.
- Bass guitar: groove variation, fills into transitions, lock with kick, electric-bass register, and avoiding synth-bass/sub-heavy fallback.
- Reference-style matching: era-specific differences between classic rock, grunge, punk, indie, and hard-rock-as-rock prompts should be measured with prompts/seeds before any tuning.
- Analyzer coverage: current analyzer gates catch broad rock-family energy/drum/sub-bass issues but do not yet prove audible guitar riff presence or amp/cab realism.
- Longer-form arrangement quality: 16-bar baselines verify route and short-form sections, but masterclass readiness needs longer arcs, transitions, fills, and solo/bridge behavior.

## Rock-family baseline runbook for Task 058

Common output root:

```text
output\_diagnostics\rock_family_baseline_057\run_<timestamp>\<case_id>\seed_<seed>
```

Common flags:

```text
--duration-bars 16 --seed <seed> --no-banner --skip-default-instruments --skip-expansions --require-soundfont --soundfont assets\soundfonts\FluidR3Mono_GM.sf3 --require-audio
```

Baseline cases:

| Case ID | Expected parsed genre | Prompt | Seed |
| --- | --- | --- | --- |
| `classic_rock_baseline` | `classic_rock` | classic rock band with crunchy electric guitar, organ, bass guitar, live drums, verse chorus bridge, 108 BPM in A minor | `57101` |
| `grunge_baseline` | `grunge` | grunge seattle sound band with crunchy guitars, bass guitar, live drum kit, verse chorus bridge, 108 BPM in E minor | `57102` |
| `punk_rock_baseline` | `punk_rock` | punk rock punk band punk song with fast power-chord electric guitar, bass guitar, live drums, verse chorus bridge, 168 BPM in A minor | `57103` |
| `indie_rock_baseline` | `indie_rock` | indie rock indie band with jangly electric guitar, bass guitar, live drums, verse chorus bridge, 112 BPM in D major | `57104` |
| `hard_rock_as_rock_baseline` | `rock` | hard rock band with heavy distorted electric guitar, bass guitar, live drums, verse chorus bridge, 118 BPM in E minor | `57105` |

Repeatability seed plan:

| Case | First seed | Repeat seed 1 | Repeat seed 2 |
| --- | --- | --- | --- |
| Classic rock | `57101` | `57201` | `57301` |
| Grunge | `57102` | `57202` | `57302` |
| Punk rock | `57103` | `57203` | `57303` |
| Indie rock | `57104` | `57204` | `57304` |
| Hard-rock-as-rock | `57105` | `57205` | `57305` |

Suggested Task 058 order:

1. Run the five first-seed baselines and summarize metadata/MIDI/WAV/render-report paths.
2. If any case fails hard, stop and record measured failures before tuning.
3. If a case passes but trips WATCH margin rules, run its two repeat seeds before proposing changes.
4. Only after measured gaps are known should later tasks implement parser/strategy/MIDI/profile/analyzer work.

## Rock-family acceptance gates

For each Task 058 rock-family baseline case:

- Process exits `0` and does not timeout.
- Metadata, MIDI, WAV, and render report exist.
- `renderer_path=fluidsynth`.
- `require_soundfont=true`.
- FluidSynth attempted and success are true.
- `skip_reason=null`.
- Parsed genre equals the case's expected parsed genre; hard-rock-as-rock must parse as `rock`.
- Guitar and bass are present in metadata/MIDI semantics.
- Live drum evidence includes kick, snare or clap, and hi-hats.
- FluidSynth profile is `rock:rock`.
- Tone diagnostic is exactly `high_shelf=-6.0dB@5000Hz;low_shelf=-0.75dB@90Hz`.
- `audio_analysis.passed=true`.
- `issues=[]`.
- Current target bounds for the parsed genre pass without analyzer relaxation.
- WATCH if centroid margin is less than `150 Hz` or sub-bass margin is less than `0.01`.
- WATCH triggers repeatability before tuning; do not tune from a single boundary-close green pass.

## Cross-genre baseline plan

### Tier A — profile matrix refresh

Run the existing profile matrix harness with SoundFont:

```powershell
.\scripts\smoke_fluidsynth_profile_matrix.ps1 -SoundFont assets\soundfonts\FluidR3Mono_GM.sf3 -OutputRoot output\_diagnostics\cross_genre_baseline_057\profile_matrix -DurationBars 8 -Seed 57057
```

Required Tier A settings:

- Output root: `output\_diagnostics\cross_genre_baseline_057\profile_matrix`
- `DurationBars`: `8`
- `Seed`: `57057`
- SoundFont: `assets\soundfonts\FluidR3Mono_GM.sf3`
- Treat no-op profiles as measurement baselines only, not as proof of masterclass quality.

### Tier B — quality baseline priority after rock and jazz

| Priority | Family | Example prompt | Conservative intent |
| --- | --- | --- | --- |
| 1 | Cinematic/classical | cinematic orchestral film score with strings, brass, choir, timpani, evolving sections, 96 BPM in D minor | Verify orchestral routing, dynamics, section arcs, and SoundFont realism beyond no-op profile proof. |
| 2 | Trap/modern beat | dark trap modern beat with 808 bass, snare, hihat rolls, sparse melody, 140 BPM in C minor | Measure 808/sub-bass control, hats, snare, and beat energy without applying rock assumptions. |
| 3 | R&B / neo-soul / trap-soul | neo-soul R&B groove with warm electric piano, bass, laid-back drums, lush chords, 82 BPM in F minor | Measure warmth, pocket, bass, and chord voicing; do not infer from jazz sax or trap matrix proof. |
| 4 | Lofi / boom_bap / g_funk | lofi boom bap groove with dusty drums, warm bass, mellow keys, vinyl texture, 88 BPM in C minor | Measure groove, swing, filtered texture, and sample-like drum behavior. |
| 5 | House / ambient / pop | atmospheric house pop track with pads, four-on-floor drums, bass, hook synth, 124 BPM in A minor | Measure electronic drum consistency, mix space, and pop/ambient arrangement clarity. |
| 6 | Ethiopian family | Ethiopian jazz inspired groove with pentatonic melody, bass, hand percussion feel, 104 BPM in G minor | GM SoundFont baseline can verify routing only; it is not custom-instrument masterclass proof for krar, masenqo, kebero, or regional performance practice. |

## Guardrails

- Do not modify `multimodal_gen/**`, `scripts/**`, `tests/**`, `assets/**`, or `output/**` for Task 057.
- Do not relax analyzer targets.
- Do not change profiles, rendering, parser behavior, strategy behavior, or arrangement behavior in this planning task.
- Do not claim runtime proof where no artifact exists.
- Do not claim masterclass quality without runtime artifacts, repeatability evidence, and listening/idiom evidence.
- Do not claim `hard_rock` is a separate implemented genre key; hard rock currently routes to canonical `rock`.
- Do not commit SoundFont, WAV, MIDI, or output diagnostics.
- Do not tune from a green-but-boundary-close result; WATCH requires repeatability first.

## Task 057 verification plan

PASS criteria:

- `docs/CROSS_GENRE_MATURITY_MATRIX_2026-05-16.md` exists and clearly states that Task 057 is docs/planning only.
- The matrix records exact 1990s rock as stable v1 / `PASS-WATCH`, not full rock-family completion.
- The inventory, maturity dimensions, L0-L5 definitions, maturity snapshot, rock-family gap decomposition, Task 058 runbook, acceptance gates, cross-genre plan, guardrails, and next-task decomposition are present.
- `docs/UPGRADE_PLAN_2026-05-14_1990S_ROCK_QUALITY_UI.md` has only a concise Task 057 summary/link near Task 056.
- `git diff --check` passes.
- `git diff --name-only` shows only the intended docs files for this builder slice.

FAIL criteria:

- Any source/profile/analyzer/script/test/asset/output/state file is modified by Task 057.
- The document claims new runtime proof, masterclass readiness, or separate `hard_rock` implementation without artifacts.
- The plan relaxes analyzer targets or changes behavior instead of scheduling measured baselines.
- The upgrade plan duplicates the full matrix instead of linking to it concisely.

## Next-task decomposition

- Task 058 should run the rock-family baseline measurement from this plan exactly as a measurement task: first-seed baselines, then repeatability only for failures or WATCH margins.
- Later tasks should implement only measured gaps, grouped by file overlap and proof type. Likely future slices are parser/default fixes, strategy/arrangement idiom work, MIDI/instrument semantics, analyzer additions for audible guitar/riff presence, renderer/profile tuning, and listening/reference evaluation.
- No later implementation task should begin from a speculative preference; each should cite a Task 058 or later runtime artifact and acceptance failure.