from __future__ import annotations

from pathlib import Path

from open_deep_research.video_providers.base import ProviderResult, VideoPrompt


class RunwayProvider:
    name = "runway"
    default_model = "gen-3-alpha"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        poll_interval_seconds: int = 10,
        max_wait_seconds: int | None = 900,
    ) -> None:
        self.api_key = api_key
        self.model = model or self.default_model
        self.poll_interval_seconds = poll_interval_seconds
        self.max_wait_seconds = max_wait_seconds

    def generate(self, prompt: VideoPrompt, output_dir: Path) -> ProviderResult:
        raise NotImplementedError(
            "Runway provider is not configured yet. "
            "Provide the Runway API endpoint/auth details to enable this provider."
        )
