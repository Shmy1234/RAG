import { api } from '@/lib/api'

export type ChatThread = {
  id: string
  title: string | null
  created_at: string
  updated_at: string
}

export type ChatMessage = {
  id: string
  thread_id: string
  position: number
  role: 'user' | 'assistant'
  content: string
  message_data: Record<string, unknown>
  created_at: string
}

export const chatApi = {
  listThreads: () => api.get<ChatThread[]>('/chat/threads'),
  createThread: (title: string | null) => api.post<ChatThread>('/chat/threads', { title }),
  listMessages: (threadId: string) =>
    api.get<ChatMessage[]>(`/chat/threads/${encodeURIComponent(threadId)}/messages`),
}
