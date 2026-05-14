from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "smoke_1990s_rock.ps1"
EXACT_PROMPT = "1990's era rock song with crunchy electric guitar, live drums, bass guitar, verse chorus bridge, energetic band performance, 100 BPM in E minor"


def test_smoke_1990s_rock_script_contract_is_static_and_strict_ready():
    script_text = SCRIPT_PATH.read_text(encoding="utf-8")

    assert EXACT_PROMPT in script_text
    assert "smoke_summary.json" in script_text
    assert "generation.stdout.log" in script_text
    assert "generation.stderr.log" in script_text
    assert "--require-audio" in script_text
    assert "--duration-bars" in script_text
    assert "--seed" in script_text


def test_smoke_1990s_rock_script_passes_prompt_as_one_process_argument():
    script_text = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "Start-Process" not in script_text
    assert "-ArgumentList" not in script_text
    assert ".ArgumentList.Add($arg)" in script_text
    assert "$childArgs = @(" in script_text
