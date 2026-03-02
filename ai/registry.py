import os

from ai.base import AIProvider


def get_provider() -> AIProvider:
    provider_name = os.environ.get("PROVENANCE_AI_PROVIDER", "openai").lower()

    if provider_name == "openai":
        from ai.openai_provider import OpenAIProvider
        return OpenAIProvider()

    raise RuntimeError(
        f"Unknown AI provider '{provider_name}'.\n"
        f"Set PROVENANCE_AI_PROVIDER to one of: openai\n"
        f"(More providers can be added in ai/registry.py)"
    )
