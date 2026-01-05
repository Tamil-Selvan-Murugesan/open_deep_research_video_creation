from __future__ import annotations

from open_deep_research.video_providers.base import (
    ProviderResult,
    VideoPrompt,
    VideoProvider,
)
from open_deep_research.video_providers.runway import RunwayProvider
from open_deep_research.video_providers.veo3 import Veo3Provider


_PROVIDERS: dict[str, type[VideoProvider]] = {
    Veo3Provider.name: Veo3Provider,
    RunwayProvider.name: RunwayProvider,
}


def get_provider(name: str, **kwargs) -> VideoProvider:
    provider_cls = _PROVIDERS.get(name)
    if not provider_cls:
        raise ValueError(f"Unsupported video provider '{name}'.")
    return provider_cls(**kwargs)


__all__ = [
    "ProviderResult",
    "VideoPrompt",
    "VideoProvider",
    "get_provider",
    "RunwayProvider",
    "Veo3Provider",
]
