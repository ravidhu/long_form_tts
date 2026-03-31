import { useState } from 'react'
import { ConfigPanel } from '@/components/ConfigPanel'
import { QueuePanel } from '@/components/QueuePanel'
import { SetupWizard } from '@/components/SetupWizard'
import { useQueue } from '@/hooks/useQueue'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/ui/tabs'

export default function App() {
  const [setupDone, setSetupDone] = useState(false)
  const queue = useQueue()

  if (!setupDone) {
    return <SetupWizard onComplete={() => setSetupDone(true)} />
  }

  const runningCount = queue.jobs.filter((j) => j.status === 'running').length
  const queuedCount = queue.jobs.filter((j) => j.status === 'queued').length
  const jobsBadge = runningCount + queuedCount

  return (
    <div className="h-screen flex flex-col">
      {/* Titlebar drag region */}
      <div className="titlebar-drag h-12 flex-shrink-0 flex items-center justify-center border-b bg-background/80 backdrop-blur">
        <h1 className="text-sm font-semibold text-muted-foreground">Long Form TTS</h1>
      </div>

      {/* Tab layout */}
      <Tabs defaultValue="config" className="flex-1 flex flex-col overflow-hidden">
        <div className="flex justify-center border-b px-4 py-2">
          <TabsList>
            <TabsTrigger value="config">Configuration</TabsTrigger>
            <TabsTrigger value="queue" className="gap-1.5">
              Queue
              {jobsBadge > 0 && (
                <span className="inline-flex items-center justify-center rounded-full bg-primary text-primary-foreground text-[10px] font-medium h-4 min-w-4 px-1">
                  {jobsBadge}
                </span>
              )}
            </TabsTrigger>
          </TabsList>
        </div>

        <TabsContent value="config" className="flex-1 overflow-y-auto mt-0">
          <div className="max-w-2xl mx-auto p-6">
            <ConfigPanel onEnqueue={queue.enqueue} />
          </div>
        </TabsContent>

        <TabsContent value="queue" className="flex-1 overflow-y-auto mt-0">
          <div className="max-w-2xl mx-auto p-6">
            <QueuePanel
              jobs={queue.jobs}
              getRuntimeForJob={queue.getRuntimeForJob}
              onStart={queue.startQueue}
              onRemove={queue.removeJob}
              onRequeue={queue.requeueJob}
              onStopCurrent={queue.stopCurrent}
              onClearCompleted={queue.clearCompleted}
              onClearAll={queue.clearAll}
            />
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
