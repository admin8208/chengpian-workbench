from dataclasses import dataclass


@dataclass(frozen=True)
class SmartTtsSegment:
    scene_idx: int
    speaker: str
    text: str
    pace: str = "normal"
    emotion: str = "neutral"
