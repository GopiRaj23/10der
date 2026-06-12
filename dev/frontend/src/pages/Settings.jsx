// Profile settings + subscription tier (payment integration stubbed).
import { useEffect, useState } from 'react'
import { BadgeCheck, Crown } from 'lucide-react'
import { api } from '../api/client'
import {
  Badge, Button, Card, CardHeader, Input, Label, Modal, Select, useToast,
} from '../components/ui'
import { useAuth } from '../context/AuthContext'
import { INDIAN_STATES } from '../constants'

export default function Settings() {
  const { user, refreshUser } = useAuth()
  const toast = useToast()
  const [form, setForm] = useState(null)
  const [busy, setBusy] = useState(false)
  const [upgradeOpen, setUpgradeOpen] = useState(false)

  useEffect(() => {
    if (user) {
      setForm({
        company_name: user.company_name || '',
        gstin: user.gstin || '',
        industry: user.industry || '',
        state: user.state || '',
        whatsapp_number: user.whatsapp_number || '',
      })
    }
  }, [user])

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const save = async (e) => {
    e.preventDefault()
    setBusy(true)
    try {
      await api.put('/users/me', {
        ...form,
        gstin: form.gstin || null,
        whatsapp_number: form.whatsapp_number || null,
      })
      await refreshUser()
      toast('Profile saved')
    } catch (err) {
      toast(err.message, 'error')
    } finally {
      setBusy(false)
    }
  }

  if (!form) return null

  return (
    <div className="max-w-3xl space-y-4">
      <div>
        <h1 className="text-xl font-bold text-navy">Settings</h1>
        <p className="text-xs text-slate-500">Company profile and subscription</p>
      </div>

      <Card>
        <CardHeader title="Company profile" subtitle="Used for relevance scoring (state & industry) and report headers" />
        <form onSubmit={save} className="space-y-4 p-5">
          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <Label>Email</Label>
              <Input value={user.email} disabled className="bg-slate-50 text-slate-400" />
              <p className="mt-1 flex items-center gap-1 text-[10px] text-emerald-600">
                {user.is_verified ? <><BadgeCheck className="h-3 w-3" /> Verified</> : 'Not verified — check your inbox'}
              </p>
            </div>
            <div>
              <Label>Company name</Label>
              <Input value={form.company_name} onChange={set('company_name')} />
            </div>
            <div>
              <Label>GSTIN (optional)</Label>
              <Input value={form.gstin} onChange={set('gstin')} maxLength={15} />
            </div>
            <div>
              <Label>Industry sector</Label>
              <Input value={form.industry} onChange={set('industry')} placeholder="e.g. Defence & Aerospace" />
            </div>
            <div>
              <Label>State</Label>
              <Select value={form.state} onChange={set('state')}>
                <option value="">Select…</option>
                {INDIAN_STATES.map((s) => <option key={s} value={s}>{s}</option>)}
              </Select>
            </div>
            <div>
              <Label>WhatsApp number (for future alerts)</Label>
              <Input value={form.whatsapp_number} onChange={set('whatsapp_number')} placeholder="+91…" />
            </div>
          </div>
          <Button type="submit" disabled={busy}>{busy ? 'Saving…' : 'Save profile'}</Button>
        </form>
      </Card>

      <Card>
        <CardHeader title="Subscription" />
        <div className="flex flex-wrap items-center justify-between gap-4 p-5">
          <div>
            <Badge color={user.tier === 'pro' ? 'teal' : 'slate'} className="text-xs">
              {user.tier === 'pro' ? '⭐ PRO PLAN' : 'FREE PLAN'}
            </Badge>
            <p className="mt-2 text-xs text-slate-500">
              {user.tier === 'pro'
                ? 'All 19 portals · unlimited keywords · weekly auto-reports'
                : 'Free: 3 portals (GeM, CPPP, eTenders NIC) · 5 keywords · daily digest'}
            </p>
          </div>
          {user.tier !== 'pro' && (
            <Button onClick={() => setUpgradeOpen(true)}><Crown className="h-4 w-4" /> Upgrade to Pro</Button>
          )}
        </div>
      </Card>

      <Modal open={upgradeOpen} onClose={() => setUpgradeOpen(false)} title="Upgrade to Pro">
        <div className="space-y-3 text-sm text-slate-600">
          <p className="rounded-lg bg-teal/10 p-3 text-teal-dark">
            <b>₹1,999/month</b> — all 19 portals, unlimited keywords, instant alerts, weekly intelligence reports.
          </p>
          <p className="text-xs">
            💳 Payment integration (Razorpay / Stripe) is a placeholder in this build. Contact
            <b> sales@tenderradar.example</b> or ask an admin to switch your account tier.
          </p>
          <Button className="w-full" onClick={() => { setUpgradeOpen(false) }}>
            Request upgrade (stub)
          </Button>
        </div>
      </Modal>
    </div>
  )
}
