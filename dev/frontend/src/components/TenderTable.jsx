// Shared tender results table: status select, bookmark star, urgency-aware
// closing dates, relevance badges. Used by Search, My Tenders, etc.
import { useNavigate } from 'react-router-dom'
import { Bookmark, SearchX } from 'lucide-react'
import { api, daysUntil, fmtDate, fmtDateTime, fmtINR } from '../api/client'
import { cn, EmptyState, RelevanceBadge, TableSkeleton, useToast } from './ui'

const STATUS_OPTIONS = [
  { value: 'none', label: '—' },
  { value: 'interested', label: 'Interested' },
  { value: 'bidding', label: 'Bidding' },
  { value: 'won', label: 'Won' },
  { value: 'lost', label: 'Lost' },
  { value: 'ignored', label: 'Not relevant' },
]

export const STATUS_COLORS = {
  interested: 'text-sky-700 bg-sky-50 border-sky-200',
  bidding: 'text-amber-700 bg-amber-50 border-amber-200',
  won: 'text-emerald-700 bg-emerald-50 border-emerald-200',
  lost: 'text-red-700 bg-red-50 border-red-200',
  ignored: 'text-slate-500 bg-slate-50 border-slate-200',
}

function ClosingCell({ value }) {
  const days = daysUntil(value)
  return (
    <div>
      <div className="text-xs text-slate-700">{fmtDateTime(value)}</div>
      {days !== null && days >= 0 && (
        <span className={cn('text-[10px] font-semibold', days <= 3 ? 'text-red-600' : days <= 7 ? 'text-amber-600' : 'text-slate-400')}>
          {days === 0 ? 'closes today' : `${days} day${days === 1 ? '' : 's'} left`}
        </span>
      )}
      {days !== null && days < 0 && <span className="text-[10px] font-semibold text-slate-400">closed</span>}
    </div>
  )
}

export default function TenderTable({ items, loading, onUpdated, emptyTitle = 'No tenders found', emptyMessage }) {
  const navigate = useNavigate()
  const toast = useToast()

  const update = async (tender, patch) => {
    try {
      const updated = await api.post(`/tenders/${tender.id}/status`, patch)
      onUpdated?.(updated)
      if (patch.bookmarked !== undefined) toast(patch.bookmarked ? 'Added to watchlist' : 'Removed from watchlist')
      else toast('Tender status updated')
    } catch (e) {
      toast(e.message, 'error')
    }
  }

  if (loading) return <TableSkeleton rows={8} />
  if (!items?.length) {
    return <EmptyState icon={SearchX} title={emptyTitle} message={emptyMessage ?? 'Try widening your filters, adding more keywords, or running a sync.'} />
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-200 text-left">
        <thead>
          <tr className="border-b border-slate-200 text-[10px] uppercase tracking-wider text-slate-400">
            <th className="px-4 py-2.5 font-semibold">Tender</th>
            <th className="px-2 py-2.5 font-semibold">Portal</th>
            <th className="px-2 py-2.5 font-semibold">Closing</th>
            <th className="px-2 py-2.5 font-semibold">Est. Value</th>
            <th className="px-2 py-2.5 font-semibold">Score</th>
            <th className="px-2 py-2.5 font-semibold">Status</th>
            <th className="px-2 py-2.5" />
          </tr>
        </thead>
        <tbody>
          {items.map((t) => (
            <tr key={t.id} className="group border-b border-slate-100 transition-colors hover:bg-teal/4">
              <td className="max-w-105 cursor-pointer px-4 py-3" onClick={() => navigate(`/tenders/${t.id}`)}>
                <p className="line-clamp-2 text-[13px] font-medium text-navy group-hover:text-teal-dark">{t.title}</p>
                <p className="mt-0.5 truncate text-[11px] text-slate-500">
                  {t.organisation || '—'} · {t.tender_ref_no}
                  {t.category && <span className="ml-1.5 rounded bg-slate-100 px-1 py-px text-[10px] uppercase">{t.category}</span>}
                </p>
              </td>
              <td className="px-2 py-3 text-xs text-slate-600">
                <div className="max-w-32 truncate" title={t.portal_name}>{t.portal_name}</div>
                <div className="text-[10px] text-slate-400">{t.state || ''}</div>
              </td>
              <td className="px-2 py-3"><ClosingCell value={t.closing_date} /></td>
              <td className="px-2 py-3 text-xs text-slate-600">{fmtINR(t.estimated_value)}
                <div className="text-[10px] text-slate-400">pub {fmtDate(t.published_date)}</div>
              </td>
              <td className="px-2 py-3"><RelevanceBadge score={t.relevance_score} /></td>
              <td className="px-2 py-3">
                <select
                  value={t.user_status || 'none'}
                  onChange={(e) => update(t, { status: e.target.value })}
                  onClick={(e) => e.stopPropagation()}
                  className={cn('rounded-md border px-1.5 py-1 text-[11px] font-medium cursor-pointer',
                    STATUS_COLORS[t.user_status] || 'border-slate-200 bg-white text-slate-500')}
                >
                  {STATUS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
              </td>
              <td className="px-2 py-3">
                <button
                  onClick={(e) => { e.stopPropagation(); update(t, { bookmarked: !t.bookmarked }) }}
                  className={cn('rounded-md p-1.5 transition-colors cursor-pointer',
                    t.bookmarked ? 'text-teal' : 'text-slate-300 hover:text-slate-500')}
                  title={t.bookmarked ? 'Remove from watchlist' : 'Add to watchlist'}
                >
                  <Bookmark className="h-4 w-4" fill={t.bookmarked ? 'currentColor' : 'none'} />
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
