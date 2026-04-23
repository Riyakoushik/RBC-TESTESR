import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import type { Stats } from "@/hooks/use-api"

export function FileTypesPanel({ data }: { data: Stats | null }) {
  if (!data || !data.file_types) return null

  const entries = Object.entries(data.file_types).sort(([, a], [, b]) => b - a)
  if (entries.length === 0) return null

  return (
    <Card>
      <CardHeader className="pb-3">
        <CardTitle className="text-sm font-medium">File Type Breakdown</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-wrap gap-2">
          {entries.map(([type, count]) => (
            <Badge key={type} variant="secondary" className="gap-1.5">
              {type}
              <span className="text-primary font-bold">{count}</span>
            </Badge>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
