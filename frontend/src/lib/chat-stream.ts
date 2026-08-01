import { DefaultChatTransport } from 'ai'

import { env } from '@/lib/env'
import { supabase } from '@/lib/supabase'

export function createChatTransport() {
  return new DefaultChatTransport({
    api: new URL('/chat/stream', `${env.apiBaseUrl}/`).toString(),
    headers: async (): Promise<Record<string, string>> => {
      const { data } = await supabase.auth.getSession()
      if (!data.session?.access_token) return {}
      return { Authorization: `Bearer ${data.session.access_token}` }
    },
  })
}
