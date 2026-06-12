// Main dashboard: stat cards, urgent closing strip, funnel, keyword
// performance, portal heatmap, trend and the closing-date calendar.
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { AlarmClock, Bookmark, CalendarDays, Radar, Sparkles, Tags } from 'lucide-react'
import { api, fmtDateTime } from '../api/client'
import { Funnel, Heatmap, HBarChart, MonthCalendar, TrendLine } from '../components/charts'
import { Badge, Card, CardHeader, EmptyState, RelevanceBadge, Skeleton, useToast } from '../components/ui'
import { useAuth } from '../context/AuthContext'

function StatCard({ label, value, hint, loading }) {
  return (
    <Card className="p-4">
      {loading ? (
        <><Skeleton className="h-7 w-16" /><Skeleton className="mt-2 h-3 w-24" /></>
      ) : (
        <>
          <p className="text-2xl font-bold text-navy">{value}</p>
          <p className="mt-0.5 text-xs font-medium text-slate-500">{label}</p>
          {hint && <p className="text-[10px] text-slate-400">{hint}</p>}
        </>
      )}
    </Card>
  )
}

export default function Dashboard() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const toast = useToast()
  const [stats, setStats] = useState(null)
  const [analytics, setAnalytics] = useState(null)
  const [calendar, setCalendar] = useState(null)
  const [month, setMonth] = useState(() => new Date().toISOString().slice(0, 7))

  useEffect(() => {
    api.get('/dashboard/stats').then(setStats).catch((e) => toast(e.message, 'error'))
    api.get('/dashboard/analytics').then(setAnalytics).catch(() => {})
  }, [])

  useEffect(() => {
    api.get('/dashboard/calendar', { month }).then(setCalendar).catch(() => {})
  }, [month])

  const loading = !stats
  const shiftMonth = (delta) => {
    const [y, m] = month.split('-').map(Number)
    const d = new Date(y, m - 1 + delta, 1)
    setMonth(`${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`)
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-navy">Dashboard</h1>
          <p className="text-xs text-slate-500">
            Welcome back{user?.company_name ? `, ${user.company_name}` : ''} — here’s what your radar picked up.
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <Radar className="h-4 w-4 text-teal" />
          {stats?.active_keywords ?? '—'} active keywords ·{' '}
          <Link to="/keywords" className="font-medium text-teal hover:underline">manage</Link>
        </div>
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        <StatCard loading={loading} label="Found today" value={stats?.found.today} />
        <StatCard loading={loading} label="This week" value={stats?.found.week} />
        <StatCard loading={loading} label="This month" value={stats?.found.month} />
        <StatCard loading={loading} label="New since last login" value={stats?.new_since_last_login} hint="across your keywords" />
        <StatCard loading={loading} label="Watchlist" value={stats?.bookmarks} hint={`${stats?.closing_soon_count ?? 0} closing soon`} />
      </div>

      {/* Urgent action strip */}
      <Card>
        <CardHeader
          title={<span className="flex items-center gap-1.5"><AlarmClock className="h-4 w-4 text-red-500" /> Closing in the next 7 days</span>}
          action={<Link to="/search" className="text-xs font-medium text-teal hover:underline">View all →</Link>}
        />
        {loading ? (
          <div className="space-y-2 p-4">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-10" />)}</div>
        ) : stats.closing_soon.length === 0 ? (
          <EmptyState icon={AlarmClock} title="Nothing urgent" message="No matched tenders close in the next 7 days." />
        ) : (
          <div className="divide-y divide-slate-100">
            {stats.closing_soon.map((t) => (
              <button
                key={t.id}
                onClick={() => navigate(`/tenders/${t.id}`)}
                className="flex w-full items-center gap-3 px-5 py-2.5 text-left hover:bg-teal/4 cursor-pointer"
              >
                <RelevanceBadge score={t.relevance_score} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-[13px] font-medium text-navy">{t.title}</p>
                  <p className="truncate text-[11px] text-slate-500">{t.organisation || '—'} · {t.portal_name}</p>
                </div>
                <Badge color="red">{fmtDateTime(t.closing_date)}</Badge>
              </button>
            ))}
          </div>
        )}
      </Card>

      <div className="grid gap-4 lg:grid-cols-3">
        {/* Funnel */}
        <Card>
          <CardHeader title="Tender funnel" subtitle="Interested → Bidding → Won / Lost" />
          <div className="p-5">
            {stats ? <Funnel funnel={stats.funnel} /> : <Skeleton className="h-32" />}
          </div>
        </Card>

        {/* Keyword performance */}
        <Card>
          <CardHeader
            title={<span className="flex items-center gap-1.5"><Tags className="h-4 w-4 text-teal" /> Keyword performance</span>}
            subtitle="Matches per keyword (all time)"
          />
          <div className="p-5">
            {analytics ? (
              analytics.keyword_performance.length ? (
                <HBarChart data={analytics.keyword_performance.slice(0, 6)} labelKey="keyword" valueKey="matches" />
              ) : (
                <EmptyState icon={Tags} title="No keywords yet"
                  message="Add business keywords to start matching tenders."
                  action={<Link to="/keywords" className="text-xs font-semibold text-teal hover:underline">Add keywords →</Link>} />
              )
            ) : <Skeleton className="h-32" />}
          </div>
        </Card>

        {/* Trend */}
        <Card>
          <CardHeader
            title={<span className="flex items-center gap-1.5"><Sparkles className="h-4 w-4 text-teal" /> New matches trend</span>}
            subtitle="Last 14 days"
          />
          <div className="p-5">
            {analytics ? <TrendLine trend={analytics.trend} /> : <Skeleton className="h-20" />}
          </div>
        </Card>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Portal heatmap */}
        <Card>
          <CardHeader title="Portal activity heatmap" subtitle="Matched tenders per portal per day (last 14 days)" />
          <div className="p-5">
            {analytics ? <Heatmap heatmap={analytics.portal_heatmap} /> : <Skeleton className="h-40" />}
          </div>
        </Card>

        {/* Calendar */}
        <Card>
          <CardHeader
            title={<span className="flex items-center gap-1.5"><CalendarDays className="h-4 w-4 text-teal" /> Closing calendar</span>}
            action={
              <div className="flex items-center gap-2 text-xs">
                <button onClick={() => shiftMonth(-1)} className="rounded px-2 py-1 hover:bg-slate-100 cursor-pointer">←</button>
                <span className="font-semibold text-navy">{month}</span>
                <button onClick={() => shiftMonth(1)} className="rounded px-2 py-1 hover:bg-slate-100 cursor-pointer">→</button>
              </div>
            }
          />
          <div className="p-4">
            {calendar ? <MonthCalendar month={calendar.month} days={calendar.days} /> : <Skeleton className="h-56" />}
          </div>
        </Card>
      </div>
    </div>
  )
}
