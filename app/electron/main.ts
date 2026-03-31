import { app, BrowserWindow, dialog, ipcMain, protocol, net, shell } from 'electron'
import { join } from 'path'
import { pathToFileURL } from 'url'
import { PipelineQueue } from './queue'
import { SetupManager } from './setup'
import { getProjectDir, getUvPath, isSetupDone, isTtsModelCached, RECOMMENDED_MODELS } from './paths'
import * as ollama from './ollama'

protocol.registerSchemesAsPrivileged([
  { scheme: 'audio', privileges: { stream: true, bypassCSP: true } }
])

let mainWindow: BrowserWindow | null = null
let queue: PipelineQueue | null = null
let setupManager: SetupManager | null = null

function send(channel: string, ...args: unknown[]): void {
  mainWindow?.webContents.send(channel, ...args)
}

function getQueue(): PipelineQueue {
  if (!queue) {
    queue = new PipelineQueue(getProjectDir(), getUvPath())

    queue.on('state', (jobs) => send('queue:state', jobs))
    queue.on('job:log', (jobId, line) => send('queue:job:log', jobId, line))
    queue.on('job:stage', (jobId, stage) => send('queue:job:stage', jobId, stage))
    queue.on('job:section-progress', (jobId, progress) => send('queue:job:section-progress', jobId, progress))
    queue.on('job:complete', (jobId, result) => send('queue:job:complete', jobId, result))
    queue.on('job:error', (jobId, error) => send('queue:job:error', jobId, error))
  }
  return queue
}

function getSetupManager(): SetupManager {
  if (!setupManager) {
    setupManager = new SetupManager()
    setupManager.on('step', (stepStatus) => send('setup:step', stepStatus))
    setupManager.on('log', (line) => send('setup:log', line))
  }
  return setupManager
}

function createWindow(): void {
  mainWindow = new BrowserWindow({
    width: 960,
    height: 800,
    minWidth: 700,
    minHeight: 600,
    titleBarStyle: 'hiddenInset',
    trafficLightPosition: { x: 16, y: 16 },
    webPreferences: {
      preload: join(__dirname, '..', 'preload', 'index.mjs'),
      sandbox: false
    }
  })

  if (process.env.ELECTRON_RENDERER_URL) {
    mainWindow.loadURL(process.env.ELECTRON_RENDERER_URL)
  } else {
    mainWindow.loadFile(join(__dirname, '..', 'renderer', 'index.html'))
  }
}

app.whenReady().then(() => {
  protocol.handle('audio', (request) => {
    const filePath = decodeURIComponent(request.url.slice('audio:///'.length))
    return net.fetch(pathToFileURL(filePath).toString())
  })

  createWindow()

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow()
  })
})

app.on('window-all-closed', () => {
  queue?.stopCurrent()
  if (process.platform !== 'darwin') app.quit()
})

// --- Dialog IPC ---

ipcMain.handle('dialog:open-file', async () => {
  const result = await dialog.showOpenDialog({
    properties: ['openFile'],
    filters: [{ name: 'PDF Files', extensions: ['pdf'] }]
  })
  return result.canceled ? null : result.filePaths[0]
})

ipcMain.handle('dialog:open-directory', async () => {
  const result = await dialog.showOpenDialog({
    properties: ['openDirectory', 'createDirectory']
  })
  return result.canceled ? null : result.filePaths[0]
})

ipcMain.on('shell:open-path', (_event, filePath: string) => {
  shell.openPath(filePath)
})

ipcMain.on('shell:show-item', (_event, filePath: string) => {
  shell.showItemInFolder(filePath)
})

// --- Setup IPC ---

ipcMain.handle('setup:check', () => {
  return {
    needsSetup: !isSetupDone(),
    platform: process.platform,
    arch: process.arch,
    recommendedModels: RECOMMENDED_MODELS,
    ttsModelCached: isTtsModelCached()
  }
})

ipcMain.handle('setup:run-auto', async () => {
  try {
    await getSetupManager().runAutoSetup()
    return { ok: true }
  } catch (e) {
    return { ok: false, error: String(e) }
  }
})

ipcMain.handle('setup:check-ollama', async () => {
  try {
    return await getSetupManager().checkOllama()
  } catch {
    return { connected: false, models: [] }
  }
})

ipcMain.handle('setup:pull-model', async (_event, model: string) => {
  try {
    await getSetupManager().pullOllamaModel(model)
    return { ok: true }
  } catch (e) {
    return { ok: false, error: String(e) }
  }
})

ipcMain.handle('setup:download-tts', async () => {
  try {
    await getSetupManager().downloadTtsModels()
    return { ok: true }
  } catch (e) {
    return { ok: false, error: String(e) }
  }
})

ipcMain.on('setup:complete', () => {
  getSetupManager().markComplete()
})

// --- Ollama IPC (for use after setup too) ---

ipcMain.handle('ollama:list-models', async () => {
  try {
    const models = await ollama.listModels()
    return { models: models.map((m) => m.name) }
  } catch {
    return { models: [] }
  }
})

ipcMain.handle('ollama:check', async () => {
  return { connected: await ollama.checkConnection() }
})

// --- Queue IPC ---

ipcMain.handle('queue:enqueue', (_event, config) => {
  const job = getQueue().enqueue(config)
  return job
})

ipcMain.handle('queue:remove', (_event, jobId: string) => {
  return getQueue().remove(jobId)
})

ipcMain.on('queue:start', () => {
  getQueue().start()
})

ipcMain.on('queue:stop-current', () => {
  getQueue().stopCurrent()
})

ipcMain.handle('queue:requeue', (_event, jobId: string) => {
  return getQueue().requeue(jobId)
})

ipcMain.on('queue:clear-completed', () => {
  getQueue().clearCompleted()
})

ipcMain.on('queue:clear-all', () => {
  getQueue().clearAll()
})

ipcMain.handle('queue:get-jobs', () => {
  return getQueue().getJobs()
})
