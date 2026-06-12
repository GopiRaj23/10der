// Full tender search with filters, sorting and pagination.
import { useCallback, useEffect, useState } from 'react'
import { RotateCcw, SlidersHorizontal } from 'lucide-react'
import { api } from '../api/client'
import TenderTable from '../components/TenderTable'
import { Button, Card, Input, Label, Pagination, Select, useToast } from '../components/ui'
import { CATEGORIES, INDIAN_STATES } from '../constants'

const DEFAULT_FILTERS = {
  keyword: '', portal: '', state: '', category: '', closing_within_days: '',
  organisation: '', value_min: '', value_max: '', min_score: '', sort: 'relevance',
}

export default function Search() {
  const toast = useToast()
  const [filters, setFilters] = useState(DEFAULT_FILTERS)
  const [showAdvanced, setShowAdvanced] = useState(false)
  const [portals, setPortals] = useState([])
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [page, setPage] = useState(1)

  useEffect(() => {
    api.get('/portals').then(setPortals).catch(() => {})
  }, [])

  const load = useCallback(async (pageNum = 1, f = filters) => {
    setLoading(true)
    try {
      const res = await api.get('/tenders', { ...f, page: pageNum, page_size: 20 })
      setData(res)
      setPage(pageNum)
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setLoading(false)
    }
  }, [filters, toast])

  useEffect(() => { load(1, DEFAULT_FILTERS) }, []) // initial load

  const set = (k) => (e) => setFilters((f) => ({ ...f, [k]: e.target.value }))
  const submit = (e) => { e?.preventDefault(); load(1) }
  const reset = () => { setFilters(DEFAULT_FILTERS); load(1, DEFAULT_FILTERS) }

  const updateRow = (updated) =>
    setData((d) => ({ ...d, items: d.items.map((t) => (t.id === updated.id ? updated : t)) }))

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-navy">Search Tenders</h1>
        <p className="text-xs text-slate-500">Full-text search across all aggregated tenders ({data?.total ?? '…'} in scope)</p>
      </div>

      <Card className="p-4">
        <form onSubmit={submit} className="space-y-3">
          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-56 flex-1">
              <Label>Keyword</Label>
              <Input value={filters.keyword} onChange={set('keyword')} placeholder='e.g. drone, "thermal camera", surveillance' />
            </div>
            <div className="w-44">
              <Label>Portal</Label>
              <Select value={filters.portal} onChange={set('portal')}>
                <option value="">All portals</option>
                {portals.map((p) => <option key={p.code} value={p.code}>{p.name}</option>)}
              </Select>
            </div>
            <div className="w-40">
              <Label>Closing within</Label>
              <Select value={filters.closing_within_days} onChange={set('closing_within_days')}>
                <option value="">Any time</option>
                <option value="7">7 days</option>
                <option value="30">30 days</option>
                <option value="90">90 days</option>
              </Select>
            </div>
            <div className="w-40">
              <Label>Sort by</Label>
              <Select value={filters.sort} onChange={set('sort')}>
                <option value="relevance">Relevance score</option>
                <option value="closing">Closing date (nearest)</option>
                <option value="published">Published (latest)</option>
              </Select>
            </div>
            <Button type="submit">Search</Button>
            <Button type="button" variant="ghost" size="sm" onClick={() => setShowAdvanced(!showAdvanced)}>
              <SlidersHorizontal className="h-3.5 w-3.5" /> Filters
            </Button>
            <Button type="button" variant="ghost" size="sm" onClick={reset} title="Reset filters">
              <RotateCcw className="h-3.5 w-3.5" />
            </Button>
          </div>

          {showAdvanced && (
            <div className="flex flex-wrap items-end gap-3 border-t border-slate-100 pt-3">
              <div className="w-44">
                <Label>State / UT</Label>
                <Select value={filters.state} onChange={set('state')}>
                  <option value="">All states</option>
                  {INDIAN_STATES.map((s) => <option key={s} value={s}>{s}</option>)}
                </Select>
              </div>
              <div className="w-36">
                <Label>Category</Label>
                <Select value={filters.category} onChange={set('category')}>
                  <option value="">All</option>
                  {CATEGORIES.map((c) => <option key={c.value} value={c.value}>{c.label}</option>)}
                </Select>
              </div>
              <div className="min-w-44 flex-1">
                <Label>Organisation</Label>
                <Input value={filters.organisation} onChange={set('organisation')} placeholder="e.g. DRDO, Police" />
              </div>
              <div className="w-32">
                <Label>Min value (₹)</Label>
                <Input type="number" min="0" value={filters.value_min} onChange={set('value_min')} />
              </div>
              <div className="w-32">
                <Label>Max value (₹)</Label>
                <Input type="number" min="0" value={filters.value_max} onChange={set('value_max')} />
              </div>
              <div className="w-32">
                <Label>Min score</Label>
                <Input type="number" min="0" max="100" value={filters.min_score} onChange={set('min_score')} />
              </div>
            </div>
          )}
        </form>
      </Card>

      <Card>
        <TenderTable items={data?.items} loading={loading} onUpdated={updateRow} />
        {data && <Pagination page={page} pageSize={data.page_size} total={data.total} onPage={(p) => load(p)} />}
      </Card>
    </div>
  )
}
