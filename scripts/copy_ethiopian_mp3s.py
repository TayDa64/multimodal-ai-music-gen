"""Copy source MP3 recordings into the repo with normalized names."""
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
PARENT = REPO_ROOT.parent
DEST = REPO_ROOT / "assets" / "references" / "ethiopian" / "source_mp3"

MAPPING = {
    "Krar_acoustic 2.mp3": "krar_acoustic.mp3",
    "Krar_with _amp 2.mp3": "krar_amplified.mp3",
    "Mesenqo  2.mp3": "masenqo.mp3",
    "Begena 2.mp3": "begena.mp3",
}


def main():
    DEST.mkdir(parents=True, exist_ok=True)
    for src_name, dst_name in MAPPING.items():
        src = PARENT / src_name
        dst = DEST / dst_name
        if not src.exists():
            print(f"WARNING: source missing, skipping: {src}")
            continue
        shutil.copy2(src, dst)
        print(f"COPIED: {src.name!r} -> {dst.relative_to(REPO_ROOT)} ({dst.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
