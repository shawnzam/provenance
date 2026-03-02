"""
Proofreading helper — corrects spelling and grammar in prose strings.
Uses the configured AI provider. Only called when --check-text / -ct is passed.
"""

import json
import os

from ai.registry import get_provider

_SYSTEM = (
    "You are a proofreader. Correct spelling and grammar mistakes only. "
    "Make the minimum possible changes — fix typos and obvious errors, "
    "do not rephrase, rewrite, or expand. "
    "Input is a JSON array of strings. "
    "Output ONLY a valid JSON array of corrected strings in the same order. "
    "No commentary, no markdown, no code fences — raw JSON only."
)


def correct_texts(texts: list[str]) -> list[str]:
    """Return corrected versions of each text string, preserving order."""
    if not texts:
        return []

    provider = get_provider()
    model = os.environ.get("PROVENANCE_PROOFREAD_AI_MODEL") or None
    result = provider.complete(system=_SYSTEM, user=json.dumps(texts), model=model)

    try:
        corrected = json.loads(result.strip())
        if isinstance(corrected, list) and len(corrected) == len(texts):
            return [str(c) for c in corrected]
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: return originals if model response can't be parsed
    return texts
