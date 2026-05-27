# pi-less-yolo + little-coder — Quickstart

Run **little-coder** (a curated pi-based agent for small local models) inside an
isolated Docker container. Your host `~/.pi/agent/` is never touched.

## Prerequisites

- **Docker** (Desktop on macOS/Windows, Engine on Linux) or **Podman**
- **mise** >= 2024.12.0 — [install guide](https://mise.jdx.dev/installing-mise.html)
- **git**

## One-time Setup

```bash
# 1. Trust the project's mise config
cd /mnt/e/small-pi/pi-less-yolo
mise trust

# 2. Register tasks globally (so `mise run pi` works from any directory)
mise run install

# 3. Build the Docker image (~2 min)
mise run pi:build            # or: ./build-container.sh
```

> **Or just jump to step 4** — `mise run pi` auto-builds if the image is missing.

## Run

```bash
# Interactive session (from any project directory)
cd ~/my-project
mise run pi

# Single prompt (non-interactive)
mise run pi -- -p "summarize this repo"

# Read-only mode (project dir mounted read-only)
mise run pi:readonly
```

## Configure Once — `.env` Is Auto-Sourced

All pi tasks auto-source a `.env` file from the repo root. Set it once, forget
about env vars:

```bash
cp .env.example .env
# Edit .env — uncomment what you need:
#   PI_LOCAL_MODELS=1          # if using local models
#   LLAMACPP_API_KEY=noop     # local servers need a dummy key
#   ANTHROPIC_API_KEY=sk-...  # your cloud provider key
```

See `.env.example` for the full list of ~40 documented variables.

## Everything Lives on the Mount — Edit from Windows or WSL2

**`~/.pi/agent-little-coder/`** is the single persistent mount — you can edit
everything from the host, changes take effect immediately (no rebuild):

| Path | What you can change |
|---|---|
| `extensions/*/index.ts` | Add custom extensions or edit bundled ones |
| `skills/tools/*.md` | Tool-usage skill cards (loaded by skill-inject) |
| `skills/knowledge/*.md` | Algorithm cheat sheets (loaded by knowledge-inject) |
| `skills/protocols/*.md` | Research/workflow protocols |
| `settings.json` | Model profiles (thinking budget, temperature, etc.) |
| `models.json` | Provider definitions (llama.cpp, ollama, lmstudio) |
| `AGENTS.md` | System prompt (takes priority over bundled version) |
| `auth.json` | API credentials (create if needed) |

> **How overrides work:** The launcher and extensions check the mount FIRST,
> then fall back to the bundled copy inside the image. User files with the
> same name as bundled ones REPLACE them. User-only files are added alongside.

### Migrate from your existing config

```bash
cp ~/.pi/agent/auth.json      ~/.pi/agent-little-coder/
cp ~/.pi/agent/models.json    ~/.pi/agent-little-coder/
```

Everything else is auto-seeded on first run.

## Updating the Fork

```bash
cd vendor/little-coder && git pull && cd ../..
mise run pi:build
```

## All Tasks

| Command | What it does |
|---|---|
| `mise run pi` | Run little-coder in the sandboxed container |
| `mise run pi:shell` | Bash shell inside the container (same mounts) |
| `mise run pi:readonly` | Run with project dir read-only |
| `mise run pi:health` | Check setup for common problems |
| `mise run pi:build` | Build / rebuild the Docker image |
| `mise run pi:upgrade` | Pull fork + rebuild |
| `mise run pi:pi-acp` | ACP stdio connection for IDE integration |

## Host Isolation Guarantee

- `~/.pi/agent/` is **never mounted** — your global pi config stays on the host
- `~/.pi/agent-little-coder/` is the only pi directory accessible from the
  container — edit from Windows Explorer or WSL2 terminal
- The container runs with `--cap-drop=ALL`, `--no-new-privileges`,
  `--user $(id -u):$(id -g)`
