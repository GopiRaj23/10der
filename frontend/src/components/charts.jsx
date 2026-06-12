// Lightweight hand-rolled charts (no chart library): bars, heatmap, funnel,
// trend line and the closing-date calendar.
import { useNavigate } from 'react-router-dom'
import { cn } from './ui'

export function HBarChart({ data, labelKey, valueKey, color = 'bg-teal' }) {
  const max = Math.max(1, ...data.map((d) => d[valueKey]))
  if (!data.length) return <p className="px-1 py-6 text-center text-xs text-slate-400">No data yet</p>
  return (
    <div className="space-y-2.5">
      {data.map((d) => (
        <div key={d[labelKey]}>
          <div className="mb-0.5 flex justify-between text-[11px]">
            <span className="max-w-[70%] truncate font-medium text-slate-600">{d[labelKey]}</span>
            <span className="text-slate-400">{d[valueKey]}</span>
          </div>
          <div className="h-2 rounded-full bg-slate-100">
            <div className={cn('h-2 rounded-full', color)} style={{ width: `${(d[valueKey] / max) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  )
}

export function Heatmap({ heatmap, days = 14 }) {
  const portals = Object.keys(heatmap)
  if (!portals.length) return <p className="px-1 py-6 text-center text-xs text-slate-400">No portal activity yet</p>
  const dates = Array.from({ length: days }, (_, i) => {
    const d = new Date(Date.now() - (days - 1 - i) * 86400000)
    return d.toISOString().slice(0, 10)
  })
  const max = Math.max(1, ...portals.flatMap((p) => Object.values(heatmap[p])))
  return (
    <div className="overflow-x-auto">
      <table className="w-full">
        <tbody>
          {portals.map((p) => (
            <tr key={p}>
              <td className="max-w-36 truncate pr-2 text-[11px] text-slate-600" title={p}>{p}</td>
              {dates.map((d) => {
                const v = heatmap[p][d] || 0
                const intensity = v === 0 ? 'bg-slate-100' : v / max > 0.66 ? 'bg-teal' : v / max > 0.33 ? 'bg-teal/60' : 'bg-teal/30'
                return (
                  <td key={d} className="p-0.5">
                    <div className={cn('h-4 w-4 rounded-sm', intensity)} title={`${p} · ${d}: ${v} tenders`} />
                  </td>
                )
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export function Funnel({ funnel }) {
  const steps = [
    ['Interested', funnel.interested, 'bg-sky-500'],
    ['Bidding', funnel.bidding, 'bg-amber-500'],
    ['Won', funnel.won, 'bg-emerald-500'],
    ['Lost', funnel.lost, 'bg-red-400'],
  ]
  const max = Math.max(1, ...steps.map(([, v]) => v))
  return (
    <div className="space-y-2">
      {steps.map(([label, value, color]) => (
        <div key={label} className="flex items-center gap-2">
          <span className="w-18 text-[11px] font-medium text-slate-600">{label}</span>
          <div className="h-6 flex-1 rounded-md bg-slate-100">
            <div
              className={cn('flex h-6 items-center justify-end rounded-md px-2 text-[11px] font-bold text-white', color)}
              style={{ width: `${Math.max(value ? 14 : 0, (value / max) * 100)}%` }}
            >
              {value > 0 && value}
            </div>
          </div>
        </div>
      ))}
    </div>
  )
}

export function TrendLine({ trend, height = 60 }) {
  if (!trend.length) return <p className="px-1 py-4 text-center text-xs text-slate-400">No trend data yet</p>
  const max = Math.max(1, ...trend.map((t) => t.count))
  const w = 100 / Math.max(1, trend.length - 1)
  const points = trend.map((t, i) => `${i * w},${height - (t.count / max) * (height - 8)}`).join(' ')
  return (
    <svg viewBox={`0 0 100 ${height}`} className="h-20 w-full" preserveAspectRatio="none">
      <polyline points={`0,${height} ${points} 100,${height}`} fill="#0A939618" stroke="none" />
      <polyline points={points} fill="none" stroke="#0A9396" strokeWidth="1.6" vectorEffect="non-scaling-stroke" />
    </svg>
  )
}

export function MonthCalendar({ month, days }) {
  const navigate = useNavigate()
  const [year, m] = month.split('-').map(Number)
  const first = new Date(year, m - 1, 1)
  const daysInMonth = new Date(year, m, 0).getDate()
  const offset = (first.getDay() + 6) % 7 // Monday-first grid
  const cells = [...Array(offset).fill(null), ...Array.from({ length: daysInMonth }, (_, i) => i + 1)]
  const today = new Date()
  const isThisMonth = today.getFullYear() === year && today.getMonth() === m - 1

  return (
    <div>
      <div className="grid grid-cols-7 gap-1 text-center text-[10px] font-semibold uppercase text-slate-400">
        {['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su'].map((d) => <div key={d} className="py-1">{d}</div>)}
      </div>
      <div className="grid grid-cols-7 gap-1">
        {cells.map((day, i) => {
          if (day === null) return <div key={`x${i}`} />
          const key = `${month}-${String(day).padStart(2, '0')}`
          const tenders = days[key] || []
          const isToday = isThisMonth && today.getDate() === day
          return (
            <div
              key={key}
              className={cn(
                'min-h-12 rounded-md border p-1 text-[11px]',
                isToday ? 'border-teal bg-teal/5' : 'border-slate-100',
                tenders.length && 'cursor-pointer hover:border-teal/60',
              )}
              title={tenders.map((t) => t.title).join('\n')}
              onClick={() => tenders.length === 1 && navigate(`/tenders/${tenders[0].id}`)}
            >
              <span className={cn('font-semibold', isToday ? 'text-teal-dark' : 'text-slate-500')}>{day}</span>
              {tenders.length > 0 && (
                <div className="mt-0.5 flex items-center gap-0.5">
                  <span className="rounded bg-teal px-1 text-[9px] font-bold text-white">{tenders.length}</span>
                  <span className="truncate text-[9px] text-slate-400">closing</span>
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
