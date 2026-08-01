import { useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { ChatThread as ChatThreadView } from '@/components/chat/ChatThread'
import { ThreadSidebar } from '@/components/chat/ThreadSidebar'
import { chatApi, type ChatThread } from '@/lib/chat-api'

export function ChatPage() {
  const { threadId } = useParams()
  const navigate = useNavigate()
  const [threads, setThreads] = useState<ChatThread[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function refreshThreads() {
    setError(null)
    try {
      setThreads(await chatApi.listThreads())
    } catch (unknownError) {
      setError(unknownError instanceof Error ? unknownError.message : 'Failed to load chats')
    }
  }

  async function createThread() {
    setCreating(true)
    setError(null)
    try {
      const thread = await chatApi.createThread(null)
      setThreads((current) => [thread, ...current])
      navigate(`/app/chats/${thread.id}`)
    } catch (unknownError) {
      setError(unknownError instanceof Error ? unknownError.message : 'Failed to create chat')
    } finally {
      setCreating(false)
    }
  }

  useEffect(() => {
    let cancelled = false

    async function loadInitialThreads() {
      try {
        const loadedThreads = await chatApi.listThreads()
        if (cancelled) return
        setThreads(loadedThreads)
        setError(null)
      } catch (unknownError) {
        if (!cancelled) {
          setError(unknownError instanceof Error ? unknownError.message : 'Failed to load chats')
        }
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void loadInitialThreads()
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <main className="flex h-screen bg-background text-foreground">
      <ThreadSidebar threads={threads} creating={creating} onCreateThread={createThread} />
      <section className="flex min-w-0 flex-1 flex-col">
        {loading && threads.length === 0 ? (
          <div className="p-6 text-sm text-muted-foreground">Loading chats...</div>
        ) : error && threads.length === 0 ? (
          <div className="p-6 text-sm text-destructive">{error}</div>
        ) : threadId ? (
          <ChatThreadView key={threadId} threadId={threadId} onMessageCommitted={refreshThreads} />
        ) : (
          <div className="flex flex-1 items-center justify-center p-6 text-sm text-muted-foreground">
            Create or select a chat.
          </div>
        )}
      </section>
    </main>
  )
}
