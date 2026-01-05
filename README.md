# Open Deep Research Video Creation

This repo is a fork of LangChain's Open Deep Research. It keeps the same deep-research pipeline but changes the final output: instead of a long-form report, the system produces Veo-3 video prompts plus concise voiceover copy that can later be sent to a Gemini video generation API (API integration is planned but not implemented yet).

## What this fork does
- Runs multi-step research with search + MCP tools.
- Compresses research findings into a clean evidence set.
- Generates exactly 6 Veo-3-ready prompts with ~8-second voiceovers in JSON.

## Pipeline at a glance
1. Clarify the user's intent (optional).
2. Create a detailed research brief.
3. Supervisor delegates parallel research tasks.
4. Researchers gather sources and compress notes.
5. Final generator converts findings into Veo-3 prompt JSON.

## Output format
The final output is JSON only (no markdown), with exactly 6 prompts:

```json
{
  "video_prompts": [
    {
      "id": 1,
      "veo_prompt": "string",
      "voiceover": "string",
      "duration_seconds": 8
    }
  ]
}
```

## Repo map
- `src/open_deep_research/deep_researcher.py` - LangGraph pipeline; final stage generates Veo-3 prompts.
- `src/open_deep_research/prompts.py` - Prompt templates, including the video prompt schema.
- `src/open_deep_research/configuration.py` - Model and search configuration.
- `src/main.py` - CLI runner that prints a transcript and the final JSON.
- `tests/test_veo3.py` - Example script to call the Google GenAI client for Veo-3 video generation.
- `examples/` - Sample prompt outputs; `examples/video_from_veo3/` contains generated videos.
- `langgraph.json` - LangGraph server entrypoint config.

## Quickstart
1) Create and activate a virtual environment:
```bash
uv venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
```

2) Install dependencies:
```bash
uv sync
```

3) Set environment variables:
```bash
cp .env.example .env
```
Fill in keys for the models and tools you plan to use (for example `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `TAVILY_API_KEY`, or Azure settings if you use `azure_openai:*`).

## Run from the CLI
```bash
python src/main.py "Create a 6-shot video plan about quantum computing progress in 2025."
```

Write the transcript to a file:
```bash
python src/main.py --output-file outputs/quantum.txt "..."
```

Override configuration:
```bash
python src/main.py --set final_report_model="openai:gpt-4.1" --set search_api="tavily" "..."
```

## Video generation (planned)
The pipeline currently stops after generating Veo-3 prompts. A direct Gemini video generation API integration is planned. For now, `tests/test_veo3.py` shows a simple example of using `google-genai` to generate a video from a single prompt.

## Notes on configuration
Model and search settings live in `src/open_deep_research/configuration.py`. Defaults are set to `azure_openai:*` but can be swapped to OpenAI, Anthropic, Google, or other supported providers. Search options include Tavily, OpenAI native web search, Anthropic native web search, or no search.

## License
MIT. Original framework by LangChain; this fork adapts the final report stage for Veo-3 prompt generation.
