import { MessagesSquare, PanelLeft } from 'lucide-react'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'

import { AppSidebar } from '@/components/app/AppSidebar'
import { ChatThread } from '@/components/chat/ChatThread'
import { describeError, type ErrorDescription } from '@/components/chat/chat-errors'
import { EmptyState } from '@/components/common/EmptyState'
import { ErrorNotice } from '@/components/common/ErrorNotice'
import { Button } from '@/components/ui/button'
import { SidebarInset, SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar'
import { chatApi, type ChatThread as ChatThreadRecord } from '@/lib/chat-api'

export function ChatPage() {
  const { threadId } = useParams()
  const navigate = useNavigate()
  const [threads, setThreads] = useState<ChatThreadRecord[]>([])
  const [loading, setLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [error, setError] = useState<ErrorDescription | null>(null)

  const refreshThreads = useCallback(async () => {
    try {
      setThreads(await chatApi.listThreads())
      setError(null)
    } catch (unknownError) {
      setError(describeError(unknownError))
    }
  }, [])

  useEffect(() => {
    let cancelled = false

    async function loadInitialThreads() {
      try {
        const loaded = await chatApi.listThreads()
        if (cancelled) return
        setThreads(loaded)
        setError(null)
      } catch (unknownError) {
        if (!cancelled) setError(describeError(unknownError))
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    void loadInitialThreads()
    return () => {
      cancelled = true
    }
  }, [])

  async function createThread() {
    setCreating(true)
    try {
      const thread = await chatApi.createThread(null)
      setThreads((current) => [thread, ...current])
      setError(null)
      navigate(`/app/chats/${thread.id}`)
    } catch (unknownError) {
      setError(describeError(unknownError))
    } finally {
      setCreating(false)
    }
  }

  const activeThread = threads.find((thread) => thread.id === threadId)

  return (
    <SidebarProvider>
      <AppSidebar
        creating={creating}
        loading={loading}
        onCreateThread={() => void createThread()}
        threads={threads}
      />
      <SidebarInset className="min-h-svh">
        <header className="flex h-12 shrink-0 items-center gap-2 border-b px-3">
          <SidebarTrigger />
          <span className="min-w-0 truncate font-medium">
            {activeThread?.title || (threadId ? 'New chat' : 'Document Copilot')}
          </span>
        </header>

        {error && threads.length === 0 ? (
          <div className="mx-auto w-full max-w-md p-6">
            <ErrorNotice
              description={error.description}
              onRetry={error.canRetry ? () => void refreshThreads() : undefined}
              title={error.title}
              tone={error.tone}
            />
          </div>
        ) : threadId ? (
          <ChatThread
            hasTitle={Boolean(activeThread?.title)}
            key={threadId}
            onThreadChanged={refreshThreads}
            threadId={threadId}
          />
        ) : (
          <div className="flex min-h-0 flex-1 items-center justify-center">
            <EmptyState
              description="Pick a conversation from the sidebar, or start a new one to ask about the filing corpus."
              icon={threads.length ? MessagesSquare : PanelLeft}
              title={threads.length ? 'Select a chat' : 'No chats yet'}
            >
              <Button disabled={creating} onClick={() => void createThread()}>
                New chat
              </Button>
            </EmptyState>
          </div>
        )}
      </SidebarInset>
    </SidebarProvider>
  )
}
