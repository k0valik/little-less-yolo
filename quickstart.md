# pi-less-yolo + little-coder — Quickstart

Run **little-coder** (a curated pi-based agent for small local models) inside an
isolated Docker container. Your host `~/.pi/agent/` is never touched.

## Prerequisites

- **Docker** (Desktop on macOS/Windows, Engine on Linux) or **Podman**
- **mise** >= 2024.12.0 — [install guide](https://mise.jdx.dev/installing-mise.html)
- **git**

## One-time Setup

```bash
# 1. Clone the repo (needed for tasks/mise config — the pi commands live here)
git clone https://github.com/k0valik/little-less-yolo.git
cd little-less-yolo

# 2. Trust the project's mise config
mise trust

# 3. Register tasks globally (so `mise run pi` works from any directory)
mise run install
```

### 4. Get the Docker Image — Two Options

**Option A — Pull from GHCR (fast, CI-built):**

```bash
docker pull ghcr.io/k0valik/little-less-yolo:latest
docker tag ghcr.io/k0valik/little-less-yolo:latest pi-less-yolo:latest
```

The image is built by CI on every push to `main`. You don't need the little-coder
fork locally — it's baked in.

**Option B — Build locally (~2 min, needed if you modify Dockerfile or vendor/):**

```bash
mise run pi:build            # or: ./build-container.sh
```

> If you skip both, `mise run pi` will auto-build from source the first time
> (Option B, but slower since it's cold).

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

## Do You Need the Repo After Setup?

| What | Needs the repo? | Why |
|---|---|---|
| Running `mise run pi` | ✅ Yes | Tasks (`tasks/pi/`), `.env` auto-source, `_docker_flags` |
| Pulling the image from GHCR | ❌ No | Image is pre-built, just `docker pull` |
| Editing extensions/skills on the mount | ❌ No | They live in `~/.pi/agent-little-coder/` |
| Building locally after modifying Dockerfile | ✅ Yes | `./build-container.sh` or `mise run pi:build` |
| Updating the vendored fork | ✅ Yes | `cd vendor/little-coder && git pull` then rebuild |

**Bottom line:** Keep the clone — it's small (~50 MB with vendor/, excludes
node_modules via `.gitignore`). The tasks and config are read from it at runtime.

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
| `mise run lint` | Run hadolint + shellcheck locally (CI gate) |

## Host Isolation Guarantee

- `~/.pi/agent/` is **never mounted** — your global pi config stays on the host
- `~/.pi/agent-little-coder/` is the only pi directory accessible from the
  container — edit from Windows Explorer or WSL2 terminal
- The container runs with `--cap-drop=ALL`, `--no-new-privileges`,
  `--user $(id -u):$(id -g)`
