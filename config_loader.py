from __future__ import annotations

from pathlib import Path
from typing import Any

import toml

TOML_PATH = Path('./config/config.toml')
config_toml: dict[str, Any] = {}

def load_toml():
    """Load or hot-reload config.toml in-place so all imported references update immediately."""
    if not TOML_PATH.exists():
        print(f"[Config] {TOML_PATH} not found! Please check the file path.")
        return config_toml

    # Load toml with chinese character support
    with Path(TOML_PATH).open('r+', encoding='utf-8') as tomlFile:
        _new_config = toml.load(tomlFile)

    config_toml.clear()
    config_toml.update(_new_config)
    _sections = '\n  - '.join(config_toml.keys())
    print(f'loaded from {TOML_PATH}, content:\n  - {_sections}')
    return config_toml


# Load the configuration once and make it accessible
load_toml()
