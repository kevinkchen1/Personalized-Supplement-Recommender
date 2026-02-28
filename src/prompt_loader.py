"""
Prompt Loader — loads YAML prompt templates from src/prompts/
"""

import os
import yaml
from typing import Dict

_PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")
_cache: Dict[str, dict] = {}


def load_prompt(name: str) -> dict:
    """Load and cache a YAML prompt file. Returns dict of template strings."""
    if name not in _cache:
        path = os.path.join(_PROMPTS_DIR, f"{name}.yaml")
        with open(path) as f:
            _cache[name] = yaml.safe_load(f)
    return _cache[name]
