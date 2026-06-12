// Tender detail: full metadata, status/bookmark/notes, AI summary toggle,
// share link, "view on portal" + document links, related tenders.
import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  ArrowLeft, Bookmark, Download, ExternalLink, Share2, Sparkles,
} from 'lucide-react'
import { api, daysUntil, fmtDate, fmtDateTime, fmtINR } from '../api/client'
import { STATUS_COLORS } from '../components/TenderTable'
import {
  Badge, Button, Card, CardHeader, cn, RelevanceBadge, Skeleton, Spinner,
  Textarea, useToast,
} from '../components/ui'

function Meta({ label, value }) {
  return (
    <div>
      <p className="text-[10px] font-semibold uppercase tracking-wide text-slate-400">{label}</p>
      <p className="mt-0.5 text-sm text-slate-700">{value ?? '—'}</p>
    </div>
  )
}

export default function TenderDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const toast = useToast()
  const [tender, setTender] = useState(null)
  const [related, setRelated] = useState(null)
  const [notes, setNotes] = useState('')
  const [summary, setSummary] = useState(null)
  const [summaryBusy, setSummaryBusy] = useState(false)

  useEffect(() => {
    setTender(null)
    setSummary(null)
    api.get(`/tenders/${id}`)
      .then((t) => { setTender(t); setNotes(t.notes || '') })
      .catch((e) => toast(e.message, 'error'))
    api.get(`/tenders/${id}/related`).then(setRelated).catch(() => {})
  }, [id])

  const update = async (patch, message) => {
    try {
      const updated = await api.post(`/tenders/${id}/status`, patch)
      setTender((t) => ({ ...t, ...updated }))
      toast(message)
    } catch (e) {
      toast(e.message, 'error')
    }
  }

  const share = async () => {
    try {
      const res = await api.post(`/tenders/${id}/share`)
      await navigator.clipboard.writeText(res.share_url)
      toast('Shareable link copied to clipboard (valid 30 days)')
    } catch (e) {
      toast(e.message, 'error')
    }
  }

  const loadSummary = async () => {
    setSummaryBusy(true)
    try {
      setSummary(await api.get(`/tenders/${id}/summary`))
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setSummaryBusy(false)
    }
  }

  if (!tender) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-40" />
        <Skeleton className="h-60" />
      </div>
    )
  }

  const days = daysUntil(tender.closing_date)

  return (
    <div className="space-y-4">
      <button onClick={() => navigate(-1)} className="flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-teal cursor-pointer">
        <ArrowLeft className="h-3.5 w-3.5" /> Back
      </button>

      <Card className="p-5">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            <div className="mb-2 flex flex-wrap items-center gap-2">
              <RelevanceBadge score={tender.relevance_score} />
              <Badge color="navy">{tender.portal_name}</Badge>
              {tender.category && <Badge>{tender.category.toUpperCase()}</Badge>}
              {days !== null && days >= 0 && days <= 7 && <Badge color="red">⏰ {days === 0 ? 'Closes today' : `${days} days left`}</Badge>}
            </div>
            <h1 className="text-lg font-bold leading-snug text-navy">{tender.title}</h1>
            <p className="mt-1 text-sm text-slate-500">{tender.organisation || '—'}{tender.department ? ` · ${tender.department}` : ''}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            {tender.raw_url && (
              <a href={tender.raw_url} target="_blank" rel="noreferrer">
                <Button variant="secondary" size="sm"><ExternalLink className="h-3.5 w-3.5" /> View on portal</Button>
              </a>
            )}
            {tender.document_url && (
              <a href={tender.document_url} target="_blank" rel="noreferrer">
                <Button variant="secondary" size="sm"><Download className="h-3.5 w-3.5" /> Documents</Button>
              </a>
            )}
            <Button variant="secondary" size="sm" onClick={share}><Share2 className="h-3.5 w-3.5" /> Share</Button>
            <Button
              variant={tender.bookmarked ? 'primary' : 'secondary'} size="sm"
              onClick={() => update({ bookmarked: !tender.bookmarked }, tender.bookmarked ? 'Removed from watchlist' : 'Added to watchlist')}
            >
              <Bookmark className="h-3.5 w-3.5" fill={tender.bookmarked ? 'currentColor' : 'none'} />
              {tender.bookmarked ? 'Watching' : 'Watch'}
            </Button>
          </div>
        </div>

        <div className="mt-5 grid grid-cols-2 gap-4 border-t border-slate-100 pt-4 md:grid-cols-4">
          <Meta label="Tender Ref No" value={tender.tender_ref_no} />
          <Meta label="Published" value={fmtDate(tender.published_date)} />
          <Meta label="Closing (IST)" value={fmtDateTime(tender.closing_date)} />
          <Meta label="Estimated value" value={fmtINR(tender.estimated_value)} />
          <Meta label="State" value={tender.state} />
          <Meta label="Category" value={tender.category ? tender.category[0].toUpperCase() + tender.category.slice(1) : null} />
          <Meta label="First seen" value={fmtDateTime(tender.scraped_at)} />
          <Meta label="Matched keywords" value={tender.matched_keywords?.length ? tender.matched_keywords.join(', ') : 'None'} />
        </div>

        <p className="mt-4 rounded-lg bg-amber-50 px-3 py-2 text-[11px] text-amber-800">
          ⚠️ Aggregated from a public portal. Always verify details on the official portal before bidding.
        </p>
      </Card>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader
            title="Description"
            action={
              <Button variant="secondary" size="sm" onClick={summary ? () => setSummary(null) : loadSummary} disabled={summaryBusy}>
                {summaryBusy ? <Spinner className="h-3.5 w-3.5" /> : <Sparkles className="h-3.5 w-3.5" />}
                {summary ? 'Hide AI summary' : 'AI summary'}
              </Button>
            }
          />
          <div className="p-5">
            {summary && (
              <div className="mb-4 rounded-lg border border-teal/30 bg-teal/5 p-3.5">
                <p className="mb-2 text-[10px] font-bold uppercase tracking-wide text-teal-dark">
                  ✨ AI Summary <span className="font-normal text-slate-400">({summary.provider})</span>
                </p>
                <ul className="space-y-1.5 text-sm text-slate-700">
                  {summary.summary.map((b, i) => <li key={i} className="flex gap-2"><span className="text-teal">•</span>{b}</li>)}
                </ul>
              </div>
            )}
            <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-600">
              {tender.description_text || 'No description captured — open the original portal for full details.'}
            </p>
          </div>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader title="Your tracking" />
            <div className="space-y-3 p-5">
              <div>
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">Status</p>
                <select
                  value={tender.user_status || 'none'}
                  onChange={(e) => update({ status: e.target.value }, 'Status updated')}
                  className={cn('w-full rounded-lg border px-3 py-2 text-sm font-medium cursor-pointer',
                    STATUS_COLORS[tender.user_status] || 'border-slate-300 bg-white text-slate-600')}
                >
                  <option value="none">— No status —</option>
                  <option value="interested">Interested</option>
                  <option value="bidding">Bidding</option>
                  <option value="won">Won</option>
                  <option value="lost">Lost</option>
                  <option value="ignored">Not relevant</option>
                </select>
              </div>
              <div>
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">Private notes</p>
                <Textarea rows={5} value={notes} onChange={(e) => setNotes(e.target.value)}
                  placeholder="EMD amount, site visit dates, partner contacts…" />
                <Button size="sm" className="mt-2 w-full" onClick={() => update({ notes }, 'Notes saved')}>Save notes</Button>
              </div>
            </div>
          </Card>

          <Card>
            <CardHeader title="Related tenders" subtitle="Same organisation or category" />
            <div className="divide-y divide-slate-100">
              {!related && <div className="space-y-2 p-4">{[1, 2, 3].map((i) => <Skeleton key={i} className="h-9" />)}</div>}
              {related?.length === 0 && <p className="px-5 py-6 text-center text-xs text-slate-400">No related tenders found</p>}
              {related?.map((r) => (
                <Link key={r.id} to={`/tenders/${r.id}`} className="block px-5 py-2.5 hover:bg-teal/4">
                  <p className="line-clamp-2 text-xs font-medium text-navy">{r.title}</p>
                  <p className="mt-0.5 text-[10px] text-slate-400">{r.portal_name} · closes {fmtDate(r.closing_date)}</p>
                </Link>
              ))}
            </div>
          </Card>
        </div>
      </div>
    </div>
  )
}
