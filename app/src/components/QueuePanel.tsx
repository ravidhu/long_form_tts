import { useState } from 'react'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Progress } from '@/components/ui/progress'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Loader2, CheckCircle2, XCircle, Clock, Trash2, StopCircle,
  ChevronDown, ChevronRight, FolderOpen, Music, X, Play, RotateCcw
} from 'lucide-react'

interface JobRuntime {
  logs: string[]
  stages: StageUpdate[]
  currentStage: StageUpdate | null
  sectionProgress: SectionProgress | null
}

interface QueuePanelProps {
  jobs: QueueJob[]
  getRuntimeForJob: (jobId: string) => JobRuntime
  onStart: () => void
  onRemove: (jobId: string) => void
  onRequeue: (jobId: string) => void
  onStopCurrent: () => void
  onClearCompleted: () => void
  onClearAll: () => void
}

const STATUS_ICON: Record<string, React.ReactNode> = {
  queued: <Clock className="h-3.5 w-3.5 text-muted-foreground" />,
  running: <Loader2 className="h-3.5 w-3.5 animate-spin text-blue-500" />,
  completed: <CheckCircle2 className="h-3.5 w-3.5 text-green-500" />,
  error: <XCircle className="h-3.5 w-3.5 text-destructive" />,
  stopped: <StopCircle className="h-3.5 w-3.5 text-yellow-500" />
}

const STATUS_BADGE: Record<string, 'default' | 'secondary' | 'destructive' | 'outline'> = {
  queued: 'secondary',
  running: 'default',
  completed: 'outline',
  error: 'destructive',
  stopped: 'secondary'
}

export function QueuePanel({
  jobs, getRuntimeForJob, onStart, onRemove, onRequeue, onStopCurrent, onClearCompleted, onClearAll
}: QueuePanelProps) {
  const [expandedJob, setExpandedJob] = useState<string | null>(null)

  if (jobs.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
        <Clock className="h-8 w-8 mb-3 opacity-40" />
        <p className="text-sm">No jobs in queue</p>
        <p className="text-xs mt-1">Add a job from the Configuration tab to get started</p>
      </div>
    )
  }

  const runningJob = jobs.find((j) => j.status === 'running')
  const queuedCount = jobs.filter((j) => j.status === 'queued').length
  const completedCount = jobs.filter((j) => j.status !== 'queued' && j.status !== 'running').length

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <CardTitle className="text-base">Queue</CardTitle>
            <span className="text-xs text-muted-foreground">
              {jobs.length} job{jobs.length !== 1 ? 's' : ''}
              {queuedCount > 0 && ` (${queuedCount} waiting)`}
            </span>
          </div>
          <div className="flex gap-1">
            {queuedCount > 0 && !runningJob && (
              <Button size="sm" onClick={onStart} className="h-7 text-xs">
                <Play className="mr-1 h-3 w-3" />
                Start
              </Button>
            )}
            {completedCount > 0 && (
              <Button variant="ghost" size="sm" onClick={onClearCompleted} className="h-7 text-xs">
                Clear Done
              </Button>
            )}
            {jobs.length > 0 && (
              <Button variant="ghost" size="sm" onClick={onClearAll} className="h-7 text-xs text-destructive hover:text-destructive">
                Clear All
              </Button>
            )}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-2">
        {jobs.map((job) => {
          const isExpanded = expandedJob === job.id
          const runtime = getRuntimeForJob(job.id)

          return (
            <div
              key={job.id}
              className="rounded-lg border bg-muted/20 overflow-hidden"
            >
              {/* Job header */}
              <div
                className="flex items-center gap-2 px-3 py-2 cursor-pointer hover:bg-muted/40"
                onClick={() => setExpandedJob(isExpanded ? null : job.id)}
              >
                {isExpanded
                  ? <ChevronDown className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
                  : <ChevronRight className="h-3.5 w-3.5 text-muted-foreground flex-shrink-0" />
                }
                {STATUS_ICON[job.status]}
                <span className="text-sm flex-1 truncate">{job.label}</span>
                <Badge variant={STATUS_BADGE[job.status]} className="text-[10px] px-1.5 py-0">
                  {job.status}
                </Badge>

                {/* Action buttons */}
                {job.status === 'running' && (
                  <Button
                    variant="ghost" size="icon" className="h-6 w-6"
                    onClick={(e) => { e.stopPropagation(); onStopCurrent() }}
                  >
                    <StopCircle className="h-3.5 w-3.5 text-destructive" />
                  </Button>
                )}
                {job.status === 'queued' && (
                  <Button
                    variant="ghost" size="icon" className="h-6 w-6"
                    onClick={(e) => { e.stopPropagation(); onRemove(job.id) }}
                  >
                    <X className="h-3.5 w-3.5" />
                  </Button>
                )}
              </div>

              {/* Running job progress (always visible) */}
              {job.status === 'running' && runtime.currentStage && (
                <div className="px-3 pb-2 space-y-1.5">
                  <Progress
                    value={(runtime.currentStage.number / runtime.currentStage.total) * 100}
                    className="h-1.5"
                  />
                  <div className="space-y-0.5">
                    {Array.from({ length: runtime.currentStage.total }, (_, i) => {
                      const stageNum = i + 1
                      const stage = runtime.stages.find((s) => s.number === stageNum)
                      const isCurrent = stageNum === runtime.currentStage!.number
                      const isDone = stageNum < runtime.currentStage!.number
                      return (
                        <div key={stageNum} className={`flex items-center gap-1.5 text-[11px] ${
                          isCurrent ? 'text-foreground font-medium' : isDone ? 'text-muted-foreground' : 'text-muted-foreground/40'
                        }`}>
                          {isDone ? (
                            <CheckCircle2 className="h-3 w-3 text-green-500 flex-shrink-0" />
                          ) : isCurrent ? (
                            <Loader2 className="h-3 w-3 animate-spin text-blue-500 flex-shrink-0" />
                          ) : (
                            <span className="h-3 w-3 flex items-center justify-center flex-shrink-0 text-[9px]">{stageNum}</span>
                          )}
                          <span>{stage?.name || `Stage ${stageNum}`}</span>
                          {isCurrent && runtime.sectionProgress && (
                            <span className="ml-auto text-[10px] text-muted-foreground">
                              {runtime.sectionProgress.current}/{runtime.sectionProgress.total} — {runtime.sectionProgress.title}
                            </span>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              )}

              {/* Expanded detail */}
              {isExpanded && (
                <div className="border-t px-3 py-2 space-y-2">
                  {/* Config summary */}
                  <div className="text-xs text-muted-foreground space-y-0.5">
                    <div>Pipeline: {job.config.pipeline}</div>
                    <div className="truncate">Input: {job.config.input}</div>
                    {job.config.sourceLang && <div>Language: {job.config.sourceLang} &rarr; {job.config.targetLang || job.config.sourceLang}</div>}
                    {job.outputDir && <div className="truncate">Output: {job.outputDir}</div>}
                    {job.error && <div className="text-destructive">Error: {job.error}</div>}
                  </div>

                  {/* Completed job actions */}
                  {job.status === 'completed' && job.audioFile && (
                    <div className="flex gap-2">
                      <Button
                        variant="outline" size="sm" className="h-7 text-xs flex-1"
                        onClick={() => job.audioFile && window.electronAPI.showItemInFolder(job.audioFile)}
                      >
                        <Music className="mr-1 h-3 w-3" />
                        Show Audio
                      </Button>
                      <Button
                        variant="outline" size="sm" className="h-7 text-xs flex-1"
                        onClick={() => job.outputDir && window.electronAPI.openPath(job.outputDir)}
                      >
                        <FolderOpen className="mr-1 h-3 w-3" />
                        Open Folder
                      </Button>
                    </div>
                  )}

                  {/* Audio player for completed jobs */}
                  {job.status === 'completed' && job.audioFile && (
                    <audio
                      controls
                      src={`audio:///${encodeURIComponent(job.audioFile)}`}
                      className="w-full h-8"
                      preload="metadata"
                    />
                  )}

                  {/* Log viewer for running/expanded jobs */}
                  {runtime.logs.length > 0 && (
                    <ScrollArea className="max-h-[200px] rounded border bg-muted/30">
                      <div className="p-2 font-mono text-[10px] leading-relaxed whitespace-pre-wrap">
                        {runtime.logs.filter(filterLogLine).map((line, i) => (
                          <div key={i} className={getLineClass(line)}>{line}</div>
                        ))}
                      </div>
                    </ScrollArea>
                  )}

                  {/* Actions for finished jobs */}
                  {(job.status === 'completed' || job.status === 'error' || job.status === 'stopped') && (
                    <div className="flex gap-2">
                      {(job.status === 'stopped' || job.status === 'error') && (
                        <Button
                          variant="outline" size="sm" className="h-7 text-xs flex-1"
                          onClick={() => onRequeue(job.id)}
                        >
                          <RotateCcw className="mr-1 h-3 w-3" />
                          Re-queue
                        </Button>
                      )}
                      <Button
                        variant="ghost" size="sm" className="h-7 text-xs flex-1"
                        onClick={() => onRemove(job.id)}
                      >
                        <Trash2 className="mr-1 h-3 w-3" />
                        Remove
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </div>
          )
        })}
      </CardContent>
    </Card>
  )
}

/** Hide noisy terminal lines — config header, separators, and stage banners
 *  (stage progress is shown via the dedicated stage list UI). */
function filterLogLine(line: string): boolean {
  if (line.startsWith('====')) return false
  if (line.startsWith('Stage ')) return false
  if (/^(Output|Format|Target duration|Language|LLM|TTS|  Ollama|  Lang):?\s/.test(line)) return false
  if (line.trim() === '') return false
  return true
}

function getLineClass(line: string): string {
  if (line.includes('ERROR') || line.includes('Error') || line.includes('Traceback')) return 'text-destructive'
  if (line.includes('cached')) return 'text-muted-foreground'
  return 'text-foreground/80'
}
