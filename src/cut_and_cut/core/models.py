from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class CutMode(Enum):
    PRECISE = "precise"
    FAST = "fast"


@dataclass(frozen=True)
class MediaInfo:
    path: Path
    duration_s: float
    width: int
    height: int
    video_codec: str
    audio_codec: str | None
    container: str

    @property
    def has_audio(self) -> bool:
        return self.audio_codec is not None


@dataclass(frozen=True)
class ProjectConfig:
    name: str
    destination: Path
    source: Path
    segment_duration_s: float
    count: int | None
    mode: CutMode


@dataclass
class ClipPlan:
    index: int
    start_s: float
    end_s: float
    duration_s: float
    shorter: bool
    title: str
    included: bool = True


@dataclass(frozen=True)
class PlanResult:
    clips: tuple[ClipPlan, ...]
    warning: str | None = None


class PlanError(ValueError):
    """The requested cuts cannot be planned."""
