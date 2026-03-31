# Electron App

Desktop GUI for the Long Form TTS pipelines. Wraps the existing Python CLI scripts with a native Electron shell — no Python code changes needed.

## Quick Start

```bash
cd app
npm install
npm run dev    # launches Electron with hot reload
```

In dev mode, the app uses your system `uv` and the parent project directory. In production, everything is bundled.

## Architecture

```
Electron Main Process
├── main.ts         Window, IPC handlers, custom audio:// protocol
├── setup.ts        First-launch setup manager (Python, deps, Ollama, TTS)
├── paths.ts        Path resolution (dev vs production, platform detection)
├── ollama.ts       Ollama HTTP client (check, list, pull models)
├── queue.ts        Queue manager — sequential job execution
└── pipeline.ts     Subprocess runner — spawns uv, parses stdout

Electron Preload
└── preload.ts      Context bridge — exposes setup + queue API to renderer

React Renderer (Vite + TypeScript + Tailwind)
├── App.tsx         Root — shows SetupWizard or tabbed main app
├── hooks/
│   ├── useSetup.ts Setup state hook — phases, steps, model pull progress
│   └── useQueue.ts Queue state hook — jobs, logs, stage tracking
└── components/
    ├── SetupWizard.tsx   First-launch setup flow
    ├── ConfigPanel.tsx   Pipeline type, input, languages, "Add to Queue"
    └── QueuePanel.tsx    Job list with stage progress, logs, audio playback
```

### First-Launch Setup

On first launch, the app shows a **SetupWizard** that walks through:

1. **Project Source** — copies bundled Python source to writable app data directory (production only)
2. **Python Runtime** — installs Python 3.11 via bundled `uv`
3. **Dependencies** — runs `uv sync --extra mlx|torch` to install project deps
4. **Ollama Connection** — checks if Ollama is running, shows install instructions if not
5. **LLM Model** — lists installed Ollama models, offers recommended models (qwen3 family) for download with progress tracking
6. **TTS Models** — downloads Kokoro TTS model (~160 MB) from Hugging Face

Steps 5 and 6 can be skipped. A `.setup-complete` marker file prevents the wizard from showing again.

### How it Works

1. User configures a run in the **Configuration** tab and clicks **Add to Queue**
2. Jobs appear in the **Queue** tab with status `queued`
3. User clicks **Start** — the queue begins processing
4. **PipelineQueue** (main process) spawns `uv run python scripts/<pipeline>.py` via **PipelineRunner**
5. **PipelineRunner** parses stdout for stage transitions (`Stage N: ...`) and progress markers (`[N/M]`)
6. Updates flow via IPC to the renderer: queue state, per-job logs, stage progress
7. When a job completes, the next queued job auto-starts
8. Completed jobs show an inline audio player and "Open Folder" button

### UI Layout

The app uses a **tab-based layout** with two tabs:

- **Configuration** — pipeline settings (type, input, languages, LLM/TTS options), "Add to Queue" button
- **Queue** — job list with progress tracking, logs, and controls

The Queue tab shows a **badge** with the count of running + queued jobs for at-a-glance status.

#### Job Progress

Running jobs display a **stage list** showing all pipeline stages:
- Completed stages: green checkmark
- Current stage: spinning loader with section-level progress (e.g. `3/12 — Chapter 3`)
- Future stages: dimmed with stage number

The log viewer filters out noisy terminal output (separators, config headers, stage banners) since that information is shown in the stage list and config summary.

#### Job Actions

| Status | Actions |
|---|---|
| Queued | Remove from queue |
| Running | Stop (SIGTERM, force-kill after 5s) |
| Stopped | Re-queue, Remove |
| Error | Re-queue, Remove |
| Completed | Show Audio, Open Folder, Remove |

Re-queuing reuses the same output folder — the Python scripts skip cached steps and resume from where they left off.

### Audio Playback

Local `.wav` files are served via a custom `audio://` protocol registered in the main process. This avoids CSP issues with `file://` URLs while keeping playback secure.

## Stack

- **Electron** — native desktop shell
- **electron-vite** — build tooling (main + preload + renderer)
- **React 19** + **TypeScript** — renderer UI
- **Tailwind CSS 3** — styling
- **shadcn/ui** pattern — Button, Card, Progress, ScrollArea, Badge, Tabs components
- **Radix UI** — accessible primitives (Progress, ScrollArea, Tabs)

## Project Structure

```
app/
├── electron/
│   ├── main.ts              Electron main process + IPC
│   ├── preload.ts           Context bridge API
│   ├── setup.ts             First-launch setup manager
│   ├── paths.ts             Path resolution + platform detection
│   ├── ollama.ts            Ollama HTTP API client
│   ├── pipeline.ts          Subprocess manager (stdout parsing)
│   └── queue.ts             Job queue (sequential execution)
├── src/
│   ├── main.tsx             React entry
│   ├── App.tsx              Root component (setup wizard / tabbed main app)
│   ├── env.d.ts             TypeScript types for IPC API
│   ├── index.css            Tailwind base + custom styles
│   ├── lib/utils.ts         cn() utility
│   ├── hooks/
│   │   ├── useSetup.ts      Setup state hook
│   │   └── useQueue.ts      Queue state hook (jobs, stages, logs)
│   └── components/
│       ├── SetupWizard.tsx   First-launch setup flow
│       ├── ConfigPanel.tsx   Configuration form
│       ├── QueuePanel.tsx    Job queue UI
│       └── ui/              shadcn-style primitives (button, card, tabs, etc.)
├── resources/
│   └── bin/                 Platform-specific uv binaries (downloaded by Makefile)
├── index.html               Renderer HTML entry
├── electron.vite.config.ts  Build config
├── tailwind.config.js       Tailwind theme
├── postcss.config.js
├── tsconfig*.json
├── Makefile                 Build automation (dev, dist, release, uv download)
└── package.json
```

## Development

| Command | Description |
|---|---|
| `make dev` | Start in development mode with hot reload |
| `make build` | Build main + preload + renderer for production |
| `make preview` | Preview the production build |
| `make clean` | Remove `out/`, `release/`, `node_modules/`, `resources/bin/` |

All `make` targets auto-run `npm install` if `node_modules/` is missing or stale.

## Building for Distribution

The Makefile provides targets for packaging the app per platform.

### Download uv Binaries

Before building for distribution, download the platform-specific `uv` binaries:

```bash
make uv-mac       # macOS arm64 + x64
make uv-linux     # Linux x64
make uv-win       # Windows x64
make uv-all       # All platforms
```

Binaries are downloaded from [astral-sh/uv](https://github.com/astral-sh/uv/releases/latest) and placed in `resources/bin/<platform>/<arch>/`.

### Package & Distribute

```bash
make pack          # Unpacked build (for local testing, current platform)
make dist          # Build installer (current platform)
make dist-mac      # macOS .dmg (arm64 + x64 universal)
make dist-linux    # Linux .AppImage + .deb (x64, via Docker)
make dist-win      # Windows .exe + .zip (x64, via Docker)
make dist-all      # All three platforms
```

Linux and Windows builds use Docker images from `electronuserland/builder` to cross-compile from macOS.

### Release to GitHub

```bash
make release           # Build all platforms + publish draft release
make release-mac       # Build + publish macOS only
TAG=v1.2.3 make release  # Override version tag
```

The `publish` target:
1. Creates a git tag from `package.json` version (or `TAG` override)
2. Pushes the tag to origin
3. Creates a GitHub draft release with `gh release create`
4. Uploads all installers (`.dmg`, `.AppImage`, `.deb`, `.exe`, `.zip`)

Requires `gh` CLI installed and authenticated.

### What Gets Bundled

The production app bundles via `electron-builder` `extraResources`:
- **`uv` binary** — per-platform, from `resources/bin/`
- **Python scripts** — `scripts/` directory
- **Python source** — `src/` directory
- **Project config** — `pyproject.toml` + `uv.lock`

On first launch, the bundled project source is copied from the read-only `resources/` to a writable app data directory, where `uv` creates a venv and installs dependencies.

**Ollama** is the only external dependency users must install themselves.

Platform-specific TTS backend is auto-detected:
- macOS arm64 → MLX (`uv sync --extra mlx`)
- All others → PyTorch (`uv sync --extra torch`)
