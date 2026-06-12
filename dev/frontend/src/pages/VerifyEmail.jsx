import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { api } from '../api/client'
import AuthShell from '../components/AuthShell'
import { Spinner } from '../components/ui'

export default function VerifyEmail() {
  const [params] = useSearchParams()
  const token = params.get('token')
  const [state, setState] = useState({ status: 'verifying' })

  useEffect(() => {
    if (!token) {
      setState({ status: 'error', message: 'Missing verification token.' })
      return
    }
    api.post('/auth/verify-email', { token }, { auth: false })
      .then(() => setState({ status: 'ok' }))
      .catch((err) => setState({ status: 'error', message: err.message }))
  }, [token])

  return (
    <AuthShell title="Email verification">
      {state.status === 'verifying' && (
        <div className="flex items-center gap-3 text-sm text-slate-600"><Spinner /> Verifying your email…</div>
      )}
      {state.status === 'ok' && (
        <div>
          <p className="rounded-lg bg-emerald-50 px-3 py-2 text-sm font-medium text-emerald-700">
            ✅ Email verified! Your daily digests and alerts are now active.
          </p>
          <Link to="/login" className="mt-4 inline-block text-sm font-medium text-teal hover:underline">
            Continue to sign in →
          </Link>
        </div>
      )}
      {state.status === 'error' && (
        <div>
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm font-medium text-red-700">{state.message}</p>
          <Link to="/login" className="mt-4 inline-block text-sm font-medium text-teal hover:underline">
            ← Back to sign in
          </Link>
        </div>
      )}
    </AuthShell>
  )
}
