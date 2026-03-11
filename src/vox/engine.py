"""Translation engine — sends NL to the local model and returns shell commands."""

from __future__ import annotations

import os
import re
import sys

import httpx

SYSTEM_PROMPT = (
    "You are an expert shell programmer on {platform}. "
    "Given a natural language request, output ONLY the corresponding shell command. "
    "No explanations, no markdown, no code fences, no comments. Just the raw command."
)

DEFAULT_MODEL = "nl2shell"
DEFAULT_API_URL = "http://localhost:11434"


def get_model() -> str:
    return os.environ.get("VOX_MODEL", DEFAULT_MODEL)


def get_api_url() -> str:
    return os.environ.get("VOX_API_URL", DEFAULT_API_URL)


def get_platform() -> str:
    """Detect platform for context-aware prompting."""
    if sys.platform == "darwin":
        return "macOS"
    elif sys.platform == "linux":
        return "Linux"
    elif sys.platform == "win32":
        return "Windows (PowerShell)"
    return "Unix"


def clean_response(text: str) -> str:
    """Strip common LLM artifacts from the response."""
    text = text.strip()
    # Remove markdown code fences (```bash ... ```)
    text = re.sub(r"^```(?:bash|sh|shell|zsh)?\n?", "", text)
    text = re.sub(r"\n?```$", "", text)
    # Remove inline backticks (`command`)
    if text.startswith("`") and text.endswith("`") and text.count("`") == 2:
        text = text[1:-1]
    # Remove leading $ or > prompt characters
    text = re.sub(r"^[$>]\s*", "", text)
    # Remove "Here is the command:" style preambles
    text = re.sub(
        r"^(?:Here (?:is|are) (?:the )?(?:command|script)s?:?\s*\n?)",
        "",
        text,
        flags=re.IGNORECASE,
    )
    # Strip leading comment lines (# ...) that precede the actual command
    lines = text.strip().split("\n")
    while lines and lines[0].strip().startswith("#"):
        lines.pop(0)
    text = "\n".join(lines)
    return text.strip()


def translate(query: str) -> str | None:
    """Translate natural language to a shell command using Ollama."""
    model = get_model()
    api_url = get_api_url()
    platform = get_platform()

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT.format(platform=platform)},
            {"role": "user", "content": query},
        ],
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 256,
        },
    }

    try:
        response = httpx.post(
            f"{api_url}/api/chat",
            json=payload,
            timeout=30.0,
        )
        response.raise_for_status()
        data = response.json()
        raw = data.get("message", {}).get("content", "")
        cmd = clean_response(raw)

        # Hard limit on response length
        if cmd and len(cmd) > 1000:
            print("  Response too long — likely not a single command.", file=sys.stderr)
            return None

        return cmd if cmd else None

    except KeyboardInterrupt:
        return None

    except httpx.ConnectError:
        print(
            f"  Cannot connect to Ollama at {api_url}\n"
            "  Start it with: ollama serve\n"
            "  Install from: https://ollama.ai",
            file=sys.stderr,
        )
        return None

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            print(
                f"  Model '{model}' not found.\n  Pull it with: ollama pull {model}",
                file=sys.stderr,
            )
        else:
            print(f"  API error: {e}", file=sys.stderr)
        return None

    except Exception as e:
        print(f"  Error: {e}", file=sys.stderr)
        return None


def check_ollama() -> bool:
    """Check if Ollama is running and the model is available."""
    api_url = get_api_url()
    try:
        r = httpx.get(f"{api_url}/api/tags", timeout=5.0)
        r.raise_for_status()
        models = [m["name"] for m in r.json().get("models", [])]
        model = get_model()
        return any(m == model or m.startswith(f"{model}:") for m in models)
    except Exception:
        return False
