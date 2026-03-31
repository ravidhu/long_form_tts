import { useState, useEffect, useCallback, useRef } from 'react'

export type SetupPhase = 'loading' | 'auto' | 'ollama' | 'ollama-model' | 'tts' | 'done'

interface SetupState {
  phase: SetupPhase
  needsSetup: boolean | null
  platform: string
  arch: string
  recommendedModels: RecommendedModel[]

  // Auto setup steps
  steps: Record<string, SetupStepStatus>
  logs: string[]

  // Ollama
  ollamaConnected: boolean
  ollamaModels: string[]
  pullingModel: string | null
  pullProgress: number | null
  pullStatus: string

  // TTS
  ttsModelCached: boolean

  // Errors
  error: string | null
}

export function useSetup() {
  const [state, setState] = useState<SetupState>({
    phase: 'loading',
    needsSetup: null,
    platform: '',
    arch: '',
    recommendedModels: [],
    steps: {},
    logs: [],
    ollamaConnected: false,
    ollamaModels: [],
    pullingModel: null,
    pullProgress: null,
    pullStatus: '',
    ttsModelCached: false,
    error: null
  })

  const cleanups = useRef<(() => void)[]>([])

  useEffect(() => {
    const api = window.electronAPI

    // Listen to setup events
    cleanups.current.push(
      api.onSetupStep((step) => {
        setState((prev) => ({
          ...prev,
          steps: { ...prev.steps, [step.step]: step },
          // Update pull progress if it's the ollama-model step
          ...(step.step === 'ollama-model' ? {
            pullProgress: step.progress ?? prev.pullProgress,
            pullStatus: step.message || prev.pullStatus
          } : {}),
          // Update error
          ...(step.status === 'error' ? { error: step.message || 'Unknown error' } : {})
        }))
      })
    )

    cleanups.current.push(
      api.onSetupLog((line) => {
        setState((prev) => ({
          ...prev,
          logs: [...prev.logs.slice(-200), line]
        }))
      })
    )

    // Check initial setup status
    api.setupCheck().then((result) => {
      setState((prev) => ({
        ...prev,
        needsSetup: result.needsSetup,
        platform: result.platform,
        arch: result.arch,
        recommendedModels: result.recommendedModels,
        ttsModelCached: result.ttsModelCached,
        phase: result.needsSetup ? 'auto' : 'done'
      }))
    })

    return () => {
      cleanups.current.forEach((fn) => fn())
      cleanups.current = []
    }
  }, [])

  const runAutoSetup = useCallback(async () => {
    setState((prev) => ({ ...prev, phase: 'auto', error: null }))
    const result = await window.electronAPI.setupRunAuto()
    if (result.ok) {
      setState((prev) => ({ ...prev, phase: 'ollama' }))
    } else {
      setState((prev) => ({ ...prev, error: result.error || 'Auto setup failed' }))
    }
  }, [])

  const checkOllama = useCallback(async () => {
    setState((prev) => ({ ...prev, error: null }))
    const result = await window.electronAPI.setupCheckOllama()
    setState((prev) => ({
      ...prev,
      ollamaConnected: result.connected,
      ollamaModels: result.models,
      ...(result.connected ? { phase: 'ollama-model' as const } : {})
    }))
    return result.connected
  }, [])

  const retryOllama = useCallback(async () => {
    await checkOllama()
  }, [checkOllama])

  const pullModel = useCallback(async (model: string) => {
    setState((prev) => ({
      ...prev,
      pullingModel: model,
      pullProgress: 0,
      pullStatus: 'Starting download...',
      error: null
    }))
    const result = await window.electronAPI.setupPullModel(model)
    if (result.ok) {
      // Refresh model list
      const ollamaResult = await window.electronAPI.setupCheckOllama()
      setState((prev) => ({
        ...prev,
        pullingModel: null,
        pullProgress: null,
        pullStatus: '',
        ollamaModels: ollamaResult.models,
        phase: 'tts'
      }))
    } else {
      setState((prev) => ({
        ...prev,
        pullingModel: null,
        error: result.error || 'Model download failed'
      }))
    }
  }, [])

  const skipModelPull = useCallback(() => {
    setState((prev) => ({ ...prev, phase: 'tts' }))
  }, [])

  const downloadTts = useCallback(async () => {
    setState((prev) => ({ ...prev, error: null }))
    const result = await window.electronAPI.setupDownloadTts()
    if (result.ok) {
      setState((prev) => ({ ...prev, phase: 'done' }))
      window.electronAPI.setupComplete()
    } else {
      setState((prev) => ({ ...prev, error: result.error || 'TTS download failed' }))
    }
  }, [])

  const skipTts = useCallback(() => {
    setState((prev) => ({ ...prev, phase: 'done' }))
    window.electronAPI.setupComplete()
  }, [])

  return {
    ...state,
    runAutoSetup,
    checkOllama,
    retryOllama,
    pullModel,
    skipModelPull,
    downloadTts,
    skipTts
  }
}
