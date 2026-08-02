import importlib.util
import json
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).parent.parent
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "audit_rock_source_candidates.py"


def _load_script_module():
    module_name = "audit_rock_source_candidates_under_test"
    sys.modules.pop(module_name, None)
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _build_tmp_repo(tmp_path):
    repo_root = tmp_path / "repo"

    soundfont = repo_root / "assets" / "soundfonts" / "FluidR3Mono_GM.sf3"
    soundfont.parent.mkdir(parents=True)
    soundfont.write_bytes(b"fake soundfont")

    guitar = repo_root / "instruments" / "guitar" / "1990s_Rock_Guitar.WAV"
    guitar.parent.mkdir(parents=True)
    guitar.write_bytes(b"fake guitar wav")

    bass = repo_root / "instruments" / "bass" / "picked_bass.wav"
    bass.parent.mkdir(parents=True)
    bass.write_bytes(b"fake bass wav")

    expansion_root = tmp_path / "expansions" / "personal_rock_pack"
    expansion_manifest = expansion_root / "expansion.json"
    expansion_manifest.parent.mkdir(parents=True)
    expansion_manifest.write_text(
        json.dumps(
            {
                "name": "Personal Rock Pack",
                "license": "Commercial - For personal use",
                "target_genres": ["rock", "classic_rock"],
            }
        ),
        encoding="utf-8",
    )

    expansion_guitar = expansion_root / "samples" / "Crunch Guitar.WAV"
    expansion_guitar.parent.mkdir(parents=True)
    expansion_guitar.write_bytes(b"fake expansion guitar")

    expansion_bass_xpm = expansion_root / "programs" / "picked_bass.xpm"
    expansion_bass_xpm.parent.mkdir(parents=True)
    expansion_bass_xpm.write_text("<xpm/>\n", encoding="utf-8")

    return repo_root


def _candidates_by_name(report):
    return {Path(candidate["path"]).name: candidate for candidate in report["candidates"]}


def test_audit_reports_no_eligible_exact_rock_upgrade_candidates(tmp_path):
    script = _load_script_module()
    repo_root = _build_tmp_repo(tmp_path)

    report = script.audit_rock_source_candidates(repo_root)
    candidates = _candidates_by_name(report)

    assert report["schema_version"] == 1
    assert report["summary"]["eligible_exact_rock_upgrade_candidates"] == 0
    assert report["summary"]["total_candidates"] == 5
    assert all(
        candidate["eligible_for_exact_rock_upgrade"] is False
        for candidate in report["candidates"]
    )

    fluid = candidates["FluidR3Mono_GM.sf3"]
    assert fluid["source_quality"] == "gm_soundfont_baseline"
    assert fluid["family"] == "general_midi"
    assert fluid["source_scope"] == "soundfont"
    assert fluid["eligible_for_exact_rock_upgrade"] is False
    assert "baseline" in fluid["reason"].lower()
    assert "not a dedicated guitar/bass" in fluid["reason"].lower()

    local_guitar = candidates["1990s_Rock_Guitar.WAV"]
    local_bass = candidates["picked_bass.wav"]
    for candidate, family in ((local_guitar, "guitar"), (local_bass, "bass")):
        assert candidate["source_quality"] == "local_user_sample_unverified"
        assert candidate["family"] == family
        assert candidate["source_scope"] == "local_instruments"
        assert candidate["eligible_for_exact_rock_upgrade"] is False
        assert "license" in candidate["reason"].lower()
        assert "multisample proof" in candidate["reason"].lower()

    expansion_guitar = candidates["Crunch Guitar.WAV"]
    expansion_bass = candidates["picked_bass.xpm"]
    for candidate, family in ((expansion_guitar, "guitar"), (expansion_bass, "bass")):
        assert candidate["source_quality"] == "expansion_personal_use"
        assert candidate["license_status"] == "personal_use_restricted"
        assert candidate["family"] == family
        assert candidate["source_scope"] == "expansion"
        assert candidate["expansion_name"] == "Personal Rock Pack"
        assert candidate["expansion_license"] == "Commercial - For personal use"
        assert candidate["target_genres"] == ["rock", "classic_rock"]
        assert candidate["eligible_for_exact_rock_upgrade"] is False


def test_cli_out_writes_valid_json_and_prints_stdout(tmp_path):
    repo_root = _build_tmp_repo(tmp_path)
    out_path = tmp_path / "audit" / "rock_source_candidates.json"

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_PATH),
            "--repo-root",
            str(repo_root),
            "--out",
            str(out_path),
        ],
        capture_output=True,
        text=True,
        cwd=str(PROJECT_ROOT),
    )

    assert result.returncode == 0, result.stderr
    stdout_report = json.loads(result.stdout)
    file_report = json.loads(out_path.read_text(encoding="utf-8"))

    assert stdout_report == file_report
    assert file_report["summary"]["eligible_exact_rock_upgrade_candidates"] == 0
    assert file_report["summary"]["by_source_quality"]["gm_soundfont_baseline"] == 1
    assert file_report["summary"]["by_source_quality"]["local_user_sample_unverified"] == 2
    assert file_report["summary"]["by_source_quality"]["expansion_personal_use"] == 2