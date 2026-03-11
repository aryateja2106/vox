# vox

**Talk to your terminal.** Natural language to shell commands, powered by a local AI model.

Stop memorizing flags. Stop Googling syntax. Just say what you want.

```
vox > find all python files bigger than 1MB
  find . -name "*.py" -size +1M -type f
  Run it? [Y/n/c] y
```

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/aryateja2106/vox/main/install.sh | bash
```

**Requirements:** Python 3.9+, [Ollama](https://ollama.ai) for local inference.

## Uninstall

```bash
curl -fsSL https://raw.githubusercontent.com/aryateja2106/vox/main/uninstall.sh | bash
```

## Usage

```bash
# Interactive mode — type naturally, get commands
vox

# Single command
vox "show what's running on port 3000"

# Auto-execute (skip confirmation)
vox -x "show free disk space"

# Use a different model
vox --model llama3.2 "list all docker containers"

# Raw command pass-through (in REPL)
vox > !ls -la
```

## Examples

| You say | Vox gives you |
|---------|---------------|
| find all python files | `find . -name "*.py"` |
| what's running on port 3000 | `lsof -ti:3000` |
| show disk usage sorted by size | `du -sh * \| sort -rh \| head -20` |
| start the docker compose stack | `docker compose up -d` |
| kill the process on port 8080 | `lsof -ti:8080 \| xargs kill` |
| show my git changes | `git diff --stat` |
| compress this folder | `tar czf archive.tar.gz .` |
| what's my public IP | `curl -s ifconfig.me` |
| find large files over 100MB | `find / -size +100M -type f 2>/dev/null \| head -20` |
| check if docker is running | `docker info > /dev/null 2>&1 && echo "running" \|\| echo "stopped"` |

## Why Vox?

- **100% Local** — Runs entirely on your machine. Nothing leaves your terminal. No API keys, no cloud, no subscriptions.
- **Tiny Model** — Powered by a fine-tuned model under 1 billion parameters. Works on any laptop without a GPU.
- **One Curl Install** — `curl | bash` and you're running. No Docker, no npm, no accounts.
- **Platform Smart** — Detects macOS vs Linux and gives you the right command for your system.
- **Voice Ready** — Built for voice input from day one. Talk to your terminal like you'd talk to a friend.
- **Open Source** — MIT licensed. Fork it. Train your own model. Make it yours.

## How It Works

```
You (English) → Vox → Local Model (Ollama) → Shell Command → You decide (run/copy/skip)
```

1. You type (or speak) what you want in plain English
2. Vox sends it to a local AI model running on your machine via Ollama
3. The model translates your intent to the correct shell command
4. You review the command and choose to run it, copy it, or skip

The model is a fine-tuned Qwen3.5-0.8B trained on 12,000+ natural language to shell command pairs, including expert-curated patterns from senior engineers.

## Configuration

Vox is configured via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `VOX_MODEL` | `nl2shell` | Ollama model name |
| `VOX_API_URL` | `http://localhost:11434` | Ollama API endpoint |

## The Problem We're Solving

The terminal is the most powerful interface on every computer. But it's also the most intimidating.

You know you need to find a large file, or check what's running on a port, or restart a Docker container. You know *what* you want — you just don't remember *how*. So you Google it. Or ask ChatGPT and pay $20/month for something a sub-1B model can handle locally.

We believe:

1. **Shell commands are a solved problem.** There are finite commands, finite flags, finite patterns. A small model can learn them all.
2. **Privacy matters.** Your terminal history shouldn't go to the cloud. Ever.
3. **Portability matters.** One curl command on any machine — Linux, macOS — and you're productive.
4. **The future is voice.** Typing commands is fast. Speaking them is faster. The interface should support both.

Vox is a step toward a world where the terminal understands you — not the other way around.

## Model

Vox is powered by [NL2Shell](https://github.com/aryateja2106/nl2shell), a fine-tuned Qwen3.5-0.8B model trained specifically for natural language to shell command translation.

- **Parameters:** ~859M (runs on CPU, no GPU needed)
- **Training data:** 12,000+ deduplicated NL→bash pairs including 960+ expert-curated commands
- **Format:** GGUF (via Ollama) for efficient local inference
- **Latency:** <500ms on Apple Silicon, <2s on most CPUs

You can also use any other Ollama model: `vox --model llama3.2`

## Contributing

```bash
git clone https://github.com/aryateja2106/vox.git
cd vox
uv sync
uv run python -m vox
```

## License

MIT
