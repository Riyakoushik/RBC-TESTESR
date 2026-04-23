import { useState } from "react"
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs"
import { SystemBar } from "@/components/dashboard/system-bar"
import { StatCards } from "@/components/dashboard/stat-cards"
import { FileTypesPanel } from "@/components/dashboard/file-types"
import { ConversionPanel } from "@/components/dashboard/conversion-panel"
import { LogsPanel } from "@/components/dashboard/logs-panel"
import { TimelinePanel } from "@/components/dashboard/timeline-panel"
import { GraphPanel } from "@/components/dashboard/graph-panel"
import { FilesPanel } from "@/components/dashboard/files-panel"
import { useStats, useSystemStats, useProgress, useLogs } from "@/hooks/use-api"
import { Zap } from "lucide-react"

export default function App() {
  const [logLevel, setLogLevel] = useState("")
  const { data: stats } = useStats()
  const { data: systemStats } = useSystemStats()
  const { data: progress, refresh: refreshProgress } = useProgress()
  const { data: logsData } = useLogs(logLevel || undefined)

  const fileTypes = stats ? Object.keys(stats.file_types) : []

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="sticky top-0 z-50 border-b border-border bg-card/80 backdrop-blur-sm">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          <div className="flex h-14 items-center gap-3">
            <Zap className="h-5 w-5 text-primary" />
            <div>
              <h1 className="text-base font-semibold tracking-tight">RBC-TESTER</h1>
              <p className="text-[10px] uppercase tracking-widest text-muted-foreground leading-none">
                Riya Built-in Commands and Memories
              </p>
            </div>
          </div>
        </div>
      </header>

      {/* Main */}
      <main className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-6 space-y-6">
        <SystemBar data={systemStats} />
        <StatCards data={stats} />
        <FileTypesPanel data={stats} />
        <ConversionPanel data={progress} onRefresh={refreshProgress} />

        {/* Tabbed Sections */}
        <Tabs defaultValue="logs">
          <TabsList className="w-full sm:w-auto">
            <TabsTrigger value="logs">Logs</TabsTrigger>
            <TabsTrigger value="timeline">Timeline</TabsTrigger>
            <TabsTrigger value="graph">Knowledge Graph</TabsTrigger>
            <TabsTrigger value="files">Files</TabsTrigger>
          </TabsList>

          <TabsContent value="logs">
            <LogsPanel
              logs={logsData?.logs ?? []}
              level={logLevel}
              onLevelChange={setLogLevel}
            />
          </TabsContent>

          <TabsContent value="timeline">
            <TimelinePanel />
          </TabsContent>

          <TabsContent value="graph">
            <GraphPanel />
          </TabsContent>

          <TabsContent value="files">
            <FilesPanel fileTypes={fileTypes} />
          </TabsContent>
        </Tabs>
      </main>

      {/* Footer */}
      <footer className="border-t border-border py-4 text-center text-xs text-muted-foreground">
        RBC-TESTER v1.0.0 — Document Conversion Pipeline
      </footer>
    </div>
  )
}
