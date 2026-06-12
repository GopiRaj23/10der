// Report generation (daily / weekly / custom; PDF / CSV / XLSX) + history.
import { useEffect, useState } from 'react'
import { Download, FileText } from 'lucide-react'
import { api, fmtDate, fmtDateTime } from '../api/client'
import {
  Badge, Button, Card, CardHeader, EmptyState, Input, Label, Select,
  TableSkeleton, useToast,
} from '../components/ui'
import { useAuth } from '../context/AuthContext'

export default function Reports() {
  const { user, refreshUser } = useAuth()
  const toast = useToast()
  const [reports, setReports] = useState(null)
  const [portals, setPortals] = useState([])
  const [busy, setBusy] = useState(false)
  const [form, setForm] = useState({
    report_type: 'daily', file_format: 'pdf', date_from: '', date_to: '',
    portal_code: '', min_score: '',
  })

  const load = () => api.get('/reports').then(setReports).catch((e) => toast(e.message, 'error'))
  useEffect(() => {
    load()
    api.get('/portals').then(setPortals).catch(() => {})
  }, [])

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const generate = async (e) => {
    e.preventDefault()
    setBusy(true)
    try {
      const payload = {
        report_type: form.report_type,
        file_format: form.file_format,
        date_from: form.report_type === 'custom' && form.date_from ? form.date_from : null,
        date_to: form.report_type === 'custom' && form.date_to ? form.date_to : null,
        portal_code: form.portal_code || null,
        min_score: form.min_score ? Number(form.min_score) : null,
      }
      const report = await api.post('/reports/generate', payload)
      toast(`Report generated — ${report.tender_count} tenders included`)
      load()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  const download = async (r) => {
    try {
      await api.download(`/reports/${r.id}/download`, `tenderradar_${r.report_type}_${r.id}.${r.file_format}`)
    } catch (err) {
      toast(err.message, 'error')
    }
  }

  const toggleWeekly = async () => {
    try {
      await api.put('/users/me', { weekly_report_enabled: !user.weekly_report_enabled })
      await refreshUser()
      toast(user.weekly_report_enabled ? 'Weekly auto-report disabled' : 'Weekly report will be emailed every Monday 8 AM IST')
    } catch (err) {
      toast(err.message, 'error')
    }
  }

  const typeLabel = { daily: 'Daily Summary', weekly: 'Weekly Intelligence', custom: 'Custom' }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-navy">Reports</h1>
        <p className="text-xs text-slate-500">Generate PDF / Excel tender intelligence reports on demand</p>
      </div>

      <Card className="p-4">
        <form onSubmit={generate} className="flex flex-wrap items-end gap-3">
          <div className="w-48">
            <Label>Report type</Label>
            <Select value={form.report_type} onChange={set('report_type')}>
              <option value="daily">Daily Summary (today)</option>
              <option value="weekly">Weekly Intelligence (7 days)</option>
              <option value="custom">Custom range</option>
            </Select>
          </div>
          {form.report_type === 'custom' && (
            <>
              <div className="w-40">
                <Label>From</Label>
                <Input type="date" value={form.date_from} onChange={set('date_from')} />
              </div>
              <div className="w-40">
                <Label>To</Label>
                <Input type="date" value={form.date_to} onChange={set('date_to')} />
              </div>
            </>
          )}
          <div className="w-32">
            <Label>Format</Label>
            <Select value={form.file_format} onChange={set('file_format')}>
              <option value="pdf">PDF</option>
              <option value="csv">CSV</option>
              <option value="xlsx">Excel</option>
            </Select>
          </div>
          <div className="w-44">
            <Label>Portal (optional)</Label>
            <Select value={form.portal_code} onChange={set('portal_code')}>
              <option value="">All portals</option>
              {portals.map((p) => <option key={p.code} value={p.code}>{p.name}</option>)}
            </Select>
          </div>
          <div className="w-28">
            <Label>Min score</Label>
            <Input type="number" min="0" max="100" value={form.min_score} onChange={set('min_score')} placeholder="any" />
          </div>
          <Button type="submit" disabled={busy}>{busy ? 'Generating…' : 'Generate report'}</Button>
        </form>
        <div className="mt-3 flex items-center gap-2 border-t border-slate-100 pt-3 text-xs text-slate-600">
          <input type="checkbox" checked={!!user?.weekly_report_enabled} onChange={toggleWeekly} className="accent-teal cursor-pointer" id="weekly" />
          <label htmlFor="weekly" className="cursor-pointer">
            Email me the <b>Weekly Intelligence Report</b> automatically every Monday at 8:00 AM IST
          </label>
        </div>
      </Card>

      <Card>
        <CardHeader title="Generated reports" subtitle="Last 50 reports, newest first" />
        {!reports ? (
          <TableSkeleton rows={4} />
        ) : reports.length === 0 ? (
          <EmptyState icon={FileText} title="No reports yet"
            message="Generate your first report above — daily summary, weekly intelligence or a custom range." />
        ) : (
          <div className="divide-y divide-slate-100">
            {reports.map((r) => (
              <div key={r.id} className="flex flex-wrap items-center gap-3 px-5 py-3">
                <FileText className="h-4.5 w-4.5 text-teal" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-navy">
                    {typeLabel[r.report_type]} Report
                    <Badge className="ml-2">{r.file_format.toUpperCase()}</Badge>
                  </p>
                  <p className="text-[11px] text-slate-400">
                    {fmtDate(r.date_range_start)} → {fmtDate(r.date_range_end)} · {r.tender_count} tenders · generated {fmtDateTime(r.generated_at)}
                  </p>
                </div>
                <Button variant="secondary" size="sm" onClick={() => download(r)}>
                  <Download className="h-3.5 w-3.5" /> Download
                </Button>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}
