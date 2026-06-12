import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import AuthShell from '../components/AuthShell'
import { Button, Input, Label, useToast } from '../components/ui'

export default function ForgotPassword() {
  const navigate = useNavigate()
  const toast = useToast()
  const [step, setStep] = useState(1)
  const [email, setEmail] = useState('')
  const [otp, setOtp] = useState('')
  const [password, setPassword] = useState('')
  const [devOtp, setDevOtp] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  const requestOtp = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const res = await api.post('/auth/forgot-password', { email }, { auth: false })
      if (res.dev_otp) setDevOtp(res.dev_otp)
      setStep(2)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const reset = async (e) => {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await api.post('/auth/reset-password', { email, otp, new_password: password }, { auth: false })
      toast('Password reset — sign in with your new password')
      navigate('/login')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthShell
      title="Reset password"
      subtitle={step === 1 ? 'We’ll email you a 6-digit OTP.' : `Enter the OTP sent to ${email}`}
    >
      {error && <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-xs font-medium text-red-700">{error}</p>}
      {step === 1 ? (
        <form onSubmit={requestOtp} className="space-y-4">
          <div>
            <Label>Email</Label>
            <Input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          </div>
          <Button type="submit" className="w-full" disabled={busy}>{busy ? 'Sending…' : 'Send OTP'}</Button>
        </form>
      ) : (
        <form onSubmit={reset} className="space-y-4">
          {devOtp && (
            <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
              Dev mode OTP: <b className="tracking-widest">{devOtp}</b>
            </p>
          )}
          <div>
            <Label>6-digit OTP</Label>
            <Input required minLength={6} maxLength={6} value={otp}
              onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))} className="tracking-[0.4em]" />
          </div>
          <div>
            <Label>New password (min 8 characters)</Label>
            <Input type="password" required minLength={8} value={password} onChange={(e) => setPassword(e.target.value)} />
          </div>
          <Button type="submit" className="w-full" disabled={busy}>{busy ? 'Resetting…' : 'Reset password'}</Button>
        </form>
      )}
      <p className="mt-4 text-xs">
        <Link to="/login" className="font-medium text-teal hover:underline">← Back to sign in</Link>
      </p>
    </AuthShell>
  )
}
