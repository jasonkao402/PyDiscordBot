import os
from pathlib import Path
from typing import Any
import toml

TOML_PATH = Path('./config/config.toml')
configToml: dict[str, Any] = {}

def loadToml():
    """Load or hot-reload config.toml in-place so all imported references update immediately."""
    if not TOML_PATH.exists():
        print(f"[Config] {TOML_PATH} not found! Please check the file path.")
        return configToml
    
    # Load toml with chinese character support
    with open(TOML_PATH, 'r+', encoding='utf-8') as tomlFile:
        _new_config = toml.load(tomlFile)

    configToml.clear()
    configToml.update(_new_config)
    _sections = '\n  - '.join(configToml.keys())
    print(f'loaded from {TOML_PATH}, content:\n  - {_sections}')
    return configToml

# Load the configuration once and make it accessible
loadToml()