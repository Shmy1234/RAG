import { useNavigate } from 'react-router-dom'

import { useAuth } from '@/auth/auth-context'

export function ProtectedPage() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()
  return <main className="mx-auto max-w-3xl p-8"><div className="flex items-center justify-between"><div><p className="text-sm text-muted-foreground">Signed in as</p><h1 className="text-2xl font-semibold">{user?.email}</h1></div><button className="rounded-lg border px-4 py-2" onClick={() => { void signOut().then(() => navigate('/sign-in', { replace: true })) }}>Sign out</button></div><p className="mt-8 text-muted-foreground">Your authenticated workspace is ready.</p></main>
}
