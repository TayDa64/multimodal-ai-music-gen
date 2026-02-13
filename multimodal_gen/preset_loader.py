"""
Preset Loader — Unified YAML-based preset system for MUSE.

Loads genre/style presets from configs/presets/*.yaml and applies them
to the generation pipeline via PolicyContext integration.
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

# Guard import for YAML
try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


PRESETS_DIR = Path(__file__).parent.parent / "configs" / "presets"


@dataclass
class PresetInfo:
    """Metadata about an available preset."""
    name: str
    category: str
    description: str
    tags: List[str]
    file_path: str


class PresetLoader:
    """Loads and manages YAML-based genre/style presets."""

    def __init__(self, presets_dir: Optional[str] = None):
        self._presets_dir = Path(presets_dir) if presets_dir else PRESETS_DIR
        self._cache: Dict[str, Dict] = {}

    def list_available_presets(self) -> List[PresetInfo]:
        """List all available presets with metadata."""
        presets: List[PresetInfo] = []
        if not self._presets_dir.exists():
            return presets
        for yaml_file in sorted(self._presets_dir.glob("*.yaml")):
            try:
                data = self._load_yaml(yaml_file)
                presets.append(PresetInfo(
                    name=data.get("name", yaml_file.stem),
                    category=data.get("category", "genre"),
                    description=data.get("description", ""),
                    tags=data.get("tags", []),
                    file_path=str(yaml_file),
                ))
            except Exception:
                continue
        return presets

    def load_preset(self, name: str) -> Dict[str, Any]:
        """Load a preset by name. Returns full config dict."""
        if name in self._cache:
            return self._cache[name]

        # Try exact filename match first
        yaml_path = self._presets_dir / f"{name}.yaml"
        if not yaml_path.exists():
            # Try searching by preset name field
            for f in self._presets_dir.glob("*.yaml"):
                data = self._load_yaml(f)
                if data.get("name") == name:
                    yaml_path = f
                    break
            else:
                raise FileNotFoundError(
                    f"Preset '{name}' not found in {self._presets_dir}"
                )

        data = self._load_yaml(yaml_path)
        self._cache[name] = data
        return data

    def get_mastering_chain(self, preset_name: str) -> Dict[str, Any]:
        """Extract mastering settings from a preset."""
        preset = self.load_preset(preset_name)
        return preset.get("mastering", {"target_lufs": -14.0})

    def _load_yaml(self, path: Path) -> Dict:
        """Load a YAML file, with JSON fallback."""
        with open(path, 'r', encoding='utf-8') as f:
            if _HAS_YAML:
                return yaml.safe_load(f) or {}
            else:
                # Fallback: try JSON (won't work for YAML but prevents crash)
                try:
                    return json.load(f)
                except Exception:
                    return {}

    def clear_cache(self):
        """Clear the preset cache."""
        self._cache.clear()


# Convenience functions
def list_presets() -> List[PresetInfo]:
    """List all available presets."""
    return PresetLoader().list_available_presets()


def load_preset(name: str) -> Dict[str, Any]:
    """Load a preset by name."""
    return PresetLoader().load_preset(name)
