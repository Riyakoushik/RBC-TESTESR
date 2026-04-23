import { useState, useEffect } from "react"
import { Badge } from "@/components/ui/badge"
import { Select } from "@/components/ui/select"
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from "@/components/ui/table"
import { fetchFiles, type FileEntry } from "@/hooks/use-api"

const statusVariants: Record<string, "default" | "secondary" | "destructive"> = {
  completed: "default",
  pending: "secondary",
  failed: "destructive",
}

export function FilesPanel({ fileTypes }: { fileTypes: string[] }) {
  const [files, setFiles] = useState<FileEntry[]>([])
  const [total, setTotal] = useState(0)
  const [statusFilter, setStatusFilter] = useState("")
  const [typeFilter, setTypeFilter] = useState("")

  useEffect(() => {
    fetchFiles(statusFilter || undefined, typeFilter || undefined).then((data) => {
      if (data) {
        setFiles(data.files)
        setTotal(data.total)
      }
    })
  }, [statusFilter, typeFilter])

  return (
    <div className="space-y-3">
      <div className="flex gap-3">
        <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="w-36">
          <option value="">All Status</option>
          <option value="pending">Pending</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
        </Select>
        <Select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} className="w-36">
          <option value="">All Types</option>
          {fileTypes.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </Select>
        <span className="text-sm text-muted-foreground self-center ml-auto">{total} files</span>
      </div>

      <div className="h-[400px] overflow-y-auto rounded-lg border border-border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Size</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {files.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} className="text-center text-muted-foreground py-8">
                  No files found.
                </TableCell>
              </TableRow>
            ) : (
              files.map((file) => (
                <TableRow key={file.path}>
                  <TableCell className="font-medium truncate max-w-[300px]" title={file.path}>
                    {file.name}
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary" className="text-xs">{file.type}</Badge>
                  </TableCell>
                  <TableCell className="tabular-nums text-muted-foreground">{file.size_kb} KB</TableCell>
                  <TableCell>
                    <Badge variant={statusVariants[file.status] ?? "secondary"}>{file.status}</Badge>
                  </TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </div>
    </div>
  )
}
