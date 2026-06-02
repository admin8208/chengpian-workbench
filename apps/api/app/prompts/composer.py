from app.prompts.types import PromptMessages


def compose_prompt(*parts: str) -> str:
    lines: list[str] = []
    for part in parts:
        s = str(part or "").strip()
        if s:
            lines.append(s)
    return "\n".join(lines).strip()


def build_messages(*, system_parts: list[str], user_parts: list[str]) -> PromptMessages:
    return PromptMessages(system=compose_prompt(*system_parts), user=compose_prompt(*user_parts))
