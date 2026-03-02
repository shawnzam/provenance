import json
import os
import openai  # Only file in this project that imports openai

from ai.base import AIProvider


class OpenAIProvider(AIProvider):
    def __init__(self):
        api_key = os.environ.get("PROVENANCE_OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError(
                "PROVENANCE_OPENAI_API_KEY is not set.\n"
                "Add it to your .env file:\n"
                "  PROVENANCE_OPENAI_API_KEY=sk-..."
            )
        self.client = openai.OpenAI(api_key=api_key)
        self.model = os.environ.get("PROVENANCE_AI_MODEL", "gpt-4o")

    def complete(self, system: str, user: str, model: str | None = None) -> str:
        response = self.client.chat.completions.create(
            model=model or self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return response.choices[0].message.content

    def chat_with_tools(
        self,
        system: str,
        messages: list[dict],
        tools: list[dict],
    ) -> tuple[str | None, list[dict]]:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "system", "content": system}] + messages,
            tools=tools,
            tool_choice="auto",
        )
        msg = response.choices[0].message

        if msg.tool_calls:
            return None, [
                {
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                    # Keep raw for re-sending to the API
                    "_raw": {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    },
                }
                for tc in msg.tool_calls
            ]

        return msg.content, []
