import { useState, useEffect, useRef, useCallback } from "react"
import { fetchGraph, type GraphData } from "@/hooks/use-api"

const NODE_COLORS: Record<string, string> = {
  file: "#8b5cf6",
  tag: "#22c55e",
  person: "#eab308",
  unknown: "#60a5fa",
}

export function GraphPanel() {
  const [graphData, setGraphData] = useState<GraphData | null>(null)
  const [loading, setLoading] = useState(true)
  const canvasRef = useRef<HTMLCanvasElement>(null)

  useEffect(() => {
    fetchGraph().then((data) => {
      if (data) setGraphData(data)
      setLoading(false)
    })
  }, [])

  const draw = useCallback(() => {
    const canvas = canvasRef.current
    if (!canvas || !graphData) return

    const ctx = canvas.getContext("2d")
    if (!ctx) return

    const rect = canvas.parentElement?.getBoundingClientRect()
    if (!rect) return

    canvas.width = rect.width
    canvas.height = rect.height

    ctx.clearRect(0, 0, canvas.width, canvas.height)

    const { nodes, edges } = graphData

    if (nodes.length === 0) {
      ctx.fillStyle = "#8b8fa3"
      ctx.font = "14px sans-serif"
      ctx.textAlign = "center"
      ctx.fillText("No graph data yet. Run a conversion to build the knowledge graph.", canvas.width / 2, canvas.height / 2)
      return
    }

    const cx = canvas.width / 2
    const cy = canvas.height / 2
    const radius = Math.min(cx, cy) * 0.75

    const positions: Record<string | number, { x: number; y: number }> = {}
    nodes.forEach((node, i) => {
      const angle = (2 * Math.PI * i) / nodes.length
      positions[node.id] = {
        x: cx + radius * Math.cos(angle) + (Math.random() - 0.5) * 20,
        y: cy + radius * Math.sin(angle) + (Math.random() - 0.5) * 20,
      }
    })

    // Edges
    ctx.strokeStyle = "rgba(139, 92, 246, 0.2)"
    ctx.lineWidth = 1
    for (const edge of edges) {
      const from = positions[edge.source]
      const to = positions[edge.target]
      if (from && to) {
        ctx.beginPath()
        ctx.moveTo(from.x, from.y)
        ctx.lineTo(to.x, to.y)
        ctx.stroke()
      }
    }

    // Nodes
    for (const node of nodes) {
      const pos = positions[node.id]
      if (!pos) continue
      const color = NODE_COLORS[node.type ?? "unknown"] ?? NODE_COLORS.unknown
      const r = node.type === "file" ? 5 : 4

      ctx.beginPath()
      ctx.arc(pos.x, pos.y, r, 0, 2 * Math.PI)
      ctx.fillStyle = color
      ctx.fill()

      if (nodes.length < 50) {
        ctx.fillStyle = "#e4e6f0"
        ctx.font = "10px sans-serif"
        ctx.textAlign = "center"
        const label = (node.label ?? "").slice(0, 15) + ((node.label?.length ?? 0) > 15 ? "..." : "")
        ctx.fillText(label, pos.x, pos.y - 8)
      }
    }
  }, [graphData])

  useEffect(() => {
    draw()
    const handleResize = () => draw()
    window.addEventListener("resize", handleResize)
    return () => window.removeEventListener("resize", handleResize)
  }, [draw])

  if (loading) {
    return <p className="text-center text-muted-foreground py-8">Loading knowledge graph...</p>
  }

  const stats = graphData?.stats ?? {}

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-4 text-sm">
        <span className="text-muted-foreground">Nodes: <strong className="text-primary">{stats.total_nodes ?? 0}</strong></span>
        <span className="text-muted-foreground">Edges: <strong className="text-primary">{stats.total_edges ?? 0}</strong></span>
        <span className="text-muted-foreground">Files: <strong className="text-chart-1">{stats.file_nodes ?? 0}</strong></span>
        <span className="text-muted-foreground">Tags: <strong className="text-chart-2">{stats.tag_nodes ?? 0}</strong></span>
        <span className="text-muted-foreground">People: <strong className="text-chart-3">{stats.person_nodes ?? 0}</strong></span>
      </div>
      <div className="h-[400px] rounded-lg border border-border bg-background overflow-hidden">
        <canvas ref={canvasRef} className="w-full h-full" />
      </div>
    </div>
  )
}
