import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Progress } from "@/components/ui/progress"
import type { ProgressData } from "@/hooks/use-api"
import { startConversion, stopConversion, retryFailed, resetState } from "@/hooks/use-api"
import { Play, Square, RotateCcw, Trash2, Loader2 } from "lucide-react"

export function ConversionPanel({ data, onRefresh }: { data: ProgressData | null; onRefresh: () => void }) {
  const running = data?.running ?? false

  const handleStart = async () => {
    await startConversion()
    onRefresh()
  }
  const handleStop = async () => {
    await stopConversion()
    onRefresh()
  }
  const handleRetry = async () => {
    await retryFailed()
    onRefresh()
  }
  const handleReset = async () => {
    if (confirm("Reset all conversion tracking? Output files will not be deleted.")) {
      await resetState()
      onRefresh()
    }
  }

  const computedPercent = data?.percent || (data && data.total > 0 ? Math.round((data.processed / data.total) * 1000) / 10 : 0)

  const eta = data?.eta_seconds
    ? `ETA: ${Math.floor(data.eta_seconds / 60)}m ${data.eta_seconds % 60}s`
    : ""

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="text-sm font-medium">Conversion</CardTitle>
          <div className="flex gap-2">
            <Button size="sm" onClick={handleStart} disabled={running} className="gap-1.5">
              <Play className="h-3.5 w-3.5" /> Start
            </Button>
            <Button size="sm" variant="destructive" onClick={handleStop} disabled={!running} className="gap-1.5">
              <Square className="h-3.5 w-3.5" /> Stop
            </Button>
            <Button size="sm" variant="outline" onClick={handleRetry} disabled={running} className="gap-1.5">
              <RotateCcw className="h-3.5 w-3.5" /> Retry
            </Button>
            <Button size="sm" variant="ghost" onClick={handleReset} disabled={running} className="gap-1.5">
              <Trash2 className="h-3.5 w-3.5" /> Reset
            </Button>
          </div>
        </div>
      </CardHeader>
      {(running || (data && data.processed > 0)) && (
        <CardContent>
          <div className="space-y-2">
            <div className="flex items-center justify-between text-sm">
              <span className="tabular-nums text-muted-foreground">
                {data?.processed ?? 0} / {data?.total ?? 0} files
              </span>
              <span className="tabular-nums font-medium">{computedPercent}%</span>
              {eta && <span className="text-xs text-muted-foreground">{eta}</span>}
            </div>
            <Progress value={computedPercent} />
            {running && data?.current_file && (
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Loader2 className="h-3 w-3 animate-spin" />
                <span className="truncate">{data.current_file}</span>
              </div>
            )}
            {!running && data && data.processed > 0 && (
              <p className="text-xs text-chart-2">
                Conversion complete — {data.successful} succeeded, {data.failed} failed
              </p>
            )}
          </div>
        </CardContent>
      )}
    </Card>
  )
}
