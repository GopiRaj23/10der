import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import AuthShell from '../components/AuthShell'
import { Button, Input, Label, useToast } from '../components/ui'
import { useAuth } from '../context/AuthContext'

export default function Login() {
  const { login } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const toast = useToast()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const submit = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await login(email, password)
      toast('Welcome back!')
      navigate(location.state?.from?.pathname || '/', { replace: true })
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell title="Sign in" subtitle="Track tenders matched to your business keywords">
      <form onSubmit={submit} className="space-y-4">
        {error && <p className="rounded-lg bg-red-50 px-3 py-2 text-xs font-medium text-red-700">{error}</p>}
        <div>
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" required value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@company.in" />
        </div>
        <div>
          <Label htmlFor="password">Password</Label>
          <Input id="password" type="password" required value={password} onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" />
        </div>
        <Button type="submit" className="w-full" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</Button>
      </form>
      <div className="mt-4 flex justify-between text-xs">
        <Link to="/forgot-password" className="font-medium text-teal hover:underline">Forgot password?</Link>
        <Link to="/register" className="font-medium text-teal hover:underline">Create an account</Link>
      </div>
      <div className="mt-6 rounded-lg border border-slate-200 bg-white p-3 text-[11px] text-slate-500">
        <p className="mb-1 font-semibold text-slate-600">Demo credentials (seeded)</p>
        <p>Pro user: <code className="text-teal-dark">demo@tenderradar.example / Demo@12345</code></p>
        <p>Admin: <code className="text-teal-dark">admin@tenderradar.example / Admin@12345</code></p>
      </div>
    </AuthShell>
  )
}
