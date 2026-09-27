"""Load the YAML config and fill in secrets from environment variables.

Anything written as ${NAME} in the config is replaced with the environment
variable NAME. This keeps API keys and passwords OUT of the config file, so the
folder is safe to move or push to GitHub. Locally, a .env file is loaded first
(see .env.example); on GitHub the values come from repository Secrets.
"""

from __future__ import annotations

import os
import re
from pathlib import Path

import yaml

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    # python-dotenv is optional. On GitHub the env vars come from Secrets.
    pass

_ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")


def _expand(value):
    """Replace ${NAME} inside any string with the environment variable NAME."""
    if isinstance(value, str):
        def repl(m):
            return os.environ.get(m.group(1), "")
        return _ENV_PATTERN.sub(repl, value)
    if isinstance(value, list):
        return [_expand(v) for v in value]
    if isinstance(value, dict):
        return {k: _expand(v) for k, v in value.items()}
    return value


def load_config(path: str = "config.yaml") -> dict:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(
            f"Config file not found: {p}. Copy config.example.yaml to config.yaml "
            f"and edit it."
        )
    with open(p, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return _expand(raw)
