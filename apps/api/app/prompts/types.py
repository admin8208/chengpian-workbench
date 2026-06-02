from dataclasses import dataclass


@dataclass(frozen=True)
class PromptMessages:
    system: str
    user: str


@dataclass(frozen=True)
class PromptParts:
    parts: tuple[str, ...]
