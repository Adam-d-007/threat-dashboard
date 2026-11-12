"""The rebuilt pipeline's settings (config.yaml) and Adam's corrections (overrides.yaml)."""

from pathlib import Path

import yaml

HERE = Path(__file__).parent


def load() -> dict:
    return yaml.safe_load((HERE / "config.yaml").read_text())


def overrides() -> dict:
    return yaml.safe_load((HERE / "overrides.yaml").read_text()) or {}
