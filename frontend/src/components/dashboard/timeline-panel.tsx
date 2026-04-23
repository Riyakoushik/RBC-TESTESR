import { useState, useEffect } from "react"
import { fetchTimeline } from "@/hooks/use-api"
import { CalendarDays, FileText } from "lucide-react"

export function TimelinePanel() {
  const [timeline, setTimeline] = useState<Record<string, string[]>>({})
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchTimeline().then((data) => {
      if (data?.timeline) setTimeline(data.timeline)
      setLoading(false)
    })
  }, [])

  const dates = Object.keys(timeline).sort().reverse()

  if (loading) {
    return <p className="text-center text-muted-foreground py-8">Loading timeline...</p>
  }

  if (dates.length === 0) {
    return (
      <p className="text-center text-muted-foreground py-8">
        No timeline data yet. Run a conversion to generate timeline entries.
      </p>
    )
  }

  return (
    <div className="h-[400px] overflow-y-auto space-y-1 pr-2">
      {dates.map((date) => {
        const files = timeline[date] ?? []
        return (
          <div key={date} className="flex gap-4 py-3 border-b border-border/50 last:border-0">
            <div className="flex items-start gap-2 shrink-0 w-32">
              <CalendarDays className="h-4 w-4 text-primary mt-0.5" />
              <span className="text-sm font-semibold text-primary">{date}</span>
            </div>
            <ul className="space-y-0.5">
              {files.map((f, i) => {
                const name = f.split("/").pop() ?? f
                return (
                  <li key={i} className="flex items-center gap-1.5 text-sm text-muted-foreground">
                    <FileText className="h-3 w-3 shrink-0" />
                    <span className="truncate">{name}</span>
                  </li>
                )
              })}
            </ul>
          </div>
        )
      })}
    </div>
  )
}
