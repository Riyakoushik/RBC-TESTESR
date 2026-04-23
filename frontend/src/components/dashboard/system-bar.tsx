import { cn } from "@/lib/utils"
import type { SystemStats } from "@/hooks/use-api"
import { Cpu, HardDrive, MemoryStick } from "lucide-react"

function MiniProgress({ value, label, icon: Icon }: { value: number; label: string; icon: React.ElementType }) {
  const color = value > 80 ? "bg-destructive" : value > 60 ? "bg-chart-3" : "bg-primary"
  return (
    <div className="flex items-center gap-3">
      <Icon className="h-4 w-4 text-muted-foreground" />
      <span className="text-xs font-medium uppercase text-muted-foreground w-12">{label}</span>
      <div className="w-24 h-1.5 rounded-full bg-secondary overflow-hidden">
        <div className={cn("h-full rounded-full transition-all duration-500", color)} style={{ width: `${value}%` }} />
      </div>
      <span className="text-xs font-semibold tabular-nums w-10 text-right">{value}%</span>
    </div>
  )
}

export function SystemBar({ data }: { data: SystemStats | null }) {
  if (!data) return null
  return (
    <div className="flex flex-wrap items-center gap-6 rounded-xl border border-border bg-card px-5 py-3">
      <MiniProgress value={data.cpu_percent} label="CPU" icon={Cpu} />
      <MiniProgress value={data.memory_percent} label="RAM" icon={MemoryStick} />
      <MiniProgress value={data.disk_percent} label="Disk" icon={HardDrive} />
      <div className="ml-auto text-xs text-muted-foreground hidden md:block">
        {data.memory_used_gb} / {data.memory_total_gb} GB RAM
      </div>
    </div>
  )
}
