import { useState, useEffect, useCallback, useRef } from 'react'

interface JobRuntime {
  logs: string[]
  stages: StageUpdate[]
  currentStage: StageUpdate | null
  sectionProgress: SectionProgress | null
}

interface QueueState {
  jobs: QueueJob[]
  jobRuntime: Record<string, JobRuntime>
}

export function useQueue() {
  const [state, setState] = useState<QueueState>({
    jobs: [],
    jobRuntime: {}
  })

  const cleanupFns = useRef<(() => void)[]>([])

  useEffect(() => {
    const api = window.electronAPI

    // Fetch initial state
    api.getJobs().then((jobs) => {
      setState((prev) => ({ ...prev, jobs }))
    })

    // Listen to queue state changes
    cleanupFns.current.push(
      api.onQueueState((jobs) => {
        setState((prev) => ({ ...prev, jobs }))
      })
    )

    cleanupFns.current.push(
      api.onJobLog((jobId, line) => {
        setState((prev) => ({
          ...prev,
          jobRuntime: {
            ...prev.jobRuntime,
            [jobId]: {
              ...getRuntime(prev, jobId),
              logs: [...(getRuntime(prev, jobId).logs), line]
            }
          }
        }))
      })
    )

    cleanupFns.current.push(
      api.onJobStage((jobId, stage) => {
        setState((prev) => {
          const rt = getRuntime(prev, jobId)
          // Append to stages list (avoid duplicates by stage number)
          const stages = rt.stages.some((s) => s.number === stage.number)
            ? rt.stages
            : [...rt.stages, stage]
          return {
            ...prev,
            jobRuntime: {
              ...prev.jobRuntime,
              [jobId]: {
                ...rt,
                stages,
                currentStage: stage,
                sectionProgress: null
              }
            }
          }
        })
      })
    )

    cleanupFns.current.push(
      api.onJobSectionProgress((jobId, progress) => {
        setState((prev) => ({
          ...prev,
          jobRuntime: {
            ...prev.jobRuntime,
            [jobId]: {
              ...getRuntime(prev, jobId),
              sectionProgress: progress
            }
          }
        }))
      })
    )

    return () => {
      cleanupFns.current.forEach((fn) => fn())
      cleanupFns.current = []
    }
  }, [])

  const enqueue = useCallback(async (config: PipelineConfig) => {
    await window.electronAPI.enqueue(config)
  }, [])

  const removeJob = useCallback(async (jobId: string) => {
    await window.electronAPI.removeJob(jobId)
  }, [])

  const requeueJob = useCallback(async (jobId: string) => {
    await window.electronAPI.requeueJob(jobId)
    // Clear runtime data for this job since it's restarting
    setState((prev) => {
      const { [jobId]: _, ...rest } = prev.jobRuntime
      return { ...prev, jobRuntime: rest }
    })
  }, [])

  const startQueue = useCallback(() => {
    window.electronAPI.startQueue()
  }, [])

  const stopCurrent = useCallback(() => {
    window.electronAPI.stopCurrent()
  }, [])

  const clearCompleted = useCallback(() => {
    window.electronAPI.clearCompleted()
    // Clear runtime data for non-existent jobs
    setState((prev) => {
      const activeIds = new Set(prev.jobs.filter((j) => j.status === 'queued' || j.status === 'running').map((j) => j.id))
      const cleaned: Record<string, JobRuntime> = {}
      for (const [id, rt] of Object.entries(prev.jobRuntime)) {
        if (activeIds.has(id)) cleaned[id] = rt
      }
      return { ...prev, jobRuntime: cleaned }
    })
  }, [])

  const clearAll = useCallback(() => {
    window.electronAPI.clearAll()
    setState({ jobs: [], jobRuntime: {} })
  }, [])

  const getRuntimeForJob = useCallback(
    (jobId: string): JobRuntime => {
      return state.jobRuntime[jobId] || { logs: [], stages: [], currentStage: null, sectionProgress: null }
    },
    [state.jobRuntime]
  )

  const runningJob = state.jobs.find((j) => j.status === 'running') || null
  const queuedCount = state.jobs.filter((j) => j.status === 'queued').length
  const hasCompleted = state.jobs.some((j) => j.status === 'completed' || j.status === 'error' || j.status === 'stopped')

  return {
    jobs: state.jobs,
    runningJob,
    queuedCount,
    hasCompleted,
    getRuntimeForJob,
    enqueue,
    startQueue,
    removeJob,
    requeueJob,
    stopCurrent,
    clearCompleted,
    clearAll
  }
}

function getRuntime(state: QueueState, jobId: string): JobRuntime {
  return state.jobRuntime[jobId] || { logs: [], stages: [], currentStage: null, sectionProgress: null }
}
