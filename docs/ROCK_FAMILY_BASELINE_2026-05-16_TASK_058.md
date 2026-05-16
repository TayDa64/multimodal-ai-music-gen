# Task 058 — Rock-family baseline measurement aggregation

Date: 2026-05-16
Task ID: `rock-family-baseline-measurement-058`
Task title: Task 058 — Rock-family first-seed baseline measurement before tuning

## Scope and guardrails

This is a docs/state-only aggregation of an already-completed direct `main.py` FluidSynth measurement harness. Task 058 made no source, profile, analyzer target, parser, strategy, script, test, asset, SoundFont, or tuning changes.

Output diagnostics remain local proof artifacts and must stay ignored/uncommitted. This report records only concise artifact paths, aggregate status, and measured metrics needed to guide the next measured implementation task.

## Harness summary

- Generated at: `2026-05-16T09:03:11Z`
- Repo head: `b2945a6`
- Direct runtime harness: `main.py` with FluidSynth rendering, 16 bars per run, explicit seed per case, `--skip-default-instruments`, `--skip-expansions`, `--require-soundfont`, and `--require-audio`.
- Required SoundFont: `assets\soundfonts\FluidR3Mono_GM.sf3`
- Renderer path for all cases: `fluidsynth`
- Profile for all cases: `rock:rock`
- Tone shaping for all cases: `high_shelf=-6.0dB@5000Hz;low_shelf=-0.75dB@90Hz`
- Preflight proof: `preflight.proof_passed=true`
- Repeats: failing first-seed cases were repeated on the two planned repeat seeds; the passing grunge first seed did not require repeats.

## Artifact paths

| Artifact | Path |
| --- | --- |
| Run root | `output\_diagnostics\rock_family_baseline_057\run_20260516_014229` |
| Summary JSON | `output\_diagnostics\rock_family_baseline_057\run_20260516_014229\rock_family_baseline_058_summary.json` |
| Case output pattern | `output\_diagnostics\rock_family_baseline_057\run_20260516_014229\<case_id>\seed_<seed>` |

Do not copy or commit the generated WAV, MIDI, render-report, stdout/stderr, or metadata files from the output diagnostics tree.

## Aggregate result

| Field | Value |
| --- | --- |
| Overall status | `FAIL-MEASURED` |
| Planned case count | `5` |
| Case count | `5` |
| Run count | `13` |
| Pass count | `1` |
| Watch count | `0` |
| Failure count | `4` |
| Blocked | `false` |
| Systemic block | `null` |

## Per-case result summary

| Case | Expected parsed genre | Status | Seeds run | Result interpretation |
| --- | --- | --- | --- | --- |
| `classic_rock_baseline` | `classic_rock` | `FAIL-MEASURED` | `57101`, `57201`, `57301` | Deterministic classic-rock failure: too bright and too much sub-bass. |
| `grunge_baseline` | `grunge` | `PASS` | `57102` | First seed passed with no issues; no repeats required by the Task 057 runbook. |
| `punk_rock_baseline` | `punk_rock` | `FAIL-MEASURED` | `57103`, `57203`, `57303` | Deterministic punk-rock sub-bass failure; centroid is often boundary-close high, but the hard failure is sub-bass. |
| `indie_rock_baseline` | `indie_rock` | `FAIL-MEASURED` | `57104`, `57204`, `57304` | Deterministic indie-rock sub-bass failure; brightness/centroid is boundary-close or over bound. |
| `hard_rock_as_rock_baseline` | `rock` | `FAIL-MEASURED` | `57105`, `57205`, `57305` | Deterministic hard-rock-as-rock sub-bass failure with brightness/centroid at or over the upper rock bound. |

## Per-seed measured metrics

Positive margins are inside the current analyzer bound. Negative margins are out of bound.

| Case | Seed | Status | Score | Centroid Hz | Centroid margin | Sub-bass | Sub-bass margin | Issues / failed categories |
| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `classic_rock_baseline` | `57101` | `FAIL-MEASURED` | `0.68` | `4198.1` | `-398.1` | `0.1424` | `-0.0224` | 2 issues: centroid outside `800-3800`; sub-bass above max `0.12`. |
| `classic_rock_baseline` | `57201` | `FAIL-MEASURED` | `0.68` | `4196.1` | `-396.1` | `0.1375` | `-0.0175` | 2 issues: centroid outside `800-3800`; sub-bass above max `0.12`. |
| `classic_rock_baseline` | `57301` | `FAIL-MEASURED` | `0.68` | `4204.3` | `-404.3` | `0.1462` | `-0.0262` | 2 issues: centroid outside `800-3800`; sub-bass above max `0.12`. |
| `grunge_baseline` | `57102` | `PASS` | `1.0` | `3976.1` | `423.9` | `0.1616` | `0.0184` | 0 issues. |
| `punk_rock_baseline` | `57103` | `FAIL-MEASURED` | `0.68` | `4938.0` | `62.0` | `0.1828` | `-0.0328` | 1 issue: sub-bass above max `0.15`. |
| `punk_rock_baseline` | `57203` | `FAIL-MEASURED` | `0.68` | `4833.6` | `166.4` | `0.1827` | `-0.0327` | 1 issue: sub-bass above max `0.15`. |
| `punk_rock_baseline` | `57303` | `FAIL-MEASURED` | `0.68` | `4911.8` | `88.2` | `0.1842` | `-0.0342` | 1 issue: sub-bass above max `0.15`. |
| `indie_rock_baseline` | `57104` | `FAIL-MEASURED` | `0.68` | `4000.1` | `199.9` | `0.1632` | `-0.0232` | 1 issue: sub-bass above max `0.14`. |
| `indie_rock_baseline` | `57204` | `FAIL-MEASURED` | `0.68` | `4233.4` | `-33.4` | `0.1635` | `-0.0235` | 2 issues: centroid outside `800-4200`; sub-bass above max `0.14`. |
| `indie_rock_baseline` | `57304` | `FAIL-MEASURED` | `0.68` | `4192.9` | `7.1` | `0.1626` | `-0.0226` | 1 issue: sub-bass above max `0.14`. |
| `hard_rock_as_rock_baseline` | `57105` | `FAIL-MEASURED` | `0.68` | `4605.1` | `-105.1` | `0.1905` | `-0.0305` | 2 issues: centroid outside `1000-4500`; sub-bass above max `0.16`. |
| `hard_rock_as_rock_baseline` | `57205` | `FAIL-MEASURED` | `0.68` | `4480.5` | `19.5` | `0.1750` | `-0.0150` | 1 issue: sub-bass above max `0.16`. |
| `hard_rock_as_rock_baseline` | `57305` | `FAIL-MEASURED` | `0.68` | `4501.4` | `-1.4` | `0.1711` | `-0.0111` | 2 issues: centroid outside `1000-4500`; sub-bass above max `0.16`. |

## Interpretation

Task 058 confirms that exact-rock stability from Task 056 does not generalize to full rock-family masterclass completion. The first measured rock-family slice is mixed: `grunge` passes the current gates on its first seed, but `classic_rock`, `punk_rock`, `indie_rock`, and hard-rock-as-canonical-`rock` are measured failures.

The dominant repeated failure is excess sub-bass across every failing family. Brightness/centroid is also a hard repeated failure for `classic_rock`, appears as a measured over-bound for one `indie_rock` repeat, and is at or over the upper `rock` bound for hard-rock-as-rock. `punk_rock` centroid margins are close to the high bound on two seeds, but its hard repeated failure is sub-bass.

These are current-target failures, not reasons to relax analyzer gates. The next implementation task should use these artifacts as the measured baseline and preserve the passing `grunge` behavior plus the exact-rock Task 056 green control.

## Recommended next measured implementation task

Open Task 059 as a measured rock-family remediation slice focused on the repeated failures from Task 058, without analyzer relaxation:

1. Diagnose why rock-family bass/drum/rendering produces excess sub-bass for `classic_rock`, `punk_rock`, `indie_rock`, and hard-rock-as-`rock` while `grunge` and exact rock remain acceptable.
2. Separately inspect the centroid/brightness path for `classic_rock`, `indie_rock`, and hard-rock-as-`rock` using the existing Task 058 seeds.
3. Implement only the smallest measured source/profile/arrangement correction justified by those diagnostics, then rerun the same failing seeds and the `grunge` pass seed as regression controls.
4. Keep SoundFont/WAV/MIDI/render-report artifacts under ignored `output\_diagnostics`; do not commit output diagnostics.
