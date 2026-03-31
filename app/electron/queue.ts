import { randomUUID } from 'crypto'
import { EventEmitter } from 'events'
import { PipelineRunner } from './pipeline'

export type JobStatus = 'queued' | 'running' | 'completed' | 'error' | 'stopped'

export interface QueueJob {
  id: string
  config: {
    pipeline: 'audiobook' | 'podcast'
    input: string
    output?: string
    sourceLang?: string
    targetLang?: string
  }
  status: JobStatus
  label: string
  addedAt: number
  startedAt?: number
  finishedAt?: number
  error?: string
  outputDir?: string
  audioFile?: string | null
}

export class PipelineQueue extends EventEmitter {
  private jobs: QueueJob[] = []
  private runner: PipelineRunner | null = null
  private projectRoot: string
  private uvPath: string
  private started: boolean = false
  private stoppingJobId: string | null = null

  constructor(projectRoot: string, uvPath: string = 'uv') {
    super()
    this.projectRoot = projectRoot
    this.uvPath = uvPath
  }

  getJobs(): QueueJob[] {
    return [...this.jobs]
  }

  enqueue(config: QueueJob['config']): QueueJob {
    const inputName = config.input.split('/').pop()?.split('\\').pop() || config.input
    const label = `${config.pipeline === 'audiobook' ? 'Audiobook' : 'Podcast'} — ${inputName}`

    const job: QueueJob = {
      id: randomUUID(),
      config,
      status: 'queued',
      label,
      addedAt: Date.now()
    }

    this.jobs.push(job)
    this.emitState()
    // Auto-advance only if the queue was already started
    if (this.started) {
      this.processNext()
    }
    return job
  }

  start(): void {
    this.started = true
    this.processNext()
  }

  remove(jobId: string): boolean {
    const idx = this.jobs.findIndex((j) => j.id === jobId)
    if (idx === -1) return false

    const job = this.jobs[idx]

    // Can't remove a running job — use stop instead
    if (job.status === 'running') return false

    this.jobs.splice(idx, 1)
    this.emitState()
    return true
  }

  stopCurrent(): void {
    if (this.runner && this.currentJob) {
      this.stoppingJobId = this.currentJob.id
      this.runner.stop()
    }
  }

  requeue(jobId: string): QueueJob | null {
    const job = this.jobs.find((j) => j.id === jobId)
    if (!job || (job.status !== 'stopped' && job.status !== 'error')) return null

    // Reset job to queued state
    job.status = 'queued'
    job.error = undefined
    job.startedAt = undefined
    job.finishedAt = undefined
    job.outputDir = undefined
    job.audioFile = undefined
    this.emitState()

    // Auto-advance if queue is started
    if (this.started) {
      this.processNext()
    }
    return job
  }

  clearCompleted(): void {
    this.jobs = this.jobs.filter((j) => j.status === 'queued' || j.status === 'running')
    this.emitState()
  }

  clearAll(): void {
    // Keep running jobs, only clear non-running ones
    const running = this.jobs.filter((j) => j.status === 'running')
    this.jobs = running
    this.emitState()
  }

  private get currentJob(): QueueJob | undefined {
    return this.jobs.find((j) => j.status === 'running')
  }

  private get nextQueued(): QueueJob | undefined {
    return this.jobs.find((j) => j.status === 'queued')
  }

  private processNext(): void {
    // Already running something
    if (this.currentJob) return

    const next = this.nextQueued
    if (!next) return

    next.status = 'running'
    next.startedAt = Date.now()
    this.emitState()

    this.runner = new PipelineRunner(this.projectRoot, this.uvPath)

    this.runner.on('log', (line: string) => {
      this.emit('job:log', next.id, line)
    })

    this.runner.on('stage', (stage: { number: number; name: string; total: number }) => {
      this.emit('job:stage', next.id, stage)
    })

    this.runner.on('section-progress', (progress: { current: number; total: number; title: string }) => {
      this.emit('job:section-progress', next.id, progress)
    })

    this.runner.on('complete', (result: { code: number | null; outputDir: string; audioFile: string | null }) => {
      next.finishedAt = Date.now()
      next.outputDir = result.outputDir
      next.audioFile = result.audioFile

      if (result.code === 0) {
        next.status = 'completed'
      } else if (this.stoppingJobId === next.id) {
        next.status = 'stopped'
      } else {
        next.status = 'error'
        next.error = `Pipeline exited with code ${result.code}`
      }

      this.stoppingJobId = null
      this.runner = null
      this.emit('job:complete', next.id, result)
      this.emitState()

      // Process next job in queue
      this.processNext()
    })

    this.runner.on('error', (error: string) => {
      next.finishedAt = Date.now()
      next.status = 'error'
      next.error = error
      this.runner = null
      this.emit('job:error', next.id, error)
      this.emitState()

      this.processNext()
    })

    this.runner.start(next.config)
  }

  private emitState(): void {
    this.emit('state', this.getJobs())
  }
}
