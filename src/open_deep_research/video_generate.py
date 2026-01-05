from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from open_deep_research.video_providers import get_provider
from open_deep_research.video_providers.base import ProviderResult, VideoPrompt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate videos from Veo-3 or Runway using prompt JSON."
    )
    parser.add_argument(
        "--provider",
        default="veo3",
        choices=["veo3", "runway"],
        help="Video generation provider.",
    )
    parser.add_argument(
        "--input",
        default="-",
        help="Path to JSON containing video_prompts. Use '-' for stdin.",
    )
    parser.add_argument(
        "--output-dir",
        default="outputs/videos",
        help="Directory to save generated videos and metadata.",
    )
    parser.add_argument(
        "--ids",
        help="Comma-separated prompt ids to generate (example: 1,3,5).",
    )
    parser.add_argument(
        "--model",
        help="Provider model override.",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=10,
        help="Seconds between status polls.",
    )
    parser.add_argument(
        "--max-wait-seconds",
        type=int,
        default=900,
        help="Maximum time to wait for a video generation.",
    )
    parser.add_argument(
        "--google-api-key",
        default=os.getenv("GOOGLE_API_KEY"),
        help="Google API key for Veo-3.",
    )
    parser.add_argument(
        "--runway-api-key",
        default=os.getenv("RUNWAY_API_KEY"),
        help="Runway API key.",
    )
    parser.add_argument(
        "--output-json",
        help="Optional path to write JSON output for UI usage.",
    )
    return parser


def load_input_payload(path: str) -> dict[str, Any]:
    if path == "-":
        if sys.stdin.isatty():
            raise SystemExit("Provide --input or pipe JSON via stdin.")
        raw = sys.stdin.read()
    else:
        raw = Path(path).read_text(encoding="utf-8")
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON input: {exc}") from exc
    if not isinstance(payload, dict):
        raise SystemExit("Input JSON must be an object with a video_prompts list.")
    return payload


def parse_prompt(item: dict[str, Any]) -> VideoPrompt:
    if "id" not in item:
        raise SystemExit("Each video prompt must include an id field.")
    return VideoPrompt(
        id=int(item["id"]),
        veo_prompt=str(item.get("veo_prompt", "")),
        voiceover=str(item.get("voiceover", "")),
        actual_content=str(
            item.get("actual-content", item.get("actual_content", ""))
        ),
        duration_seconds=int(item.get("duration_seconds", 8)),
    )


def parse_id_filter(raw: str | None) -> set[int] | None:
    if not raw:
        return None
    ids: set[int] = set()
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        ids.add(int(part))
    return ids or None


def build_metadata(
    prompt: VideoPrompt,
    provider_name: str,
    model: str,
    result: ProviderResult,
) -> dict[str, Any]:
    return {
        "id": prompt.id,
        "provider": provider_name,
        "model": model,
        "veo_prompt": prompt.veo_prompt,
        "voiceover": prompt.voiceover,
        "actual-content": prompt.actual_content,
        "duration_seconds": prompt.duration_seconds,
        "file_path": str(result.output_path),
        "provider_metadata": result.provider_metadata,
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    payload = load_input_payload(args.input)
    prompts_raw = payload.get("video_prompts", [])
    if not isinstance(prompts_raw, list):
        raise SystemExit("video_prompts must be a list.")

    prompts = [parse_prompt(item) for item in prompts_raw]
    ids_filter = parse_id_filter(args.ids)
    if ids_filter is not None:
        prompts = [prompt for prompt in prompts if prompt.id in ids_filter]

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    provider_kwargs = {
        "model": args.model,
        "poll_interval_seconds": args.poll_interval,
        "max_wait_seconds": args.max_wait_seconds,
    }
    if args.provider == "veo3":
        provider_kwargs["api_key"] = args.google_api_key
    else:
        provider_kwargs["api_key"] = args.runway_api_key

    provider = get_provider(args.provider, **provider_kwargs)
    provider_model = getattr(provider, "model", args.model) or provider.default_model

    results: list[dict[str, Any]] = []
    errors: list[str] = []

    if not prompts:
        errors.append("No prompts matched the provided id filter.")
    else:
        for prompt in prompts:
            try:
                provider_result = provider.generate(prompt, output_dir)
                metadata = build_metadata(
                    prompt,
                    provider.name,
                    provider_model,
                    provider_result,
                )
                metadata_path = provider_result.output_path.with_suffix(".json")
                metadata_path.write_text(
                    json.dumps(metadata, ensure_ascii=True, indent=2),
                    encoding="utf-8",
                )
                results.append(
                    {
                        "id": prompt.id,
                        "status": "success",
                        "file_path": str(provider_result.output_path),
                        "metadata_path": str(metadata_path),
                        "provider_metadata": provider_result.provider_metadata,
                        "veo_prompt": prompt.veo_prompt,
                        "voiceover": prompt.voiceover,
                        "actual-content": prompt.actual_content,
                        "duration_seconds": prompt.duration_seconds,
                    }
                )
            except Exception as exc:
                results.append(
                    {
                        "id": prompt.id,
                        "status": "error",
                        "error": str(exc),
                        "veo_prompt": prompt.veo_prompt,
                        "voiceover": prompt.voiceover,
                        "actual-content": prompt.actual_content,
                        "duration_seconds": prompt.duration_seconds,
                    }
                )

    output = {
        "provider": provider.name,
        "model": provider_model,
        "output_dir": str(output_dir),
        "results": results,
    }
    if errors:
        output["errors"] = errors

    output_json = json.dumps(output, ensure_ascii=True, indent=2)
    print(output_json)

    if args.output_json:
        Path(args.output_json).write_text(output_json, encoding="utf-8")

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
