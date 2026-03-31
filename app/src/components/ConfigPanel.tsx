import { useState } from 'react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { FileText, Globe, Plus, FolderOpen, Link, ChevronDown, ChevronRight, Settings2, Info } from 'lucide-react'

const LANGUAGES = [
  { value: 'en', label: 'English' },
  { value: 'fr', label: 'French' },
  { value: 'es', label: 'Spanish' },
  { value: 'hi', label: 'Hindi' },
  { value: 'it', label: 'Italian' },
  { value: 'ja', label: 'Japanese' },
  { value: 'pt', label: 'Portuguese' },
  { value: 'zh', label: 'Chinese' }
]

const VOICE_PRESETS: Record<string, { label: string; voices: string[] }> = {
  en: { label: 'English', voices: ['af_heart', 'am_michael', 'af_bella', 'am_adam', 'bf_emma', 'bm_george'] },
  fr: { label: 'French', voices: ['ff_siwis'] },
  es: { label: 'Spanish', voices: ['ef_dora', 'em_alex'] },
  hi: { label: 'Hindi', voices: ['hf_alpha', 'hm_omega'] },
  it: { label: 'Italian', voices: ['if_sara', 'im_nicola'] },
  ja: { label: 'Japanese', voices: ['jf_alpha', 'jm_kumo'] },
  pt: { label: 'Portuguese', voices: ['pf_dora', 'pm_alex'] },
  zh: { label: 'Chinese', voices: ['zf_xiaobei', 'zm_yunjian'] }
}

const inputClass = 'w-full h-8 rounded-md border border-input bg-transparent px-3 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring'
const labelClass = 'text-xs font-medium text-muted-foreground'

interface ConfigPanelProps {
  onEnqueue: (config: PipelineConfig) => void
}

export function ConfigPanel({ onEnqueue }: ConfigPanelProps) {
  const [pipeline, setPipeline] = useState<'audiobook' | 'podcast'>('audiobook')
  const [inputMode, setInputMode] = useState<'file' | 'url'>('file')
  const [inputPath, setInputPath] = useState('')
  const [urlInput, setUrlInput] = useState('')
  const [outputDir, setOutputDir] = useState('')
  const [sourceLang, setSourceLang] = useState('en')
  const [targetLang, setTargetLang] = useState('en')
  const [showAdvanced, setShowAdvanced] = useState(false)

  // LLM
  const [model, setModel] = useState('')
  const [temperature, setTemperature] = useState('')

  // TTS
  const [voice, setVoice] = useState('')     // audiobook
  const [voice1, setVoice1] = useState('')   // podcast speaker 1
  const [voice2, setVoice2] = useState('')   // podcast speaker 2
  const [speed, setSpeed] = useState('')

  // Audiobook
  const [maxWorkers, setMaxWorkers] = useState('')

  // Podcast
  const [dialogueFormat, setDialogueFormat] = useState<'two_hosts' | 'host_guest'>('two_hosts')
  const [voice1name, setVoice1name] = useState('')
  const [voice2name, setVoice2name] = useState('')
  const [duration, setDuration] = useState('')
  const [segmentWords, setSegmentWords] = useState('')

  const handleBrowseFile = async () => {
    const path = await window.electronAPI.openFile()
    if (path) setInputPath(path)
  }

  const handleBrowseOutput = async () => {
    const path = await window.electronAPI.openDirectory()
    if (path) setOutputDir(path)
  }

  const handleEnqueue = () => {
    const input = inputMode === 'file' ? inputPath : urlInput
    if (!input.trim()) return

    // Default output to same directory as the input file
    let output = outputDir || undefined
    if (!output && inputMode === 'file' && input) {
      const lastSep = Math.max(input.lastIndexOf('/'), input.lastIndexOf('\\'))
      if (lastSep >= 0) {
        const dir = input.slice(0, lastSep)
        const now = new Date()
        const ts = [
          now.getFullYear(),
          String(now.getMonth() + 1).padStart(2, '0'),
          String(now.getDate()).padStart(2, '0'),
          '_',
          String(now.getHours()).padStart(2, '0'),
          String(now.getMinutes()).padStart(2, '0'),
          String(now.getSeconds()).padStart(2, '0')
        ].join('')
        output = `${dir}/${pipeline}_${ts}`
      }
    }

    const config: PipelineConfig = {
      pipeline,
      input: input.trim(),
      output,
      sourceLang: sourceLang !== 'en' ? sourceLang : undefined,
      targetLang: targetLang !== 'en' ? targetLang : undefined
    }

    // LLM overrides
    if (model) config.model = model
    if (temperature) config.temperature = parseFloat(temperature)

    // TTS overrides
    if (speed) config.speed = parseFloat(speed)

    if (pipeline === 'audiobook') {
      if (voice) config.voice = voice
      if (maxWorkers) config.maxWorkers = parseInt(maxWorkers)
    } else {
      if (voice1) config.voice1 = voice1
      if (voice2) config.voice2 = voice2
      if (dialogueFormat !== 'two_hosts') config.dialogueFormat = dialogueFormat
      if (voice1name) config.voice1name = voice1name
      if (voice2name) config.voice2name = voice2name
      if (duration) config.duration = parseInt(duration)
      if (segmentWords) config.segmentWords = parseInt(segmentWords)
    }

    onEnqueue(config)

    // Clear form after enqueue
    setInputPath('')
    setUrlInput('')
    setOutputDir('')
  }

  const inputValue = inputMode === 'file' ? inputPath : urlInput
  const canStart = inputValue.trim().length > 0

  // Compute default output path placeholder based on input file location
  const defaultOutputPlaceholder = (() => {
    if (inputMode === 'file' && inputPath) {
      const lastSep = Math.max(inputPath.lastIndexOf('/'), inputPath.lastIndexOf('\\'))
      const dir = lastSep >= 0 ? inputPath.slice(0, lastSep) : ''
      return `${dir}/${pipeline}_YYYYMMDD_HHMMSS`
    }
    return `output/${pipeline}_YYYYMMDD_HHMMSS`
  })()

  // Available voices for current target language
  const availableVoices = VOICE_PRESETS[targetLang]?.voices || VOICE_PRESETS.en.voices

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Configuration</CardTitle>
      </CardHeader>
      <CardContent className="space-y-5">
        {/* Pipeline type */}
        <div className="space-y-1.5">
          <label className="text-sm font-medium text-muted-foreground">Pipeline</label>
          <div className="flex gap-2">
            <Button
              variant={pipeline === 'audiobook' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setPipeline('audiobook')}
              className="flex-1"
            >
              <FileText className="mr-1.5 h-3.5 w-3.5" />
              Audiobook
            </Button>
            <Button
              variant={pipeline === 'podcast' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setPipeline('podcast')}
              className="flex-1"
            >
              <Globe className="mr-1.5 h-3.5 w-3.5" />
              Podcast
            </Button>
          </div>
        </div>

        {/* Input */}
        <div className="space-y-1.5">
          <label className="text-sm font-medium text-muted-foreground">Input</label>
          <div className="flex gap-2 mb-2">
            <button
              onClick={() => setInputMode('file')}
              className={`text-xs px-2 py-1 rounded ${
                inputMode === 'file'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-secondary-foreground'
              }`}
            >
              <FileText className="inline h-3 w-3 mr-1" />
              PDF File
            </button>
            <button
              onClick={() => setInputMode('url')}
              className={`text-xs px-2 py-1 rounded ${
                inputMode === 'url'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-secondary-foreground'
              }`}
            >
              <Link className="inline h-3 w-3 mr-1" />
              URL
            </button>
          </div>

          {inputMode === 'file' ? (
            <div className="flex gap-2">
              <input
                type="text"
                value={inputPath}
                onChange={(e) => setInputPath(e.target.value)}
                placeholder="Select a PDF file..."
                className="flex-1 h-9 rounded-md border border-input bg-transparent px-3 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                readOnly
              />
              <Button variant="outline" size="sm" onClick={handleBrowseFile}>
                <FolderOpen className="h-3.5 w-3.5" />
              </Button>
            </div>
          ) : (
            <input
              type="text"
              value={urlInput}
              onChange={(e) => setUrlInput(e.target.value)}
              placeholder="https://example.com/article or PDF URL..."
              className="w-full h-9 rounded-md border border-input bg-transparent px-3 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            />
          )}
        </div>

        {/* Output directory (optional) */}
        <div className="space-y-1.5">
          <label className="text-sm font-medium text-muted-foreground">
            Output Directory <span className="text-xs text-muted-foreground/60">(optional)</span>
          </label>
          <div className="flex gap-2">
            <input
              type="text"
              value={outputDir}
              onChange={(e) => setOutputDir(e.target.value)}
              placeholder={defaultOutputPlaceholder}
              className="flex-1 h-9 rounded-md border border-input bg-transparent px-3 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              readOnly
            />
            <Button variant="outline" size="sm" onClick={handleBrowseOutput}>
              <FolderOpen className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>

        {/* Languages */}
        <div className="grid grid-cols-2 gap-3">
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-muted-foreground">Source Language</label>
            <select
              value={sourceLang}
              onChange={(e) => setSourceLang(e.target.value)}
              className="w-full h-9 rounded-md border border-input bg-transparent px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              {LANGUAGES.map((lang) => (
                <option key={lang.value} value={lang.value}>
                  {lang.label}
                </option>
              ))}
            </select>
          </div>
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-muted-foreground">Target Language</label>
            <select
              value={targetLang}
              onChange={(e) => setTargetLang(e.target.value)}
              className="w-full h-9 rounded-md border border-input bg-transparent px-3 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
            >
              {LANGUAGES.map((lang) => (
                <option key={lang.value} value={lang.value}>
                  {lang.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {sourceLang !== targetLang && (
          <p className="text-xs text-muted-foreground">
            Cross-language mode: {sourceLang} &rarr; {targetLang}
          </p>
        )}

        {/* Advanced settings toggle */}
        <button
          onClick={() => setShowAdvanced(!showAdvanced)}
          className="flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          <Settings2 className="h-3.5 w-3.5" />
          {showAdvanced ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
          Advanced Settings
        </button>

        {showAdvanced && (
          <div className="space-y-4 rounded-lg border bg-muted/20 p-4">
            {/* LLM Settings */}
            <div className="space-y-3">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">LLM</p>
              <div className="grid grid-cols-2 gap-3">
                <div className="space-y-1">
                  <label className={labelClass}>Ollama Model</label>
                  <input
                    type="text"
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    placeholder="qwen3:14b"
                    className={inputClass}
                  />
                </div>
                <div className="space-y-1">
                  <label className={labelClass}>Temperature</label>
                  <input
                    type="number"
                    value={temperature}
                    onChange={(e) => setTemperature(e.target.value)}
                    placeholder={pipeline === 'audiobook' ? '0.3' : '0.7'}
                    min="0" max="2" step="0.1"
                    className={inputClass}
                  />
                </div>
              </div>
            </div>

            {/* TTS Settings */}
            <div className="space-y-3">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">TTS</p>

              {pipeline === 'audiobook' ? (
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1">
                    <label className={labelClass}>Voice</label>
                    <select
                      value={voice}
                      onChange={(e) => setVoice(e.target.value)}
                      className={inputClass}
                    >
                      <option value="">Default</option>
                      {availableVoices.map((v) => (
                        <option key={v} value={v}>{v}</option>
                      ))}
                    </select>
                  </div>
                  <div className="space-y-1">
                    <label className={labelClass}>Speed</label>
                    <input
                      type="number"
                      value={speed}
                      onChange={(e) => setSpeed(e.target.value)}
                      placeholder="0.95"
                      min="0.5" max="2" step="0.05"
                      className={inputClass}
                    />
                  </div>
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <label className={labelClass}>Speaker 1 Voice</label>
                      <select
                        value={voice1}
                        onChange={(e) => setVoice1(e.target.value)}
                        className={inputClass}
                      >
                        <option value="">Default</option>
                        {availableVoices.map((v) => (
                          <option key={v} value={v}>{v}</option>
                        ))}
                      </select>
                    </div>
                    <div className="space-y-1">
                      <label className={labelClass}>Speaker 2 Voice</label>
                      <select
                        value={voice2}
                        onChange={(e) => setVoice2(e.target.value)}
                        className={inputClass}
                      >
                        <option value="">Default</option>
                        {availableVoices.map((v) => (
                          <option key={v} value={v}>{v}</option>
                        ))}
                      </select>
                    </div>
                  </div>
                  <div className="space-y-1">
                    <label className={labelClass}>Speed</label>
                    <input
                      type="number"
                      value={speed}
                      onChange={(e) => setSpeed(e.target.value)}
                      placeholder="0.95"
                      min="0.5" max="2" step="0.05"
                      className={inputClass}
                    />
                  </div>
                </>
              )}
            </div>

            {/* Pipeline-specific settings */}
            <div className="space-y-3">
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                {pipeline === 'audiobook' ? 'Audiobook' : 'Podcast'}
              </p>

              {pipeline === 'audiobook' ? (
                <div className="space-y-1">
                  <label className={labelClass}>Parallel LLM Workers</label>
                  <input
                    type="number"
                    value={maxWorkers}
                    onChange={(e) => setMaxWorkers(e.target.value)}
                    placeholder="1"
                    min="1" max="8" step="1"
                    className={inputClass}
                  />
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <label className={labelClass}>Format</label>
                      <select
                        value={dialogueFormat}
                        onChange={(e) => setDialogueFormat(e.target.value as 'two_hosts' | 'host_guest')}
                        className={inputClass}
                      >
                        <option value="two_hosts">Two Hosts</option>
                        <option value="host_guest">Host + Guest</option>
                      </select>
                    </div>
                    <div className="space-y-1">
                      <label className={labelClass}>
                        Target Duration (min)
                        <span className="relative inline-block ml-1 group">
                          <Info className="inline h-3 w-3 text-muted-foreground/60 cursor-help" />
                          <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 hidden group-hover:block w-52 rounded bg-zinc-900 border border-zinc-700 px-2.5 py-1.5 text-[11px] text-zinc-100 shadow-md z-50">
                            When set to Auto, the LLM will cover all sections thoroughly with no fixed time limit. Set a value to guide the LLM toward a specific episode length.
                          </span>
                        </span>
                      </label>
                      <input
                        type="number"
                        value={duration}
                        onChange={(e) => setDuration(e.target.value)}
                        placeholder="Auto"
                        min="5" max="180" step="5"
                        className={inputClass}
                      />
                    </div>
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <label className={labelClass}>Speaker 1 Name</label>
                      <input
                        type="text"
                        value={voice1name}
                        onChange={(e) => setVoice1name(e.target.value)}
                        placeholder="Alex"
                        className={inputClass}
                      />
                    </div>
                    <div className="space-y-1">
                      <label className={labelClass}>Speaker 2 Name</label>
                      <input
                        type="text"
                        value={voice2name}
                        onChange={(e) => setVoice2name(e.target.value)}
                        placeholder="Sam"
                        className={inputClass}
                      />
                    </div>
                  </div>
                  <div className="space-y-1">
                    <label className={labelClass}>
                      Words per Segment
                      <span className="relative inline-block ml-1 group">
                        <Info className="inline h-3 w-3 text-muted-foreground/60 cursor-help" />
                        <span className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1.5 hidden group-hover:block w-52 rounded bg-zinc-900 border border-zinc-700 px-2.5 py-1.5 text-[11px] text-zinc-100 shadow-md z-50">
                          Controls how many words of dialogue the LLM generates per outline section. Lower values produce shorter, punchier segments; higher values give deeper discussion. Default 1200 ≈ 8 min per segment.
                        </span>
                      </span>
                    </label>
                    <input
                      type="number"
                      value={segmentWords}
                      onChange={(e) => setSegmentWords(e.target.value)}
                      placeholder="1200"
                      min="200" max="5000" step="100"
                      className={inputClass}
                    />
                    <p className="text-[10px] text-muted-foreground/60">~8 min per segment at 150 wpm</p>
                  </div>
                </>
              )}
            </div>
          </div>
        )}

        {/* Add to queue button */}
        <Button onClick={handleEnqueue} disabled={!canStart} className="w-full">
          <Plus className="mr-2 h-4 w-4" />
          Add to Queue
        </Button>
      </CardContent>
    </Card>
  )
}
