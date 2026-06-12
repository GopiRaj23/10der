// Admin panel: user management, scraper control + logs, keyword blacklist,
// system health and usage analytics. Superadmin only.
import { useEffect, useState } from 'react'
import { Activity, Ban, Play, RefreshCw, Users } from 'lucide-react'
import { api, fmtDateTime } from '../../api/client'
import {
  Badge, Button, Card, CardHeader, cn, EmptyState, Input, Select, Switch,
  TableSkeleton, Tabs, useToast,
} from '../../components/ui'
import { useAuth } from '../../context/AuthContext'

const TABS = [
  { value: 'users', label: 'Users' },
  { value: 'scrapers', label: 'Scrapers' },
  { value: 'health', label: 'System health' },
  { value: 'usage', label: 'Usage analytics' },
  { value: 'blacklist', label: 'Keyword blacklist' },
]

const STATUS_BADGE = {
  success: 'green', partial: 'amber', failed: 'red', skipped: 'slate', running: 'teal',
}

function UsersTab() {
  const toast = useToast()
  const [data, setData] = useState(null)
  const [q, setQ] = useState('')

  const load = (query = q) => api.get('/admin/users', { q: query }).then(setData).catch((e) => toast(e.message, 'error'))
  useEffect(() => { load('') }, [])

  const update = async (u, patch) => {
    try {
      await api.put(`/admin/users/${u.id}`, patch)
      toast(`Updated ${u.email}`)
      load()
    } catch (e) {
      toast(e.message, 'error')
    }
  }

  return (
    <Card>
      <CardHeader
        title={`All users ${data ? `(${data.total})` : ''}`}
        action={
          <form onSubmit={(e) => { e.preventDefault(); load() }}>
            <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search email/company…" className="w-56" />
          </form>
        }
      />
      {!data ? <TableSkeleton /> : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-160 text-left text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-[10px] uppercase text-slate-400">
                <th className="px-4 py-2.5">User</th>
                <th className="px-2 py-2.5">Keywords</th>
                <th className="px-2 py-2.5">Tier</th>
                <th className="px-2 py-2.5">Verified</th>
                <th className="px-2 py-2.5">Last login</th>
                <th className="px-2 py-2.5">Enabled</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((u) => (
                <tr key={u.id} className="border-b border-slate-100">
                  <td className="px-4 py-2.5">
                    <p className="font-medium text-navy">{u.email}</p>
                    <p className="text-[10px] text-slate-400">{u.company_name || '—'} {u.role === 'superadmin' && <Badge color="purple">ADMIN</Badge>}</p>
                  </td>
                  <td className="px-2 py-2.5">{u.keyword_count}</td>
                  <td className="px-2 py-2.5">
                    <Select value={u.tier} onChange={(e) => update(u, { tier: e.target.value })} className="w-22 py-1 text-[11px]">
                      <option value="free">free</option>
                      <option value="pro">pro</option>
                    </Select>
                  </td>
                  <td className="px-2 py-2.5">{u.is_verified ? '✅' : '—'}</td>
                  <td className="px-2 py-2.5 text-slate-500">{u.last_login_at ? fmtDateTime(u.last_login_at) : 'never'}</td>
                  <td className="px-2 py-2.5">
                    <Switch checked={u.is_active} onChange={(v) => update(u, { is_active: v })} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  )
}

function ScrapersTab() {
  const toast = useToast()
  const [portals, setPortals] = useState(null)
  const [logs, setLogs] = useState(null)

  const load = () => {
    api.get('/portals/status').then(setPortals).catch((e) => toast(e.message, 'error'))
    api.get('/scrape/logs', { limit: 30 }).then(setLogs).catch(() => {})
  }
  useEffect(load, [])

  const trigger = async (code) => {
    try {
      const res = await api.post('/scrape/trigger', { portal_code: code })
      toast(res.message)
      setTimeout(load, 2500)
    } catch (e) {
      toast(e.message, 'error')
    }
  }

  const togglePortal = async (p) => {
    try {
      await api.put(`/admin/portals/${p.id}?is_active=${!p.is_active}`)
      load()
    } catch (e) {
      toast(e.message, 'error')
    }
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader
          title="Portal scrapers"
          subtitle="Health per portal — trigger manual runs, enable/disable"
          action={
            <Button size="sm" onClick={() => trigger(null)}>
              <Play className="h-3.5 w-3.5" /> Scrape all portals
            </Button>
          }
        />
        {!portals ? <TableSkeleton /> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-180 text-left text-xs">
              <thead>
                <tr className="border-b border-slate-200 text-[10px] uppercase text-slate-400">
                  <th className="px-4 py-2.5">Portal</th>
                  <th className="px-2 py-2.5">Engine</th>
                  <th className="px-2 py-2.5">Last run</th>
                  <th className="px-2 py-2.5">Status</th>
                  <th className="px-2 py-2.5">Found / New</th>
                  <th className="px-2 py-2.5">Active</th>
                  <th className="px-2 py-2.5" />
                </tr>
              </thead>
              <tbody>
                {portals.map((p) => (
                  <tr key={p.id} className={cn('border-b border-slate-100', !p.is_active && 'opacity-50')}>
                    <td className="px-4 py-2.5">
                      <p className="font-medium text-navy">{p.name}</p>
                      <p className="text-[10px] text-slate-400">{p.base_url} {p.tier_required === 'free' && <Badge color="teal">FREE TIER</Badge>}</p>
                    </td>
                    <td className="px-2 py-2.5"><Badge>{p.scraper_type}</Badge></td>
                    <td className="px-2 py-2.5 text-slate-500">{p.last_scraped_at ? fmtDateTime(p.last_scraped_at) : 'never'}</td>
                    <td className="px-2 py-2.5">
                      {p.last_status ? <Badge color={STATUS_BADGE[p.last_status]}>{p.last_status}</Badge> : '—'}
                      {p.last_error && <p className="mt-0.5 max-w-44 truncate text-[10px] text-red-500" title={p.last_error}>{p.last_error}</p>}
                    </td>
                    <td className="px-2 py-2.5 text-slate-600">
                      {p.last_records_found ?? '—'} / {p.last_records_new ?? '—'}
                      {p.last_duration_seconds != null && <span className="text-[10px] text-slate-400"> · {p.last_duration_seconds}s</span>}
                    </td>
                    <td className="px-2 py-2.5"><Switch checked={p.is_active} onChange={() => togglePortal(p)} /></td>
                    <td className="px-2 py-2.5">
                      <Button variant="secondary" size="sm" onClick={() => trigger(p.code)} disabled={!p.is_active}>
                        <RefreshCw className="h-3 w-3" /> Run
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      <Card>
        <CardHeader title="Recent scrape logs" action={<Button variant="ghost" size="sm" onClick={load}><RefreshCw className="h-3.5 w-3.5" /></Button>} />
        {!logs ? <TableSkeleton rows={4} /> : logs.length === 0 ? (
          <EmptyState icon={Activity} title="No scrape runs yet" message="Trigger a scrape above to see logs." />
        ) : (
          <div className="max-h-80 divide-y divide-slate-100 overflow-y-auto">
            {logs.map((l) => (
              <div key={l.id} className="flex items-center gap-3 px-5 py-2 text-xs">
                <Badge color={STATUS_BADGE[l.status] || 'slate'}>{l.status}</Badge>
                <span className="font-medium text-navy">{l.portal_name}</span>
                <span className="text-slate-400">{fmtDateTime(l.run_at)}</span>
                <span className="text-slate-500">{l.records_found} found · {l.records_new} new</span>
                <span className="ml-auto text-[10px] text-slate-400">{l.triggered_by}{l.duration_seconds != null && ` · ${l.duration_seconds}s`}</span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  )
}

function HealthTab() {
  const [health, setHealth] = useState(null)
  useEffect(() => { api.get('/admin/system-health').then(setHealth).catch(() => {}) }, [])
  if (!health) return <TableSkeleton />
  const cards = [
    ['Database size', health.db_size, health.db_dialect],
    ['Cache backend', health.cache_backend, `queue depth ${health.redis_queue_depth}`],
    ['Tenders stored', health.tenders_total, 'active (non-archived)'],
    ['Registered users', health.users_total, health.demo_mode ? 'DEMO MODE ON' : 'live mode'],
  ]
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {cards.map(([label, value, hint]) => (
          <Card key={label} className="p-4">
            <p className="text-xl font-bold text-navy">{value}</p>
            <p className="text-xs font-medium text-slate-500">{label}</p>
            <p className="text-[10px] text-slate-400">{hint}</p>
          </Card>
        ))}
      </div>
      <Card>
        <CardHeader title="Per-portal error rate (7 days)" />
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-slate-200 text-[10px] uppercase text-slate-400">
                <th className="px-4 py-2.5">Portal</th><th className="px-2 py-2.5">Last scraped</th>
                <th className="px-2 py-2.5">Runs</th><th className="px-2 py-2.5">Failed</th><th className="px-2 py-2.5">Error rate</th>
              </tr>
            </thead>
            <tbody>
              {health.portals.map((p) => (
                <tr key={p.code} className="border-b border-slate-100">
                  <td className="px-4 py-2">{p.name}</td>
                  <td className="px-2 py-2 text-slate-500">{p.last_scraped_at ? fmtDateTime(p.last_scraped_at) : 'never'}</td>
                  <td className="px-2 py-2">{p.runs_7d}</td>
                  <td className="px-2 py-2">{p.failed_7d}</td>
                  <td className="px-2 py-2">
                    <span className={cn('font-semibold', p.error_rate > 50 ? 'text-red-600' : p.error_rate > 10 ? 'text-amber-600' : 'text-emerald-600')}>
                      {p.error_rate}%
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}

function UsageTab() {
  const [usage, setUsage] = useState(null)
  useEffect(() => { api.get('/admin/usage').then(setUsage).catch(() => {}) }, [])
  if (!usage) return <TableSkeleton />
  return (
    <div className="grid gap-4 lg:grid-cols-3">
      <Card className="p-5 text-center">
        <p className="text-3xl font-bold text-navy">{usage.dau}</p>
        <p className="text-xs text-slate-500">Daily active users (today)</p>
        <div className="mt-3 flex justify-center gap-2 text-[11px]">
          <Badge>free: {usage.tiers.free || 0}</Badge>
          <Badge color="teal">pro: {usage.tiers.pro || 0}</Badge>
        </div>
      </Card>
      <Card>
        <CardHeader title="Top keywords (global)" />
        <div className="divide-y divide-slate-100">
          {usage.top_keywords.map((k) => (
            <div key={k.keyword} className="flex justify-between px-5 py-2 text-xs">
              <span className="font-mono text-navy">{k.keyword}</span>
              <span className="text-slate-400">{k.users} use{k.users === 1 ? '' : 's'}</span>
            </div>
          ))}
          {!usage.top_keywords.length && <p className="px-5 py-6 text-center text-xs text-slate-400">No keywords yet</p>}
        </div>
      </Card>
      <Card>
        <CardHeader title="Most active portals" />
        <div className="divide-y divide-slate-100">
          {usage.most_active_portals.map((p) => (
            <div key={p.portal} className="flex justify-between px-5 py-2 text-xs">
              <span className="max-w-44 truncate text-navy">{p.portal}</span>
              <span className="text-slate-400">{p.tenders} tenders</span>
            </div>
          ))}
          {!usage.most_active_portals.length && <p className="px-5 py-6 text-center text-xs text-slate-400">No tenders yet</p>}
        </div>
      </Card>
    </div>
  )
}

function BlacklistTab() {
  const toast = useToast()
  const [items, setItems] = useState(null)
  const [term, setTerm] = useState('')
  const [reason, setReason] = useState('')

  const load = () => api.get('/admin/blacklist').then(setItems).catch(() => {})
  useEffect(load, [])

  const add = async (e) => {
    e.preventDefault()
    try {
      await api.post('/admin/blacklist', { term, reason: reason || null })
      toast(`Blocked keyword "${term}"`)
      setTerm(''); setReason('')
      load()
    } catch (err) {
      toast(err.message, 'error')
    }
  }

  const remove = async (item) => {
    await api.del(`/admin/blacklist/${item.id}`)
    toast(`Unblocked "${item.term}"`)
    load()
  }

  return (
    <Card>
      <CardHeader title="Keyword blacklist" subtitle="Users cannot save these terms as keywords (spam prevention)" />
      <div className="p-5">
        <form onSubmit={add} className="mb-4 flex flex-wrap gap-2">
          <Input required value={term} onChange={(e) => setTerm(e.target.value)} placeholder="term to block" className="w-48" />
          <Input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="reason (optional)" className="w-64" />
          <Button type="submit"><Ban className="h-3.5 w-3.5" /> Block</Button>
        </form>
        {!items ? <TableSkeleton rows={3} /> : items.length === 0 ? (
          <p className="py-4 text-center text-xs text-slate-400">No blacklisted terms</p>
        ) : (
          <div className="flex flex-wrap gap-2">
            {items.map((b) => (
              <span key={b.id} className="flex items-center gap-2 rounded-full border border-red-200 bg-red-50 px-3 py-1 text-xs text-red-700">
                {b.term}
                {b.reason && <i className="text-[10px] text-red-400">({b.reason})</i>}
                <button onClick={() => remove(b)} className="font-bold hover:text-red-900 cursor-pointer">×</button>
              </span>
            ))}
          </div>
        )}
      </div>
    </Card>
  )
}

export default function Admin() {
  const { user } = useAuth()
  const [tab, setTab] = useState('users')

  if (user?.role !== 'superadmin') {
    return <EmptyState icon={Users} title="Admin access required" message="This area is restricted to superadmin accounts." />
  }

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-bold text-navy">Admin Panel</h1>
        <p className="text-xs text-slate-500">User management · scraper control · system health</p>
      </div>
      <Tabs tabs={TABS} active={tab} onChange={setTab} />
      {tab === 'users' && <UsersTab />}
      {tab === 'scrapers' && <ScrapersTab />}
      {tab === 'health' && <HealthTab />}
      {tab === 'usage' && <UsageTab />}
      {tab === 'blacklist' && <BlacklistTab />}
    </div>
  )
}
