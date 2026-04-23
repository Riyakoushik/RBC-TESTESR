import { useState, useEffect, useCallback, useRef } from "react"

const API_BASE = "/api"

async function apiFetch<T>(path: string, opts?: RequestInit): Promise<T | null> {
  try {
    const res = await fetch(API_BASE + path, opts)
    if (!res.ok) return null
    return await res.json()
  } catch {
    return null
  }
}

export interface Stats {
  input_files: number
  output_files: number
  output_size_mb: number
  completed: number
  failed: number
  pending: number
  file_types: Record<string, number>
  knowledge: {
    total_embeddings?: number
    total_backlinks?: number
    total_tags?: number
    total_people?: number
    total_dates?: number
  }
}

export interface SystemStats {
  cpu_percent: number
  memory_percent: number
  memory_used_gb: number
  memory_total_gb: number
  disk_percent: number
  disk_used_gb: number
  disk_total_gb: number
}

export interface ProgressData {
  running: boolean
  total: number
  processed: number
  successful: number
  failed: number
  current_file: string
  started_at: number | null
  eta_seconds: number | null
  percent: number
}

export interface LogEntry {
  timestamp: string
  level: string
  message: string
}

export interface FileEntry {
  path: string
  name: string
  type: string
  status: string
  size_kb: number
}

export interface TimelineData {
  timeline: Record<string, string[]>
}

export interface GraphData {
  nodes: Array<{ id: string | number; label?: string; type?: string }>
  edges: Array<{ source: string | number; target: string | number }>
  stats: Record<string, number>
}

export function usePolling<T>(fetcher: () => Promise<T | null>, intervalMs: number) {
  const [data, setData] = useState<T | null>(null)
  const fetcherRef = useRef(fetcher)
  fetcherRef.current = fetcher

  const refresh = useCallback(async () => {
    const result = await fetcherRef.current()
    if (result !== null) setData(result)
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, intervalMs)
    return () => clearInterval(id)
  }, [refresh, intervalMs])

  return { data, refresh }
}

export function useStats() {
  return usePolling<Stats>(() => apiFetch("/stats"), 10000)
}

export function useSystemStats() {
  return usePolling<SystemStats>(() => apiFetch("/stats/system"), 5000)
}

export function useProgress() {
  return usePolling<ProgressData>(() => apiFetch("/progress"), 2000)
}

export function useLogs(level?: string) {
  const params = level ? `?level=${level}` : ""
  return usePolling<{ logs: LogEntry[] }>(() => apiFetch(`/logs${params}`), 3000)
}

export async function fetchFiles(status?: string, fileType?: string) {
  let params = "?limit=200"
  if (status) params += `&status=${status}`
  if (fileType) params += `&file_type=${fileType}`
  return apiFetch<{ total: number; files: FileEntry[] }>(`/files${params}`)
}

export async function fetchTimeline() {
  return apiFetch<TimelineData>("/timeline")
}

export async function fetchGraph() {
  return apiFetch<GraphData>("/graph")
}

export async function startConversion() {
  return apiFetch<{ status: string }>("/convert/start", { method: "POST" })
}

export async function stopConversion() {
  return apiFetch<{ status: string }>("/convert/stop", { method: "POST" })
}

export async function retryFailed() {
  return apiFetch<{ status: string; count?: number }>("/convert/retry", { method: "POST" })
}

export async function resetState() {
  return apiFetch<{ status: string }>("/convert/reset", { method: "POST" })
}
