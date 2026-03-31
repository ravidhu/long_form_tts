import { contextBridge, ipcRenderer } from 'electron'

// --- Types ---

export interface StageUpdate { number: number; name: string; total: number }
export interface SectionProgress { current: number; total: number; title: string }
export interface PipelineResult { code: number | null; outputDir: string; audioFile: string | null }
export interface PipelineConfig {
  pipeline: 'audiobook' | 'podcast'
  input: string
  output?: string
  sourceLang?: string
  targetLang?: string
}
export interface QueueJob {
  id: string; config: PipelineConfig
  status: 'queued' | 'running' | 'completed' | 'error' | 'stopped'
  label: string; addedAt: number; startedAt?: number; finishedAt?: number
  error?: string; outputDir?: string; audioFile?: string | null
}
export interface SetupStepStatus {
  step: string
  status: 'pending' | 'running' | 'done' | 'error' | 'skipped'
  message?: string
  progress?: number | null
}
export interface RecommendedModel {
  name: string; size: string; description: string; vram: string
}

// --- Helpers for IPC event listeners ---

function on<T>(channel: string, callback: (data: T) => void) {
  const listener = (_event: Electron.IpcRendererEvent, data: T) => callback(data)
  ipcRenderer.on(channel, listener)
  return () => ipcRenderer.removeListener(channel, listener)
}

function on2<A, B>(channel: string, callback: (a: A, b: B) => void) {
  const listener = (_event: Electron.IpcRendererEvent, a: A, b: B) => callback(a, b)
  ipcRenderer.on(channel, listener)
  return () => ipcRenderer.removeListener(channel, listener)
}

// --- API ---

const api = {
  // Setup
  setupCheck: () => ipcRenderer.invoke('setup:check') as Promise<{
    needsSetup: boolean; platform: string; arch: string; recommendedModels: RecommendedModel[]
  }>,
  setupRunAuto: () => ipcRenderer.invoke('setup:run-auto') as Promise<{ ok: boolean; error?: string }>,
  setupCheckOllama: () => ipcRenderer.invoke('setup:check-ollama') as Promise<{ connected: boolean; models: string[] }>,
  setupPullModel: (model: string) => ipcRenderer.invoke('setup:pull-model', model) as Promise<{ ok: boolean; error?: string }>,
  setupDownloadTts: () => ipcRenderer.invoke('setup:download-tts') as Promise<{ ok: boolean; error?: string }>,
  setupComplete: () => ipcRenderer.send('setup:complete'),
  onSetupStep: (cb: (step: SetupStepStatus) => void) => on<SetupStepStatus>('setup:step', cb),
  onSetupLog: (cb: (line: string) => void) => on<string>('setup:log', cb),

  // Ollama (post-setup)
  ollamaCheck: () => ipcRenderer.invoke('ollama:check') as Promise<{ connected: boolean }>,
  ollamaListModels: () => ipcRenderer.invoke('ollama:list-models') as Promise<{ models: string[] }>,

  // Queue
  enqueue: (config: PipelineConfig) => ipcRenderer.invoke('queue:enqueue', config) as Promise<QueueJob>,
  removeJob: (jobId: string) => ipcRenderer.invoke('queue:remove', jobId) as Promise<boolean>,
  requeueJob: (jobId: string) => ipcRenderer.invoke('queue:requeue', jobId) as Promise<QueueJob | null>,
  startQueue: () => ipcRenderer.send('queue:start'),
  stopCurrent: () => ipcRenderer.send('queue:stop-current'),
  clearCompleted: () => ipcRenderer.send('queue:clear-completed'),
  clearAll: () => ipcRenderer.send('queue:clear-all'),
  getJobs: () => ipcRenderer.invoke('queue:get-jobs') as Promise<QueueJob[]>,
  onQueueState: (cb: (jobs: QueueJob[]) => void) => on<QueueJob[]>('queue:state', cb),
  onJobLog: (cb: (jobId: string, line: string) => void) => on2<string, string>('queue:job:log', cb),
  onJobStage: (cb: (jobId: string, stage: StageUpdate) => void) => on2<string, StageUpdate>('queue:job:stage', cb),
  onJobSectionProgress: (cb: (jobId: string, p: SectionProgress) => void) => on2<string, SectionProgress>('queue:job:section-progress', cb),
  onJobComplete: (cb: (jobId: string, r: PipelineResult) => void) => on2<string, PipelineResult>('queue:job:complete', cb),
  onJobError: (cb: (jobId: string, e: string) => void) => on2<string, string>('queue:job:error', cb),

  // Dialogs
  openFile: () => ipcRenderer.invoke('dialog:open-file') as Promise<string | null>,
  openDirectory: () => ipcRenderer.invoke('dialog:open-directory') as Promise<string | null>,

  // Shell
  openPath: (path: string) => ipcRenderer.send('shell:open-path', path),
  showItemInFolder: (path: string) => ipcRenderer.send('shell:show-item', path)
}

contextBridge.exposeInMainWorld('electronAPI', api)
export type ElectronAPI = typeof api
