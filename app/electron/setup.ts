import { spawn } from 'child_process'
import { EventEmitter } from 'events'
import { existsSync, mkdirSync, cpSync, writeFileSync } from 'fs'
import { join } from 'path'
import {
  getDataDir, getProjectDir, getBundledProjectDir,
  getUvPath, getTtsExtra, isSetupDone
} from './paths'
import * as ollama from './ollama'
import { app } from 'electron'

export type SetupStep =
  | 'checking'
  | 'project'
  | 'python'
  | 'dependencies'
  | 'ollama-check'
  | 'ollama-model'
  | 'tts-models'
  | 'done'

export interface SetupStepStatus {
  step: SetupStep
  status: 'pending' | 'running' | 'done' | 'error' | 'skipped'
  message?: string
  progress?: number | null
}

export class SetupManager extends EventEmitter {
  private uvPath: string
  private projectDir: string

  constructor() {
    super()
    this.uvPath = getUvPath()
    this.projectDir = getProjectDir()
  }

  get isComplete(): boolean {
    return isSetupDone()
  }

  // Run the automatic setup steps (no user interaction needed)
  async runAutoSetup(): Promise<void> {
    // Step 1: Ensure project source is in place
    this.emitStep('project', 'running', 'Preparing project files...')
    try {
      this.ensureProjectSource()
      this.emitStep('project', 'done')
    } catch (e) {
      this.emitStep('project', 'error', String(e))
      throw e
    }

    // Step 2: Install Python
    this.emitStep('python', 'running', 'Installing Python 3.11...')
    try {
      await this.runCommand(this.uvPath, ['python', 'install', '3.11'], this.projectDir)
      this.emitStep('python', 'done')
    } catch (e) {
      this.emitStep('python', 'error', String(e))
      throw e
    }

    // Step 3: Install dependencies
    const extra = getTtsExtra()
    this.emitStep('dependencies', 'running', `Installing dependencies (${extra} backend)...`)
    try {
      await this.runCommand(this.uvPath, ['sync', '--extra', extra], this.projectDir)
      this.emitStep('dependencies', 'done')
    } catch (e) {
      this.emitStep('dependencies', 'error', String(e))
      throw e
    }
  }

  // Check Ollama connection
  async checkOllama(): Promise<{ connected: boolean; models: string[] }> {
    this.emitStep('ollama-check', 'running', 'Checking Ollama connection...')
    const connected = await ollama.checkConnection()
    if (!connected) {
      this.emitStep('ollama-check', 'error', 'Ollama is not running. Please install and start Ollama.')
      return { connected: false, models: [] }
    }

    const models = await ollama.listModels()
    const modelNames = models.map((m) => m.name)
    this.emitStep('ollama-check', 'done', `Connected. ${models.length} model(s) available.`)
    return { connected: true, models: modelNames }
  }

  // Pull an Ollama model with progress
  async pullOllamaModel(model: string): Promise<void> {
    this.emitStep('ollama-model', 'running', `Downloading ${model}...`)
    try {
      await ollama.pullModel(model, (status, percent) => {
        this.emitStep('ollama-model', 'running', status, percent)
      })
      this.emitStep('ollama-model', 'done', `${model} ready.`)
    } catch (e) {
      this.emitStep('ollama-model', 'error', String(e))
      throw e
    }
  }

  // Download TTS models via Python
  async downloadTtsModels(): Promise<void> {
    const extra = getTtsExtra()
    this.emitStep('tts-models', 'running', 'Downloading TTS models (Kokoro)...')

    try {
      // Trigger Kokoro model download by importing the pipeline
      const script = extra === 'mlx'
        ? 'from huggingface_hub import snapshot_download; snapshot_download("mlx-community/Kokoro-82M-bf16")'
        : 'from huggingface_hub import snapshot_download; snapshot_download("hexgrad/Kokoro-82M")'

      await this.runCommand(
        this.uvPath,
        ['run', 'python', '-c', script],
        this.projectDir
      )
      this.emitStep('tts-models', 'done', 'Kokoro TTS model downloaded.')
    } catch (e) {
      this.emitStep('tts-models', 'error', String(e))
      throw e
    }
  }

  // Mark setup as complete
  markComplete(): void {
    const marker = join(this.projectDir, '.setup-complete')
    writeFileSync(marker, new Date().toISOString())
    this.emitStep('done', 'done')
  }

  // --- Private helpers ---

  private ensureProjectSource(): void {
    // In dev, project source is already at the project root
    if (!app.isPackaged) return

    // In production, copy bundled source to writable data dir
    const dataDir = getDataDir()
    if (!existsSync(dataDir)) {
      mkdirSync(dataDir, { recursive: true })
    }

    const dest = this.projectDir
    const src = getBundledProjectDir()

    if (!existsSync(src)) {
      throw new Error(`Bundled project not found at ${src}`)
    }

    // Only copy if project dir doesn't exist yet
    if (!existsSync(dest)) {
      cpSync(src, dest, { recursive: true })
    }
  }

  private runCommand(cmd: string, args: string[], cwd: string): Promise<string> {
    return new Promise((resolve, reject) => {
      const proc = spawn(cmd, args, {
        cwd,
        env: { ...process.env },
        stdio: ['ignore', 'pipe', 'pipe']
      })

      let stdout = ''
      let stderr = ''

      proc.stdout?.on('data', (data: Buffer) => {
        stdout += data.toString()
        // Emit log lines for the UI
        for (const line of data.toString().split('\n')) {
          if (line.trim()) this.emit('log', line)
        }
      })

      proc.stderr?.on('data', (data: Buffer) => {
        stderr += data.toString()
        for (const line of data.toString().split('\n')) {
          if (line.trim()) this.emit('log', line)
        }
      })

      proc.on('close', (code) => {
        if (code === 0) {
          resolve(stdout)
        } else {
          reject(new Error(`Command failed (exit ${code}): ${cmd} ${args.join(' ')}\n${stderr.slice(0, 500)}`))
        }
      })

      proc.on('error', (err) => {
        reject(new Error(`Failed to run ${cmd}: ${err.message}`))
      })
    })
  }

  private emitStep(step: SetupStep, status: SetupStepStatus['status'], message?: string, progress?: number | null): void {
    this.emit('step', { step, status, message, progress } satisfies SetupStepStatus)
  }
}
