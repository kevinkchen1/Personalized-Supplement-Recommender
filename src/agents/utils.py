"""
Utility helpers for agents package.

Keep small, well-tested helpers here to keep agent code concise.
"""
from typing import Any
import json
import re


def clean_code_block(text: str) -> str:
    """Remove markdown code fences and leading language hints from LLM output."""
    if not text:
        return text
    # Remove ```json or ```cypher fences
    cleaned = re.sub(r"^```[a-zA-Z0-9_-]*\n|\n```$", "", text.strip(), flags=re.MULTILINE)
    return cleaned.strip()


def safe_json_load(text: str, default: Any = None) -> Any:
    """Try to parse JSON returning `default` on failure."""
    try:
        return json.loads(clean_code_block(text))
    except Exception:
        return default
