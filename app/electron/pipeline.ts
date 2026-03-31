import { spawn, ChildProcess } from 'child_process'
import { EventEmitter } from 'events'
import { join, resolve } from 'path'
import { existsSync } from 'fs'

interface PipelineConfig {
  pipeline: 'audiobook' | 'podcast'
  input: string
  output?: string
  sourceLang?: string
  targetLang?: string
  model?: string
  temperature?: number
  voice?: string
  voice1?: string
  voice2?: string
  speed?: number
  maxWorkers?: number
  dialogueFormat?: 'two_hosts' | 'host_guest'
  voice1name?: string
  voice2name?: string
  duration?: number
  segmentWords?: number
}

const STAGE_TOTALS: Record<string, number> = {
  audiobook: 5,
  podcast: 7
}

export class PipelineRunner extends EventEmitter {
  private process: ChildProcess | null = null
  private projectRoot: string
  private uvPath: string
  private outputDir: string = ''
  private pipelineType: string = 'audiobook'
  private buffer: string = ''

  constructor(projectRoot: string, uvPath: string = 'uv') {
    super()
    this.projectRoot = projectRoot
    this.uvPath = uvPath
  }

  get isRunning(): boolean {
    return this.process !== null && this.process.exitCode === null
  }

  start(config: PipelineConfig): void {
    this.pipelineType = config.pipeline
    const script = config.pipeline === 'audiobook'
      ? 'scripts/audiobook.py'
      : 'scripts/podcast.py'

    const args = ['run', 'python', script]

    if (config.input) {
      args.push('-i', config.input)
    }
    if (config.output) {
      args.push('-o', config.output)
      this.outputDir = resolve(this.projectRoot, config.output)
    }
    if (config.sourceLang) {
      args.push('--source-lang', config.sourceLang)
    }
    if (config.targetLang) {
      args.push('--target-lang', config.targetLang)
    }

    // LLM overrides
    if (config.model) {
      args.push('--model', config.model)
    }
    if (config.temperature != null) {
      args.push('--temperature', String(config.temperature))
    }

    // TTS overrides
    if (config.speed != null) {
      args.push('--speed', String(config.speed))
    }

    if (config.pipeline === 'audiobook') {
      if (config.voice) {
        args.push('--voice', config.voice)
      }
      if (config.maxWorkers != null) {
        args.push('--max-workers', String(config.maxWorkers))
      }
    } else {
      // Podcast-specific
      if (config.voice1) {
        args.push('--voice1', config.voice1)
      }
      if (config.voice2) {
        args.push('--voice2', config.voice2)
      }
      if (config.dialogueFormat) {
        args.push('--format', config.dialogueFormat)
      }
      if (config.voice1name) {
        args.push('--voice1name', config.voice1name)
      }
      if (config.voice2name) {
        args.push('--voice2name', config.voice2name)
      }
      if (config.duration != null) {
        args.push('--duration', String(config.duration))
      }
      if (config.segmentWords != null) {
        args.push('--segment-words', String(config.segmentWords))
      }
    }

    this.process = spawn(this.uvPath, args, {
      cwd: this.projectRoot,
      env: { ...process.env },
      stdio: ['ignore', 'pipe', 'pipe']
    })

    this.process.stdout?.on('data', (data: Buffer) => {
      this.handleOutput(data.toString())
    })

    this.process.stderr?.on('data', (data: Buffer) => {
      const text = data.toString()
      // stderr often has warnings/progress from Python libs - show as log
      for (const line of text.split('\n')) {
        if (line.trim()) {
          this.emit('log', line)
        }
      }
    })

    this.process.on('close', (code) => {
      // Flush remaining buffer
      if (this.buffer.trim()) {
        this.parseLine(this.buffer)
      }
      this.buffer = ''

      const audioFile = this.findAudioOutput()
      this.emit('complete', {
        code,
        outputDir: this.outputDir,
        audioFile
      })
      this.process = null
    })

    this.process.on('error', (err) => {
      this.emit('error', `Failed to start pipeline: ${err.message}`)
      this.process = null
    })
  }

  stop(): void {
    if (this.process) {
      this.process.kill('SIGTERM')
      // Force kill after 5s if still running
      setTimeout(() => {
        if (this.process && this.process.exitCode === null) {
          this.process.kill('SIGKILL')
        }
      }, 5000)
    }
  }

  private handleOutput(data: string): void {
    this.buffer += data
    const lines = this.buffer.split('\n')
    // Keep the last incomplete line in the buffer
    this.buffer = lines.pop() || ''

    for (const line of lines) {
      this.parseLine(line)
    }
  }

  private parseLine(line: string): void {
    this.emit('log', line)

    // Capture output directory from "Output: <path>" line
    const outputMatch = line.match(/^Output:\s+(.+)/)
    if (outputMatch) {
      this.outputDir = resolve(this.projectRoot, outputMatch[1].trim())
    }

    // Detect stage transitions: "Stage N: <name>"
    const stageMatch = line.match(/^Stage (\d+):\s+(.+)/)
    if (stageMatch) {
      this.emit('stage', {
        number: parseInt(stageMatch[1]),
        name: stageMatch[2].trim(),
        total: STAGE_TOTALS[this.pipelineType] || 5
      })
      return
    }

    // Detect bracket-style progress: "[N/M] title"
    const bracketMatch = line.match(/\[(\d+)\/(\d+)\]\s+(.+?)(?:\s*[→(]|\.{3}|$)/)
    if (bracketMatch) {
      this.emit('section-progress', {
        current: parseInt(bracketMatch[1]),
        total: parseInt(bracketMatch[2]),
        title: bracketMatch[3].trim()
      })
      return
    }

    // Detect numbered progress: "  N. title" or "  N/M: title"
    const numberedMatch = line.match(/^\s+(\d+)\/(\d+):\s+(.+)/)
    if (numberedMatch) {
      this.emit('section-progress', {
        current: parseInt(numberedMatch[1]),
        total: parseInt(numberedMatch[2]),
        title: numberedMatch[3].trim()
      })
    }
  }

  private findAudioOutput(): string | null {
    if (!this.outputDir) return null

    const candidates = [
      join(this.outputDir, 'audiobook.wav'),
      join(this.outputDir, 'podcast.wav'),
      join(this.outputDir, 'podcast_partial.wav')
    ]

    for (const path of candidates) {
      if (existsSync(path)) return path
    }
    return null
  }
}
