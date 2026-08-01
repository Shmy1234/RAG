import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '@/auth/auth-context'

export function AuthPage({ mode }: { mode: 'sign-in' | 'sign-up' }) {
  const isSignIn = mode === 'sign-in'
  const { session, signIn, signUp } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  if (session) {
    return <Navigate to="/app" replace />
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setError(null)
    setMessage(null)
    setSubmitting(true)
    const result = isSignIn ? await signIn(email, password) : await signUp(email, password)
    setSubmitting(false)
    if (result.error) {
      setError(result.error.message)
      return
    }
    if (isSignIn || ('session' in result && result.session)) {
      navigate((location.state as { from?: string } | null)?.from ?? '/app', { replace: true })
    } else {
      setMessage('Check your email to confirm your account before signing in.')
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md items-center px-6">
      <section className="w-full rounded-2xl border bg-card p-8 text-left shadow-sm">
        <p className="mb-2 text-sm text-muted-foreground">Document Copilot</p>
        <h1 className="mb-6 text-3xl font-semibold">{isSignIn ? 'Welcome back' : 'Create your account'}</h1>
        <form className="space-y-4" onSubmit={handleSubmit}>
          <label className="block text-sm font-medium">Email<input className="mt-1 w-full rounded-lg border px-3 py-2" type="email" required value={email} onChange={(event) => setEmail(event.target.value)} /></label>
          <label className="block text-sm font-medium">Password<input className="mt-1 w-full rounded-lg border px-3 py-2" type="password" minLength={6} required value={password} onChange={(event) => setPassword(event.target.value)} /></label>
          {error && <p className="text-sm text-destructive" role="alert">{error}</p>}
          {message && <p className="text-sm text-muted-foreground" role="status">{message}</p>}
          <button className="w-full rounded-lg bg-primary px-4 py-2 text-primary-foreground disabled:opacity-50" disabled={submitting} type="submit">{submitting ? 'Working…' : isSignIn ? 'Sign in' : 'Sign up'}</button>
        </form>
        <p className="mt-6 text-sm text-muted-foreground">{isSignIn ? "Don't have an account? " : 'Already have an account? '}<Link className="underline" to={isSignIn ? '/sign-up' : '/sign-in'}>{isSignIn ? 'Sign up' : 'Sign in'}</Link></p>
      </section>
    </main>
  )
}
