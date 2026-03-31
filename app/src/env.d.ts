/// <reference types="vite/client" />

interface StageUpdate { number: number; name: string; total: number }
interface SectionProgress { current: number; total: number; title: string }
interface PipelineResult { code: number | null; outputDir: string; audioFile: string | null }
interface PipelineConfig {
  pipeline: 'audiobook' | 'podcast'
  input: string
  output?: string
  sourceLang?: string
  targetLang?: string
  // LLM
  model?: string
  temperature?: number
  // TTS
  voice?: string        // audiobook: single voice
  voice1?: string       // podcast: speaker 1 voice
  voice2?: string       // podcast: speaker 2 voice
  speed?: number
  // Audiobook
  maxWorkers?: number
  // Podcast dialogue
  dialogueFormat?: 'two_hosts' | 'host_guest'
  voice1name?: string
  voice2name?: string
  duration?: number
  segmentWords?: number
}
interface QueueJob {
  id: string; config: PipelineConfig
  status: 'queued' | 'running' | 'completed' | 'error' | 'stopped'
  label: string; addedAt: number; startedAt?: number; finishedAt?: number
  error?: string; outputDir?: string; audioFile?: string | null
}
interface SetupStepStatus {
  step: string
  status: 'pending' | 'running' | 'done' | 'error' | 'skipped'
  message?: string
  progress?: number | null
}
interface RecommendedModel {
  name: string; size: string; description: string; vram: string
}

interface ElectronAPI {
  // Setup
  setupCheck: () => Promise<{ needsSetup: boolean; platform: string; arch: string; recommendedModels: RecommendedModel[]; ttsModelCached: boolean }>
  setupRunAuto: () => Promise<{ ok: boolean; error?: string }>
  setupCheckOllama: () => Promise<{ connected: boolean; models: string[] }>
  setupPullModel: (model: string) => Promise<{ ok: boolean; error?: string }>
  setupDownloadTts: () => Promise<{ ok: boolean; error?: string }>
  setupComplete: () => void
  onSetupStep: (cb: (step: SetupStepStatus) => void) => () => void
  onSetupLog: (cb: (line: string) => void) => () => void

  // Ollama
  ollamaCheck: () => Promise<{ connected: boolean }>
  ollamaListModels: () => Promise<{ models: string[] }>

  // Queue
  enqueue: (config: PipelineConfig) => Promise<QueueJob>
  removeJob: (jobId: string) => Promise<boolean>
  requeueJob: (jobId: string) => Promise<QueueJob | null>
  startQueue: () => void
  stopCurrent: () => void
  clearCompleted: () => void
  clearAll: () => void
  getJobs: () => Promise<QueueJob[]>
  onQueueState: (cb: (jobs: QueueJob[]) => void) => () => void
  onJobLog: (cb: (jobId: string, line: string) => void) => () => void
  onJobStage: (cb: (jobId: string, stage: StageUpdate) => void) => () => void
  onJobSectionProgress: (cb: (jobId: string, p: SectionProgress) => void) => () => void
  onJobComplete: (cb: (jobId: string, r: PipelineResult) => void) => () => void
  onJobError: (cb: (jobId: string, e: string) => void) => () => void

  // Dialogs
  openFile: () => Promise<string | null>
  openDirectory: () => Promise<string | null>

  // Shell
  openPath: (path: string) => void
  showItemInFolder: (path: string) => void
}

interface Window { electronAPI: ElectronAPI }
