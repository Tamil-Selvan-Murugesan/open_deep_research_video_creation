from __future__ import annotations

import time
from pathlib import Path
from typing import Any

from google import genai

from open_deep_research.video_providers.base import ProviderResult, VideoPrompt


class Veo3Provider:
    name = "veo3"
    default_model = "veo-3.1-generate-preview"

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
        client = genai.Client(api_key=self.api_key) if self.api_key else genai.Client()
        operation = client.models.generate_videos(
            model=self.model,
            prompt=prompt.veo_prompt,
        )

        deadline = time.time() + self.max_wait_seconds if self.max_wait_seconds else None
        while not operation.done:
            if deadline and time.time() > deadline:
                raise TimeoutError(
                    f"Timed out waiting for Veo-3 generation after {self.max_wait_seconds} seconds."
                )
            time.sleep(self.poll_interval_seconds)
            operation = client.operations.get(operation)

        response = getattr(operation, "response", None)
        generated_videos = getattr(response, "generated_videos", None) if response else None
        if not generated_videos:
            raise RuntimeError("Veo-3 returned no generated videos.")

        generated_video = generated_videos[0]
        client.files.download(file=generated_video.video)

        output_path = output_dir / f"{self.name}_prompt_{prompt.id}.mp4"
        generated_video.video.save(str(output_path))

        provider_metadata: dict[str, Any] = {
            "operation_name": getattr(operation, "name", None),
            "video_id": getattr(generated_video.video, "name", None),
        }
        return ProviderResult(output_path=output_path, provider_metadata=provider_metadata)
