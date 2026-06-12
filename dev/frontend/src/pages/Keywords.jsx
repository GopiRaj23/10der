// Keyword management: boolean expressions, synonyms, primary/secondary
// category, per-keyword portal selection and active toggles.
import { useEffect, useState } from 'react'
import { Pencil, Plus, RefreshCw, Tags, Trash2 } from 'lucide-react'
import { api } from '../api/client'
import {
  Badge, Button, Card, CardHeader, EmptyState, Input, Label, Modal, Select,
  Skeleton, Switch, useToast,
} from '../components/ui'
import { useAuth } from '../context/AuthContext'

const EMPTY_FORM = {
  keyword_text: '', category: 'primary', synonyms: '', boolean_operator: 'OR',
  portals: [], is_active: true,
}

export default function Keywords() {
  const { user } = useAuth()
  const toast = useToast()
  const [keywords, setKeywords] = useState(null)
  const [portals, setPortals] = useState([])
  const [modal, setModal] = useState(null) // null | {mode:'create'} | {mode:'edit', id}
  const [form, setForm] = useState(EMPTY_FORM)
  const [busy, setBusy] = useState(false)
  const [rescanning, setRescanning] = useState(false)

  const load = () => api.get('/keywords').then(setKeywords).catch((e) => toast(e.message, 'error'))
  useEffect(() => {
    load()
    api.get('/portals').then(setPortals).catch(() => {})
  }, [])

  const openCreate = () => { setForm(EMPTY_FORM); setModal({ mode: 'create' }) }
  const openEdit = (k) => {
    setForm({
      keyword_text: k.keyword_text, category: k.category,
      synonyms: (k.synonyms_json || []).join(', '),
      boolean_operator: k.boolean_operator, portals: k.portals_json || [],
      is_active: k.is_active,
    })
    setModal({ mode: 'edit', id: k.id })
  }

  const save = async (e) => {
    e.preventDefault()
    setBusy(true)
    const payload = {
      ...form,
      synonyms: form.synonyms.split(',').map((s) => s.trim()).filter(Boolean),
    }
    try {
      if (modal.mode === 'create') {
        await api.post('/keywords', payload)
        toast('Keyword added — matching it against collected tenders now…')
      } else {
        await api.put(`/keywords/${modal.id}`, payload)
        toast('Keyword updated — re-matching against collected tenders…')
      }
      setModal(null)
      load()
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  const toggleActive = async (k) => {
    try {
      await api.put(`/keywords/${k.id}`, {
        keyword_text: k.keyword_text, category: k.category,
        synonyms: k.synonyms_json || [], boolean_operator: k.boolean_operator,
        portals: k.portals_json || [], is_active: !k.is_active,
      })
      load()
    } catch (err) {
      toast(err.message, 'error')
    }
  }

  const remove = async (k) => {
    if (!confirm(`Delete keyword "${k.keyword_text}"? Its match history will be removed.`)) return
    try {
      await api.del(`/keywords/${k.id}`)
      toast('Keyword deleted')
      load()
    } catch (err) {
      toast(err.message, 'error')
    }
  }

  const rescan = async () => {
    setRescanning(true)
    try {
      const r = await api.post('/keywords/rescan')
      toast(`Rescan complete — ${r.matched} match(es) across ${r.tenders_scanned} tenders`)
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setRescanning(false)
    }
  }

  const togglePortal = (code) =>
    setForm((f) => ({
      ...f,
      portals: f.portals.includes(code) ? f.portals.filter((p) => p !== code) : [...f.portals, code],
    }))

  const freeLimit = user?.tier === 'free'

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold text-navy">My Business Keywords</h1>
          <p className="text-xs text-slate-500">
            Boolean operators supported: <code className="rounded bg-slate-200 px-1">AND</code>{' '}
            <code className="rounded bg-slate-200 px-1">OR</code>{' '}
            <code className="rounded bg-slate-200 px-1">NOT</code> — e.g. <i>drone AND surveillance NOT toy</i>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="secondary" onClick={rescan} disabled={rescanning}
            title="Re-match your keywords against every tender already collected — no scraping, instant.">
            <RefreshCw className={`h-4 w-4 ${rescanning ? 'animate-spin' : ''}`} />
            {rescanning ? 'Rescanning…' : 'Rescan now'}
          </Button>
          <Button onClick={openCreate}><Plus className="h-4 w-4" /> Add keyword</Button>
        </div>
      </div>

      {freeLimit && (
        <p className="rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-2.5 text-xs text-amber-800">
          Free plan: up to <b>5 keywords</b> across <b>3 portals</b> (GeM, CPPP, eTenders NIC).{' '}
          <a href="/settings" className="font-semibold underline">Upgrade to Pro</a> for unlimited keywords and all 19 portals.
        </p>
      )}

      {!keywords ? (
        <div className="grid gap-3 md:grid-cols-2">{[1, 2, 3, 4].map((i) => <Skeleton key={i} className="h-32" />)}</div>
      ) : keywords.length === 0 ? (
        <Card>
          <EmptyState
            icon={Tags}
            title="No keywords yet"
            message='Add the words that describe your business — e.g. "UAV", "thermal camera", "composite materials" — and TenderRadar will match every new tender against them.'
            action={<Button onClick={openCreate}><Plus className="h-4 w-4" /> Add your first keyword</Button>}
          />
        </Card>
      ) : (
        <div className="grid gap-3 md:grid-cols-2">
          {keywords.map((k) => (
            <Card key={k.id} className={!k.is_active ? 'opacity-60' : ''}>
              <div className="flex items-start justify-between p-4">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="font-mono text-sm font-bold text-navy">{k.keyword_text}</span>
                    <Badge color={k.category === 'primary' ? 'teal' : 'slate'}>{k.category}</Badge>
                  </div>
                  {(k.synonyms_json || []).length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {k.synonyms_json.map((s) => (
                        <span key={s} className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500">≈ {s}</span>
                      ))}
                    </div>
                  )}
                  <p className="mt-2 text-[10px] text-slate-400">
                    Portals: {(k.portals_json || []).length ? k.portals_json.join(', ').toUpperCase() : 'all allowed portals'}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-1.5">
                  <Switch checked={k.is_active} onChange={() => toggleActive(k)} />
                  <button onClick={() => openEdit(k)} className="rounded p-1.5 text-slate-400 hover:bg-slate-100 hover:text-navy cursor-pointer"><Pencil className="h-3.5 w-3.5" /></button>
                  <button onClick={() => remove(k)} className="rounded p-1.5 text-slate-400 hover:bg-red-50 hover:text-red-600 cursor-pointer"><Trash2 className="h-3.5 w-3.5" /></button>
                </div>
              </div>
            </Card>
          ))}
        </div>
      )}

      <Modal open={!!modal} onClose={() => setModal(null)} title={modal?.mode === 'create' ? 'Add keyword' : 'Edit keyword'} wide>
        <form onSubmit={save} className="space-y-4">
          <div>
            <Label>Keyword / boolean expression *</Label>
            <Input required value={form.keyword_text}
              onChange={(e) => setForm((f) => ({ ...f, keyword_text: e.target.value }))}
              placeholder='e.g. UAV — or — drone AND surveillance NOT toy' />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <Label>Category</Label>
              <Select value={form.category} onChange={(e) => setForm((f) => ({ ...f, category: e.target.value }))}>
                <option value="primary">Primary (always searched)</option>
                <option value="secondary">Secondary (lower priority)</option>
              </Select>
            </div>
            <div>
              <Label>Default operator between terms</Label>
              <Select value={form.boolean_operator} onChange={(e) => setForm((f) => ({ ...f, boolean_operator: e.target.value }))}>
                <option value="OR">OR (any term)</option>
                <option value="AND">AND (all terms)</option>
                <option value="NOT">NOT (exclude)</option>
              </Select>
            </div>
          </div>
          <div>
            <Label>Synonyms (comma separated)</Label>
            <Input value={form.synonyms} onChange={(e) => setForm((f) => ({ ...f, synonyms: e.target.value }))}
              placeholder="unmanned aerial vehicle, RPAS, drone" />
          </div>
          <div>
            <Label>Search on portals (leave all unchecked = every allowed portal)</Label>
            <div className="grid max-h-44 grid-cols-2 gap-1 overflow-y-auto rounded-lg border border-slate-200 p-2">
              {portals.map((p) => {
                const locked = user?.tier === 'free' && p.tier_required !== 'free'
                return (
                  <label key={p.code} className={`flex items-center gap-2 rounded px-2 py-1 text-xs ${locked ? 'opacity-40' : 'cursor-pointer hover:bg-slate-50'}`}>
                    <input type="checkbox" disabled={locked} checked={form.portals.includes(p.code)}
                      onChange={() => togglePortal(p.code)} className="accent-teal" />
                    <span className="truncate">{p.name}</span>
                    {locked && <Badge color="purple">PRO</Badge>}
                  </label>
                )
              })}
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Switch checked={form.is_active} onChange={(v) => setForm((f) => ({ ...f, is_active: v }))} />
            <span className="text-xs text-slate-600">Active (matched during scrapes)</span>
          </div>
          <div className="flex justify-end gap-2 border-t border-slate-100 pt-3">
            <Button type="button" variant="secondary" onClick={() => setModal(null)}>Cancel</Button>
            <Button type="submit" disabled={busy}>{busy ? 'Saving…' : 'Save keyword'}</Button>
          </div>
        </form>
      </Modal>
    </div>
  )
}
