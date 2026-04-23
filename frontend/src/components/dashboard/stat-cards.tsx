import { Card, CardContent } from "@/components/ui/card"
import type { Stats } from "@/hooks/use-api"
import {
  FileInput, FileOutput, CheckCircle2, XCircle, Clock, Database,
  Link2, Tag, Users, CalendarDays
} from "lucide-react"

interface StatCardProps {
  label: string
  value: string | number
  icon: React.ElementType
  accent?: string
}

function StatCard({ label, value, icon: Icon, accent = "text-primary" }: StatCardProps) {
  return (
    <Card>
      <CardContent className="p-4">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-xs font-medium uppercase text-muted-foreground">{label}</p>
            <p className={`text-2xl font-bold tabular-nums ${accent}`}>{value}</p>
          </div>
          <Icon className={`h-8 w-8 ${accent} opacity-40`} />
        </div>
      </CardContent>
    </Card>
  )
}

export function StatCards({ data }: { data: Stats | null }) {
  if (!data) return null

  const k = data.knowledge ?? {}

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <StatCard label="Input Files" value={data.input_files} icon={FileInput} />
        <StatCard label="Output Files" value={data.output_files} icon={FileOutput} />
        <StatCard label="Completed" value={data.completed} icon={CheckCircle2} accent="text-chart-2" />
        <StatCard label="Failed" value={data.failed} icon={XCircle} accent="text-destructive" />
        <StatCard label="Pending" value={data.pending} icon={Clock} accent="text-chart-3" />
        <StatCard label="Output (MB)" value={data.output_size_mb} icon={Database} />
      </div>
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
        <StatCard label="Embeddings" value={k.total_embeddings ?? 0} icon={Database} accent="text-chart-5" />
        <StatCard label="Backlinks" value={k.total_backlinks ?? 0} icon={Link2} accent="text-chart-5" />
        <StatCard label="Tags" value={k.total_tags ?? 0} icon={Tag} accent="text-chart-5" />
        <StatCard label="People" value={k.total_people ?? 0} icon={Users} accent="text-chart-5" />
        <StatCard label="Dates" value={k.total_dates ?? 0} icon={CalendarDays} accent="text-chart-5" />
      </div>
    </div>
  )
}
