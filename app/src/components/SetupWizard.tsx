import { useEffect, useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Progress } from '@/components/ui/progress'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Badge } from '@/components/ui/badge'
import { useSetup } from '@/hooks/useSetup'
import {
  Loader2, CheckCircle2, XCircle, Circle, Download,
  ExternalLink, SkipForward, ChevronDown, ChevronRight
} from 'lucide-react'

const OLLAMA_INSTALL_URL: Record<string, string> = {
  darwin: 'https://ollama.com/download/mac',
  win32: 'https://ollama.com/download/windows',
  linux: 'https://ollama.com/download/linux'
}

interface SetupWizardProps {
  onComplete: () => void
}

export function SetupWizard({ onComplete }: SetupWizardProps) {
  const setup = useSetup()
  const [showLogs, setShowLogs] = useState(false)
  const [selectedModel, setSelectedModel] = useState('')

  // Auto-start the setup when phase is 'auto'
  useEffect(() => {
    if (setup.phase === 'auto' && setup.needsSetup && !setup.steps['project']) {
      setup.runAutoSetup()
    }
  }, [setup.phase, setup.needsSetup])

  // Auto-check ollama when entering ollama phase
  useEffect(() => {
    if (setup.phase === 'ollama') {
      setup.checkOllama()
    }
  }, [setup.phase])

  // Set default selected model
  useEffect(() => {
    if (setup.recommendedModels.length > 0 && !selectedModel) {
      setSelectedModel(setup.recommendedModels[0].name)
    }
  }, [setup.recommendedModels])

  // Auto-skip TTS if model is already cached
  useEffect(() => {
    if (setup.phase === 'tts' && setup.ttsModelCached) {
      setup.skipTts()
    }
  }, [setup.phase, setup.ttsModelCached])

  // Setup complete — notify parent
  useEffect(() => {
    if (setup.phase === 'done') {
      onComplete()
    }
  }, [setup.phase, onComplete])

  if (setup.phase === 'loading' || setup.needsSetup === null) {
    return (
      <div className="h-screen flex items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    )
  }

  // Already set up
  if (!setup.needsSetup && setup.phase === 'done') {
    return null
  }

  return (
    <div className="h-screen flex flex-col">
      <div className="titlebar-drag h-12 flex-shrink-0 flex items-center justify-center border-b bg-background/80 backdrop-blur">
        <h1 className="text-sm font-semibold text-muted-foreground">Long Form TTS — Setup</h1>
      </div>

      <div className="flex-1 overflow-y-auto">
        <div className="max-w-xl mx-auto p-6 space-y-4">
          {/* Step indicators */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base">First-time Setup</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <StepRow label="Python Runtime" step="python" phase={setup.phase} steps={setup.steps} activePhases={['auto']} />
              <StepRow label="Dependencies" step="dependencies" phase={setup.phase} steps={setup.steps} activePhases={['auto']} />
              <StepRow label="Ollama Connection" step="ollama-check" phase={setup.phase} steps={setup.steps} activePhases={['ollama']} />
              <StepRow label="LLM Model" step="ollama-model" phase={setup.phase} steps={setup.steps} activePhases={['ollama-model']} />
              <StepRow label="TTS Models" step="tts-models" phase={setup.phase} steps={setup.steps} activePhases={['tts']} />
            </CardContent>
          </Card>

          {/* Error display */}
          {setup.error && (
            <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
              {setup.error}
            </div>
          )}

          {/* Phase-specific content */}

          {/* Auto setup: show progress + logs */}
          {setup.phase === 'auto' && (
            <Card>
              <CardContent className="pt-5 space-y-3">
                <p className="text-sm text-muted-foreground">
                  Installing Python runtime and project dependencies. This may take a few minutes on first run...
                </p>
                <button
                  onClick={() => setShowLogs(!showLogs)}
                  className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
                >
                  {showLogs ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
                  {showLogs ? 'Hide' : 'Show'} install logs
                </button>
                {showLogs && setup.logs.length > 0 && (
                  <ScrollArea className="max-h-[200px] rounded border bg-muted/30">
                    <div className="p-2 font-mono text-[10px] leading-relaxed whitespace-pre-wrap">
                      {setup.logs.map((line, i) => <div key={i}>{line}</div>)}
                    </div>
                  </ScrollArea>
                )}
              </CardContent>
            </Card>
          )}

          {/* Ollama connection check */}
          {setup.phase === 'ollama' && !setup.ollamaConnected && (
            <Card>
              <CardContent className="pt-5 space-y-4">
                <p className="text-sm">
                  Ollama is required for LLM inference. Please install and start it:
                </p>
                <ol className="text-sm text-muted-foreground space-y-1 list-decimal list-inside">
                  <li>
                    Download from{' '}
                    <button
                      onClick={() => window.electronAPI.openPath(OLLAMA_INSTALL_URL[setup.platform] || 'https://ollama.com')}
                      className="text-primary underline inline-flex items-center gap-0.5"
                    >
                      ollama.com <ExternalLink className="h-3 w-3" />
                    </button>
                  </li>
                  <li>Install and launch Ollama</li>
                  <li>Click Retry below</li>
                </ol>
                <Button onClick={setup.retryOllama} variant="outline" size="sm">
                  Retry Connection
                </Button>
              </CardContent>
            </Card>
          )}

          {/* Ollama model selection */}
          {setup.phase === 'ollama-model' && (
            <Card>
              <CardContent className="pt-5 space-y-4">
                <p className="text-sm">
                  Select an LLM model for generating narration and dialogue:
                </p>

                {/* Already installed models */}
                {setup.ollamaModels.length > 0 && (
                  <div className="space-y-1">
                    <p className="text-xs text-muted-foreground font-medium">Installed models:</p>
                    <div className="flex flex-wrap gap-1">
                      {setup.ollamaModels.map((m) => (
                        <Badge key={m} variant="secondary" className="text-xs">{m}</Badge>
                      ))}
                    </div>
                  </div>
                )}

                {/* Model picker */}
                <div className="space-y-2">
                  {setup.recommendedModels.map((model) => {
                    const installed = setup.ollamaModels.some((m) =>
                      m === model.name || m.startsWith(model.name.split(':')[0] + ':')
                    )
                    return (
                      <label
                        key={model.name}
                        className={`flex items-start gap-3 p-3 rounded-lg border cursor-pointer transition-colors ${
                          selectedModel === model.name ? 'border-primary bg-primary/5' : 'hover:bg-muted/50'
                        }`}
                      >
                        <input
                          type="radio"
                          name="model"
                          value={model.name}
                          checked={selectedModel === model.name}
                          onChange={() => setSelectedModel(model.name)}
                          className="mt-0.5"
                        />
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium">{model.name}</span>
                            <span className="text-xs text-muted-foreground">{model.size}</span>
                            {installed && <Badge variant="outline" className="text-[10px]">Installed</Badge>}
                          </div>
                          <p className="text-xs text-muted-foreground">{model.description}</p>
                          <p className="text-[10px] text-muted-foreground/60">Requires ~{model.vram} VRAM</p>
                        </div>
                      </label>
                    )
                  })}
                </div>

                {/* Pull progress */}
                {setup.pullingModel && (
                  <div className="space-y-2">
                    <div className="flex items-center gap-2 text-sm">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      <span>Downloading {setup.pullingModel}...</span>
                    </div>
                    <Progress value={setup.pullProgress ?? 0} />
                    <p className="text-xs text-muted-foreground">{setup.pullStatus}</p>
                  </div>
                )}

                <div className="flex gap-2">
                  <Button
                    onClick={() => pullModelIfNeeded()}
                    disabled={!!setup.pullingModel || !selectedModel}
                    className="flex-1"
                  >
                    <Download className="mr-1.5 h-3.5 w-3.5" />
                    {setup.ollamaModels.some((m) => m.startsWith(selectedModel.split(':')[0]))
                      ? 'Continue'
                      : 'Download & Continue'}
                  </Button>
                  <Button variant="ghost" size="sm" onClick={setup.skipModelPull} className="text-xs">
                    <SkipForward className="mr-1 h-3 w-3" />
                    Skip
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}

          {/* TTS model download */}
          {setup.phase === 'tts' && (
            <Card>
              <CardContent className="pt-5 space-y-4">
                <p className="text-sm">
                  Download the Kokoro TTS model for text-to-speech rendering (~160 MB):
                </p>
                <p className="text-xs text-muted-foreground">
                  Platform: {setup.platform === 'darwin' && setup.arch === 'arm64' ? 'Apple Silicon (MLX)' : 'PyTorch'}
                </p>

                {setup.steps['tts-models']?.status === 'running' && (
                  <div className="flex items-center gap-2 text-sm">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    <span>{setup.steps['tts-models']?.message || 'Downloading...'}</span>
                  </div>
                )}

                <div className="flex gap-2">
                  <Button
                    onClick={setup.downloadTts}
                    disabled={setup.steps['tts-models']?.status === 'running'}
                    className="flex-1"
                  >
                    <Download className="mr-1.5 h-3.5 w-3.5" />
                    Download TTS Model
                  </Button>
                  <Button variant="ghost" size="sm" onClick={setup.skipTts} className="text-xs">
                    <SkipForward className="mr-1 h-3 w-3" />
                    Skip (download later)
                  </Button>
                </div>
              </CardContent>
            </Card>
          )}
        </div>
      </div>
    </div>
  )

  function pullModelIfNeeded() {
    const alreadyInstalled = setup.ollamaModels.some((m) =>
      m === selectedModel || m.startsWith(selectedModel.split(':')[0] + ':')
    )
    if (alreadyInstalled) {
      setup.skipModelPull()
    } else {
      setup.pullModel(selectedModel)
    }
  }
}

// --- Step indicator row ---

function StepRow({ label, step, phase, steps, activePhases }: {
  label: string
  step: string
  phase: SetupPhase
  steps: Record<string, SetupStepStatus>
  activePhases: string[]
}) {
  const stepStatus = steps[step]
  const isActive = activePhases.includes(phase)

  let icon = <Circle className="h-4 w-4 text-muted-foreground/40" />
  if (stepStatus?.status === 'running') {
    icon = <Loader2 className="h-4 w-4 animate-spin text-primary" />
  } else if (stepStatus?.status === 'done') {
    icon = <CheckCircle2 className="h-4 w-4 text-green-500" />
  } else if (stepStatus?.status === 'error') {
    icon = <XCircle className="h-4 w-4 text-destructive" />
  }

  return (
    <div className="flex items-center gap-3">
      {icon}
      <span className={`text-sm ${isActive ? 'text-foreground' : 'text-muted-foreground'}`}>
        {label}
      </span>
      {stepStatus?.message && stepStatus.status === 'done' && (
        <span className="text-xs text-muted-foreground ml-auto">{stepStatus.message}</span>
      )}
    </div>
  )
}
