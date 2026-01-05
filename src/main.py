from __future__ import annotations

import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path
from typing import Any, Iterable

from dotenv import load_dotenv
from langchain_core.messages import BaseMessage
from langgraph.checkpoint.memory import MemorySaver

from open_deep_research.deep_researcher import deep_researcher_builder


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the Open Deep Research agent from the command line."
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        help="Research prompt. If omitted, read from stdin.",
    )
    parser.add_argument(
        "--input-file",
        help="Read the prompt from a file. Use '-' to read from stdin.",
    )
    parser.add_argument(
        "--config",
        help="JSON string or path to a JSON file with configuration overrides.",
    )
    parser.add_argument(
        "--set",
        dest="overrides",
        action="append",
        default=[],
        help=(
            "Override a field (key=value). Use configurable.key or metadata.key to target sections."
        ),
    )
    parser.add_argument(
        "--thread-id",
        help="Thread ID for LangGraph state. Auto-generated if omitted.",
    )
    parser.add_argument(
        "--owner",
        help="Optional metadata owner for MCP token storage.",
    )
    parser.add_argument(
        "--output-file",
        help="Write the final report to a file instead of stdout.",
    )
    parser.add_argument(
        "--output-json",
        help="Write the final JSON report payload to a file.",
    )
    return parser


def load_config_payload(raw: str | None) -> dict[str, Any]:
    if not raw:
        return {}
    config_text = raw
    config_path = Path(raw)
    if config_path.exists():
        config_text = config_path.read_text(encoding="utf-8")
    try:
        data = json.loads(config_text)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON config: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("Config must be a JSON object.")
    return data


def parse_override_value(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def apply_overrides(config: dict[str, Any], overrides: Iterable[str]) -> None:
    for entry in overrides:
        if "=" not in entry:
            raise SystemExit(f"Invalid override '{entry}'. Use key=value.")
        key, value = entry.split("=", 1)
        parsed = parse_override_value(value)
        if "." in key:
            root, leaf = key.split(".", 1)
            target = config.setdefault(root, {})
            if not isinstance(target, dict):
                raise SystemExit(f"Override target '{root}' is not a mapping.")
            target[leaf] = parsed
        else:
            config.setdefault("configurable", {})[key] = parsed


def read_prompt(args: argparse.Namespace) -> str:
    if args.input_file:
        if args.input_file == "-":
            return sys.stdin.read()
        return Path(args.input_file).read_text(encoding="utf-8")
    if args.prompt:
        return args.prompt
    if not sys.stdin.isatty():
        return sys.stdin.read()
    raise SystemExit("Provide a prompt, --input-file, or stdin.")


def format_transcript_entry(role: str, content: str) -> str:
    if "\n" in content:
        return f"{role}:\n{content}"
    return f"{role}: {content}"


def normalize_message_content(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    try:
        return json.dumps(content, ensure_ascii=True)
    except TypeError:
        return str(content)


def extract_display_message(
    message: BaseMessage, seen_ids: set[str]
) -> tuple[str, str] | None:
    if message.__class__.__name__.endswith("MessageChunk"):
        return None
    message_type = getattr(message, "type", None)
    if message_type not in {"ai", "human"}:
        return None
    message_id = getattr(message, "id", None)
    if message_id and message_id in seen_ids:
        return None
    if message_id:
        seen_ids.add(message_id)
    content = normalize_message_content(getattr(message, "content", ""))
    if not content:
        return None
    role = "Assistant" if message_type == "ai" else "User"
    return role, content


def extract_display_from_dict(message: dict[str, Any]) -> tuple[str, str] | None:
    role_value = message.get("role") or message.get("type")
    if role_value not in {"assistant", "ai", "user", "human"}:
        return None
    content = normalize_message_content(message.get("content"))
    if not content:
        return None
    role = "Assistant" if role_value in {"assistant", "ai"} else "User"
    return role, content


def iter_message_updates(update: Any) -> Iterable[Any]:
    if isinstance(update, dict):
        messages = update.get("messages")
        if messages is None:
            return
        if isinstance(messages, list):
            for message in messages:
                yield message
        else:
            yield messages
    elif isinstance(update, list):
        for item in update:
            yield from iter_message_updates(item)


def build_runnable_config(config_payload: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    thread_id = args.thread_id or str(uuid.uuid4())
    config: dict[str, Any] = {"configurable": {"thread_id": thread_id}}
    if "configurable" in config_payload or "metadata" in config_payload:
        config["configurable"].update(config_payload.get("configurable", {}))
        metadata = config_payload.get("metadata")
        if metadata is not None:
            config["metadata"] = metadata
        for key, value in config_payload.items():
            if key not in {"configurable", "metadata"}:
                config[key] = value
    else:
        config["configurable"].update(config_payload)
    if args.owner:
        config.setdefault("metadata", {})["owner"] = args.owner
    return config


def append_transcript(
    transcript: list[str],
    role: str,
    content: str,
) -> None:
    entry = format_transcript_entry(role, content)
    print(entry, flush=True)
    transcript.append(entry)


async def stream_run(
    graph: Any,
    history: list[dict[str, str]],
    config: dict[str, Any],
    transcript: list[str],
) -> dict[str, Any]:
    final_state: dict[str, Any] = {}
    seen_ids: set[str] = set()
    new_history: list[dict[str, str]] = []
    async for event in graph.astream(
        {"messages": history},
        config,
        stream_mode=["updates", "values"],
    ):
        if isinstance(event, tuple):
            if len(event) == 3:
                _, mode, payload = event
            elif len(event) == 2:
                mode, payload = event
            else:
                continue
        else:
            mode = "values"
            payload = event
        if mode == "updates":
            if not isinstance(payload, dict):
                continue
            for update in payload.values():
                for message in iter_message_updates(update):
                    if isinstance(message, BaseMessage):
                        display = extract_display_message(message, seen_ids)
                    elif isinstance(message, dict):
                        display = extract_display_from_dict(message)
                    else:
                        display = None
                    if not display:
                        continue
                    role, content = display
                    if role != "Assistant":
                        continue
                    append_transcript(transcript, role, content)
                    new_history.append({"role": "assistant", "content": content})
        elif mode == "values":
            if isinstance(payload, dict):
                final_state = payload
    if new_history:
        history.extend(new_history)
    return final_state


async def run_interactive(prompt: str, config: dict[str, Any]) -> tuple[list[str], str]:
    graph = deep_researcher_builder.compile(checkpointer=MemorySaver())
    history: list[dict[str, str]] = [{"role": "user", "content": prompt}]
    transcript: list[str] = []
    final_report_text = ""
    append_transcript(transcript, "User", prompt)

    while True:
        final_state = await stream_run(graph, history, config, transcript)
        final_report = final_state.get("final_report") if isinstance(final_state, dict) else None
        if final_report:
            final_report_text = str(final_report)
            break
        if not history or history[-1]["role"] != "assistant":
            raise SystemExit("Run ended without a final report or clarification prompt.")
        if sys.stdin.isatty():
            response = input("Clarification> ")
        else:
            response = sys.stdin.readline()
            if not response:
                raise SystemExit("Clarification required, but stdin has no data.")
            response = response.rstrip("\n")
        history.append({"role": "user", "content": response})
        append_transcript(transcript, "User", response)
    return transcript, final_report_text


def main(argv: list[str] | None = None) -> int:
    load_dotenv()
    parser = build_parser()
    args = parser.parse_args(argv)
    prompt = read_prompt(args)
    config_payload = load_config_payload(args.config)
    config = build_runnable_config(config_payload, args)
    apply_overrides(config, args.overrides)
    transcript, final_report = asyncio.run(run_interactive(prompt, config))
    if args.output_file:
        Path(args.output_file).write_text("\n".join(transcript), encoding="utf-8")
    if args.output_json:
        if not final_report:
            raise SystemExit("No final report available to write as JSON.")
        Path(args.output_json).write_text(final_report, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
