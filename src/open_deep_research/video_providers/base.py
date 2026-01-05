from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol


@dataclass(frozen=True)
class VideoPrompt:
    id: int
    veo_prompt: str
    voiceover: str
    actual_content: str
    duration_seconds: int


@dataclass(frozen=True)
class ProviderResult:
    output_path: Path
    provider_metadata: dict[str, Any]


class VideoProvider(Protocol):
    name: str
    default_model: str

    def generate(self, prompt: VideoPrompt, output_dir: Path) -> ProviderResult: ...
