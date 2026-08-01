import { createContext, useContext } from 'react'
import type { Session, User } from '@supabase/supabase-js'

import { signIn, signOut, signUp } from '@/lib/auth'

export type AuthContextValue = {
  session: Session | null
  user: User | null
  loading: boolean
  signIn: typeof signIn
  signUp: typeof signUp
  signOut: typeof signOut
}

export const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext)
  if (!context) throw new Error('useAuth must be used inside AuthProvider')
  return context
}
