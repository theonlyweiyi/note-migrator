from pathlib import Path
import yaml
from src.config.schema import AppConfig


def load_config(path: Path) -> AppConfig:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return AppConfig.model_validate(raw)


def create_example_config(path: Path):
    """Copy config.example.yaml to path if it doesn't exist."""
    example = path.parent / "config.example.yaml"
    if example.exists():
        path.write_text(example.read_text(encoding="utf-8"), encoding="utf-8")
        return True
    return False
