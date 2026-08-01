import { Send } from 'lucide-react'
import { useEffect, useMemo, useState, type FormEvent } from 'react'
import { useChat } from '@ai-sdk/react'

import { Button } from '@/components/ui/button'
import { messageText, toInitialChatMessage, type InitialChatMessage } from '@/components/chat/message-format'
import { chatApi } from '@/lib/chat-api'
import { createChatTransport } from '@/lib/chat-stream'

type ChatThreadProps = {
  threadId: string
  onMessageCommitted: () => void | Promise<void>
}

export function ChatThread({ threadId, onMessageCommitted }: ChatThreadProps) {
  const [initialMessages, setInitialMessages] = useState<InitialChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loadingHistory, setLoadingHistory] = useState(true)
  const [historyError, setHistoryError] = useState<string | null>(null)
  const transport = useMemo(() => createChatTransport(), [])
  const { messages, sendMessage, status, error, setMessages } = useChat({
    id: threadId,
    messages: initialMessages,
    transport,
  })

  useEffect(() => {
    let cancelled = false

    async function loadMessages() {
      setLoadingHistory(true)
      setHistoryError(null)
      try {
        const rows = await chatApi.listMessages(threadId)
        if (cancelled) return
        const converted = rows.map(toInitialChatMessage)
        setInitialMessages(converted)
        setMessages(converted)
      } catch (unknownError) {
        if (!cancelled) {
          setHistoryError(unknownError instanceof Error ? unknownError.message : 'Failed to load messages')
        }
      } finally {
        if (!cancelled) setLoadingHistory(false)
      }
    }

    void loadMessages()
    return () => {
      cancelled = true
    }
  }, [threadId, setMessages])

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const text = input.trim()
    if (!text || status === 'streaming' || status === 'submitted') return
    setInput('')
    try {
      await sendMessage({ text }, { body: { threadId } })
      await onMessageCommitted()
    } catch {
      setInput(text)
    }
  }

  const busy = status === 'streaming' || status === 'submitted'

  return (
    <div className="flex min-h-0 flex-1 flex-col text-left">
      <div className="flex h-14 items-center border-b px-5 text-sm font-medium">Document Copilot</div>
      <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
        {loadingHistory ? (
          <p className="text-sm text-muted-foreground">Loading messages...</p>
        ) : historyError ? (
          <p className="text-sm text-destructive">{historyError}</p>
        ) : messages.length === 0 ? (
          <p className="text-sm text-muted-foreground">Ask a question about the filing corpus.</p>
        ) : (
          <div className="space-y-4">
            {messages.map((message) => (
              <div key={message.id} className={message.role === 'user' ? 'flex justify-end' : 'flex justify-start'}>
                <div
                  className={
                    message.role === 'user'
                      ? 'max-w-3xl rounded-md bg-primary px-4 py-3 text-sm text-primary-foreground'
                      : 'max-w-3xl rounded-md border bg-background px-4 py-3 text-sm'
                  }
                >
                  {messageText(message)}
                </div>
              </div>
            ))}
          </div>
        )}
        {busy ? <p className="mt-4 text-sm text-muted-foreground">Streaming response...</p> : null}
        {error ? <p className="mt-4 text-sm text-destructive">{error.message}</p> : null}
      </div>
      <form onSubmit={submit} className="flex gap-2 border-t p-4">
        <input
          aria-label="Chat message"
          className="min-w-0 flex-1 rounded-md border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-ring"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="Ask about a filing..."
        />
        <Button
          aria-label="Send message"
          title="Send message"
          type="submit"
          disabled={!input.trim() || busy}
        >
          <Send className="size-4" />
        </Button>
      </form>
    </div>
  )
}
