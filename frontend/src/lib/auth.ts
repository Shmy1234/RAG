import type { AuthError, Session, User } from '@supabase/supabase-js'

import { supabase } from '@/lib/supabase'

export type AuthResult = { error: AuthError | null }

export async function signIn(email: string, password: string): Promise<AuthResult> {
  const { error } = await supabase.auth.signInWithPassword({ email, password })
  return { error }
}

export async function signUp(email: string, password: string): Promise<AuthResult & { session: Session | null }> {
  const { data, error } = await supabase.auth.signUp({ email, password })
  return { error, session: data.session }
}

export async function signOut(): Promise<AuthResult> {
  const { error } = await supabase.auth.signOut()
  return { error }
}

export async function getSession(): Promise<Session | null> {
  const { data } = await supabase.auth.getSession()
  return data.session
}

export async function getUser(): Promise<User | null> {
  const { data } = await supabase.auth.getUser()
  return data.user
}
