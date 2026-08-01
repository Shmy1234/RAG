import { useEffect, useMemo, useState, type ReactNode } from 'react'
import type { Session } from '@supabase/supabase-js'

import { getSession, signIn, signOut, signUp } from '@/lib/auth'
import { supabase } from '@/lib/supabase'
import { AuthContext } from '@/auth/auth-context'

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    void getSession().then((nextSession) => {
      setSession(nextSession)
      setLoading(false)
    })
    const { data } = supabase.auth.onAuthStateChange((_event, nextSession) => setSession(nextSession))
    return () => data.subscription.unsubscribe()
  }, [])

  const value = useMemo(() => ({ session, user: session?.user ?? null, loading, signIn, signUp, signOut }), [loading, session])
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
