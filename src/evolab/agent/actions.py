"""Small, explicit action types used by the baseline agent."""

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Action:
    """One requested operation; arguments are checked by the executor."""

    kind: str
    arguments: dict[str, Any] = field(default_factory=dict)
