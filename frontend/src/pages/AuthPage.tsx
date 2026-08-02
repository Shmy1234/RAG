import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '@/auth/auth-context'
import { LogoMark } from '@/components/brand/Logo'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

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

  if (session) return <Navigate replace to="/app" />

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
      return
    }
    setMessage('Check your email to confirm your account, then sign in.')
  }

  return (
    <main className="flex min-h-svh items-center justify-center px-6 py-12">
      <div className="w-full max-w-sm">
        <Link className="mb-6 flex items-center gap-2" to="/">
          <div className="flex size-8 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <LogoMark className="size-4" />
          </div>
          <span className="font-medium">Document Copilot</span>
        </Link>

        <Card>
          <CardHeader>
            <CardTitle>{isSignIn ? 'Sign in' : 'Create your account'}</CardTitle>
            <CardDescription>
              {isSignIn
                ? 'Use your work email to reach the filing corpus.'
                : 'Use your work email. Analysts only.'}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <form className="space-y-4" onSubmit={handleSubmit}>
              <div className="space-y-1.5">
                <Label htmlFor="email">Email</Label>
                <Input
                  autoComplete="email"
                  id="email"
                  onChange={(event) => setEmail(event.target.value)}
                  required
                  type="email"
                  value={email}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="password">Password</Label>
                <Input
                  autoComplete={isSignIn ? 'current-password' : 'new-password'}
                  id="password"
                  minLength={6}
                  onChange={(event) => setPassword(event.target.value)}
                  required
                  type="password"
                  value={password}
                />
              </div>

              {error ? (
                <p className="text-destructive" role="alert">
                  {error}
                </p>
              ) : null}
              {message ? (
                <p className="text-muted-foreground" role="status">
                  {message}
                </p>
              ) : null}

              <Button className="w-full" disabled={submitting} type="submit">
                {submitting ? 'Working…' : isSignIn ? 'Sign in' : 'Create account'}
              </Button>
            </form>
          </CardContent>
        </Card>

        <p className="mt-4 text-center text-muted-foreground">
          {isSignIn ? "Don't have an account? " : 'Already have an account? '}
          <Link className="underline underline-offset-2" to={isSignIn ? '/sign-up' : '/sign-in'}>
            {isSignIn ? 'Create one' : 'Sign in'}
          </Link>
        </p>
      </div>
    </main>
  )
}
