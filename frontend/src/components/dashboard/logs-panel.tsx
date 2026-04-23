import { useRef, useEffect } from "react"
import { cn } from "@/lib/utils"
import { Select } from "@/components/ui/select"
import type { LogEntry } from "@/hooks/use-api"

const levelColors: Record<string, string> = {
  INFO: "text-chart-5",
  WARNING: "text-chart-3",
  ERROR: "text-destructive",
}

export function LogsPanel({
  logs,
  level,
  onLevelChange,
}: {
  logs: LogEntry[]
  level: string
  onLevelChange: (l: string) => void
}) {
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight
    }
  }, [logs])

  return (
    <div className="space-y-3">
      <Select value={level} onChange={(e) => onLevelChange(e.target.value)} className="w-36">
        <option value="">All Levels</option>
        <option value="INFO">INFO</option>
        <option value="WARNING">WARNING</option>
        <option value="ERROR">ERROR</option>
      </Select>

      <div
        ref={containerRef}
        className="h-[400px] overflow-y-auto rounded-lg border border-border bg-background p-3 font-mono text-xs leading-relaxed"
      >
        {logs.length === 0 ? (
          <p className="text-center text-muted-foreground py-8">No log entries yet. Start a conversion to see logs.</p>
        ) : (
          logs.map((log, i) => {
            const time = log.timestamp.split("T")[1]?.split(".")[0] ?? ""
            return (
              <div key={i} className="flex gap-3 py-0.5 border-b border-border/50 last:border-0">
                <span className="text-muted-foreground shrink-0">{time}</span>
                <span className={cn("font-semibold w-16 shrink-0", levelColors[log.level])}>{log.level}</span>
                <span className="break-all">{log.message}</span>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}
