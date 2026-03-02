from abc import ABC, abstractmethod


class AIProvider(ABC):
    @abstractmethod
    def complete(self, system: str, user: str, model: str | None = None) -> str:
        """Send a system + user prompt, return the response text.

        model: override the provider's default model for this call.
        """
        ...

    def chat_with_tools(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict],
    ) -> tuple[str | None, list[dict]]:
        """One turn of tool-use.

        Returns (text, tool_calls).
        If tool_calls is non-empty the caller should execute them and loop.
        Base implementation falls back to plain complete() — ignores tools.
        """
        user_text = " ".join(
            m["content"] for m in messages if m.get("role") == "user" and isinstance(m.get("content"), str)
        )
        return self.complete(system=system, user=user_text), []
