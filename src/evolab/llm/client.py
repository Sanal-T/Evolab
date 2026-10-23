"""Provider-neutral interface for a language model client."""

from typing import Protocol


class LLMClient(Protocol):
    """The small operation an LLM provider must support."""

    def complete(self, *, system_prompt: str, user_prompt: str) -> str:
        """Return the model's text response."""
        ...