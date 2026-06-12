// Public read-only view of a shared tender (token = credential).
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ExternalLink } from 'lucide-react'
import { api, fmtDate, fmtDateTime, fmtINR } from '../api/client'
import Logo from '../components/Logo'
import { Badge, Button, Card, Spinner } from '../components/ui'

export default function ShareView() {
  const { token } = useParams()
  const [tender, setTender] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    api.get(`/share/${token}`, undefined, { auth: false })
      .then(setTender)
      .catch((e) => setError(e.message))
  }, [token])

  return (
    <div className="min-h-screen bg-slate-100">
      <header className="bg-navy px-6 py-4"><Logo /></header>
      <main className="mx-auto max-w-3xl p-6">
        {!tender && !error && <div className="flex justify-center py-20"><Spinner className="h-8 w-8" /></div>}
        {error && (
          <Card className="p-8 text-center">
            <p className="text-sm font-medium text-red-600">{error}</p>
            <p className="mt-2 text-xs text-slate-400">The share link may have expired (links are valid 30 days).</p>
          </Card>
        )}
        {tender && (
          <Card className="p-6">
            <div className="mb-3 flex flex-wrap gap-2">
              <Badge color="navy">{tender.portal_name}</Badge>
              {tender.category && <Badge>{tender.category.toUpperCase()}</Badge>}
              {tender.state && <Badge color="teal">{tender.state}</Badge>}
            </div>
            <h1 className="text-lg font-bold leading-snug text-navy">{tender.title}</h1>
            <p className="mt-1 text-sm text-slate-500">{tender.organisation || '—'}</p>
            <div className="mt-5 grid grid-cols-2 gap-4 border-t border-slate-100 pt-4 sm:grid-cols-4">
              <div><p className="text-[10px] font-semibold uppercase text-slate-400">Ref No</p><p className="text-sm">{tender.tender_ref_no}</p></div>
              <div><p className="text-[10px] font-semibold uppercase text-slate-400">Published</p><p className="text-sm">{fmtDate(tender.published_date)}</p></div>
              <div><p className="text-[10px] font-semibold uppercase text-slate-400">Closing (IST)</p><p className="text-sm">{fmtDateTime(tender.closing_date)}</p></div>
              <div><p className="text-[10px] font-semibold uppercase text-slate-400">Est. value</p><p className="text-sm">{fmtINR(tender.estimated_value)}</p></div>
            </div>
            {tender.raw_url && (
              <a href={tender.raw_url} target="_blank" rel="noreferrer" className="mt-5 inline-block">
                <Button variant="secondary" size="sm"><ExternalLink className="h-3.5 w-3.5" /> View on official portal</Button>
              </a>
            )}
            <p className="mt-5 rounded-lg bg-amber-50 px-3 py-2 text-[11px] text-amber-800">
              ⚠️ This app aggregates publicly available tender information. Always verify on the official portal before bidding.
            </p>
            <p className="mt-4 text-center text-xs text-slate-400">
              Shared via <Link to="/login" className="font-semibold text-teal">TenderRadar</Link> — automated tender discovery for Indian businesses
            </p>
          </Card>
        )}
      </main>
    </div>
  )
}
