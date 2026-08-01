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

export type Citation = {
  chunk_id: string
  citation_index: number
  quoted_text: string
  citation_label: string
  location_label: string
}

export type CitationSource = Citation & {
  chunk_index: number
  chunk_text: string
  company_name: string
  filing_type: string
  filing_date: string
  page_number: number | null
  section: string | null
  source_url: string
  previous_chunks: CitationChunk[]
  next_chunks: CitationChunk[]
}

export type CitationChunk = {
  chunk_id: string
  chunk_index: number
  text: string
  page_number: number | null
  section: string | null
}

/** Stage identifiers streamed by the backend. Copy is owned by the frontend. */
export const RUN_STAGES = ['routing', 'searching', 'analyzing', 'validating', 'saving'] as const
export type RunStage = (typeof RUN_STAGES)[number]

export const STREAM_ERROR_CODES = [
  'retrieval_failed',
  'grounding_failed',
  'processing_failed',
] as const
export type StreamErrorCode = (typeof STREAM_ERROR_CODES)[number]

export const chatApi = {
  listThreads: () => api.get<ChatThread[]>('/chat/threads'),
  createThread: (title: string | null) => api.post<ChatThread>('/chat/threads', { title }),
  updateThreadTitle: (threadId: string, title: string) =>
    api.patch<ChatThread>(`/chat/threads/${encodeURIComponent(threadId)}`, { title }),
  listMessages: (threadId: string) =>
    api.get<ChatMessage[]>(`/chat/threads/${encodeURIComponent(threadId)}/messages`),
  getCitationSource: (messageId: string, citationIndex: number) =>
    api.get<CitationSource>(
      `/chat/messages/${encodeURIComponent(messageId)}/citations/${citationIndex}/source`,
    ),
}
