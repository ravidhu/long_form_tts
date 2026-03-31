import { app } from 'electron'
import { join } from 'path'
import { existsSync } from 'fs'

// Writable data directory for the app
export function getDataDir(): string {
  return join(app.getPath('userData'), 'data')
}

// Python project directory (source + venv)
// Dev: parent of app/
// Production: copied to data dir on first launch (needs to be writable for .venv)
export function getProjectDir(): string {
  if (app.isPackaged) {
    return join(getDataDir(), 'project')
  }
  return join(__dirname, '..', '..', '..')
}

// Bundled project source (read-only, shipped with app)
export function getBundledProjectDir(): string {
  return join(process.resourcesPath, 'project')
}

// Path to uv binary
// Dev: system uv from PATH
// Production: bundled per-platform binary in resources/bin/
export function getUvPath(): string {
  if (app.isPackaged) {
    const ext = process.platform === 'win32' ? '.exe' : ''
    return join(process.resourcesPath, 'bin', `uv${ext}`)
  }
  return 'uv'
}

// TTS extra to install based on platform
export function getTtsExtra(): 'mlx' | 'torch' {
  if (process.platform === 'darwin' && process.arch === 'arm64') {
    return 'mlx'
  }
  return 'torch'
}

// Check if first-launch setup has been completed
export function isSetupDone(): boolean {
  const projectDir = getProjectDir()
  const marker = join(projectDir, '.setup-complete')
  return existsSync(marker)
}

// Check if Kokoro TTS model is already cached by huggingface_hub
export function isTtsModelCached(): boolean {
  const home = app.getPath('home')
  const extra = getTtsExtra()
  const repoId = extra === 'mlx'
    ? 'models--mlx-community--Kokoro-82M-bf16'
    : 'models--hexgrad--Kokoro-82M'
  const cachePath = join(home, '.cache', 'huggingface', 'hub', repoId, 'snapshots')
  return existsSync(cachePath)
}

// Recommended Ollama models (name, size hint, description)
export const RECOMMENDED_MODELS = [
  { name: 'qwen3:14b', size: '~9 GB', description: 'Recommended — best quality', vram: '12-15 GB' },
  { name: 'qwen3:8b', size: '~5 GB', description: 'Good balance of quality and speed', vram: '8-10 GB' },
  { name: 'qwen3:4b', size: '~2.5 GB', description: 'Lightweight — faster, lower quality', vram: '4-6 GB' }
]
