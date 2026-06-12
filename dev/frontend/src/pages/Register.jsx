import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import AuthShell from '../components/AuthShell'
import { Button, Input, Label, Select, useToast } from '../components/ui'
import { INDIAN_STATES } from '../constants'

export default function Register() {
  const navigate = useNavigate()
  const toast = useToast()
  const [form, setForm] = useState({
    email: '', password: '', company_name: '', industry: '', state: '', gstin: '',
  })
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }))

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const res = await api.post('/auth/register', {
        ...form,
        gstin: form.gstin || null,
        state: form.state || null,
        industry: form.industry || null,
        company_name: form.company_name || null,
      }, { auth: false })
      setResult(res)
      toast('Account created!')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  if (result) {
    return (
      <AuthShell title="Check your email 📬" subtitle="We sent a verification link to your inbox.">
        <p className="text-sm text-slate-600">
          Click the link in the email to verify your account, then sign in.
        </p>
        {result.dev_verification_token && (
          <div className="mt-4 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-800">
            <p className="font-semibold">Dev mode — no email provider configured.</p>
            <Button
              size="sm" className="mt-2"
              onClick={() => navigate(`/verify-email?token=${result.dev_verification_token}`)}
            >
              Verify now (dev shortcut)
            </Button>
          </div>
        )}
        <div className="mt-6">
          <Link to="/login" className="text-sm font-medium text-teal hover:underline">← Back to sign in</Link>
        </div>
      </AuthShell>
    )
  }

  return (
    <AuthShell title="Create your account" subtitle="Free plan: 3 portals, 5 keywords. Upgrade anytime.">
      <form onSubmit={submit} className="space-y-3.5">
        {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-xs font-medium text-red-700">{error}</p>}
        <div>
          <Label>Work email *</Label>
          <Input type="email" required value={form.email} onChange={set('email')} placeholder="you@company.in" />
        </div>
        <div>
          <Label>Password * (min 8 characters)</Label>
          <Input type="password" required minLength={8} value={form.password} onChange={set('password')} />
        </div>
        <div>
          <Label>Company name</Label>
          <Input value={form.company_name} onChange={set('company_name')} placeholder="Acme Industries Pvt Ltd" />
        </div>
        <div className="grid grid-cols-2 gap-3">
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
        </div>
        <div>
          <Label>GSTIN (optional)</Label>
          <Input value={form.gstin} onChange={set('gstin')} maxLength={15} placeholder="33AABCA1234F1Z5" />
        </div>
        <Button type="submit" className="w-full" disabled={busy}>{busy ? 'Creating…' : 'Create account'}</Button>
      </form>
      <p className="mt-4 text-xs text-slate-500">
        Already registered? <Link to="/login" className="font-medium text-teal hover:underline">Sign in</Link>
      </p>
    </AuthShell>
  )
}
