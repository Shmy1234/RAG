import { useChat } from '@ai-sdk/react'
import { useCallback, useEffect, useMemo, useRef, useState, type FormEvent } from 'react'
import { Link } from 'react-router-dom'

import {
  Conversation,
  ConversationContent,
  ConversationScrollButton,
} from '@/components/ai-elements/conversation'
import {
  PromptInput,
  PromptInputSubmit,
  PromptInputTextarea,
  PromptInputToolbar,
} from '@/components/ai-elements/prompt-input'
import { AssistantMessage } from '@/components/chat/AssistantMessage'
import { ChatEmptyState } from '@/components/chat/ChatEmptyState'
import { EvidencePanel, type SelectedCitation } from '@/components/chat/EvidencePanel'
import { RunStatus } from '@/components/chat/RunStatus'
import {
  describeError,
  describeStreamError,
  type ErrorDescription,
} from '@/components/chat/chat-errors'
import {
  messageErrorCode,
  messageStage,
  messageText,
  toInitialChatMessage,
  type InitialChatMessage,
} from '@/components/chat/message-format'
import { ErrorNotice } from '@/components/common/ErrorNotice'
import { Button } from '@/components/ui/button'
import { Skeleton } from '@/components/ui/skeleton'
import { chatApi } from '@/lib/chat-api'
import { createChatTransport } from '@/lib/chat-stream'
import { deriveThreadTitle } from '@/lib/format'

type ChatThreadProps = {
  threadId: string
  hasTitle: boolean
  onThreadChanged: () => void | Promise<void>
}

export function ChatThread({ threadId, hasTitle, onThreadChanged }: ChatThreadProps) {
  const [input, setInput] = useState('')
  const [loadingHistory, setLoadingHistory] = useState(true)
  const [historyError, setHistoryError] = useState<ErrorDescription | null>(null)
  const [sendError, setSendError] = useState<ErrorDescription | null>(null)
  const [selected, setSelected] = useState<SelectedCitation | null>(null)
  const [historyToken, setHistoryToken] = useState(0)
  const lastChipRef = useRef<HTMLButtonElement | null>(null)
  const composerRef = useRef<HTMLTextAreaElement>(null)

  const transport = useMemo(() => createChatTransport(), [])
  const { messages, sendMessage, status, stop, setMessages } = useChat({
    id: threadId,
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
        setMessages(rows.map(toInitialChatMessage) as InitialChatMessage[])
      } catch (unknownError) {
        if (!cancelled) setHistoryError(describeError(unknownError))
      } finally {
        if (!cancelled) setLoadingHistory(false)
      }
    }

    void loadMessages()
    return () => {
      cancelled = true
    }
  }, [threadId, historyToken, setMessages])

  const busy = status === 'streaming' || status === 'submitted'

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const text = input.trim()
    if (!text || busy) return

    setInput('')
    setSendError(null)
    try {
      await sendMessage({ text }, { body: { threadId } })
      // The thread is named after the question that started it.
      if (!hasTitle) await chatApi.updateThreadTitle(threadId, deriveThreadTitle(text))
      await onThreadChanged()
    } catch (unknownError) {
      setInput(text)
      setSendError(describeError(unknownError))
    }
  }

  /** Closing the rail returns focus to the chip that opened it. */
  const closeEvidence = useCallback(() => {
    setSelected(null)
    lastChipRef.current?.focus()
    lastChipRef.current = null
  }, [])

  const lastMessage = messages.at(-1)
  const streamErrorCode = lastMessage ? messageErrorCode(lastMessage) : null
  const activeError =
    sendError ?? (streamErrorCode ? describeStreamError(streamErrorCode) : null) ?? historyError
  const stage = busy && lastMessage?.role === 'assistant' ? messageStage(lastMessage) : null

  return (
    <div className="flex min-h-0 flex-1">
      <div className="flex min-w-0 flex-1 flex-col">
        <Conversation>
          <ConversationContent className="mx-auto w-full max-w-3xl px-4 py-6">
            {loadingHistory ? (
              <div aria-label="Loading messages" className="space-y-6" role="status">
                <Skeleton className="ml-auto h-9 w-2/5 rounded-xl" />
                <div className="space-y-2">
                  <Skeleton className="h-3 w-16" />
                  <Skeleton className="h-3 w-full" />
                  <Skeleton className="h-3 w-11/12" />
                  <Skeleton className="h-3 w-3/4" />
                </div>
              </div>
            ) : messages.length === 0 ? (
              <ChatEmptyState
                onPick={(question) => {
                  setInput(question)
                  composerRef.current?.focus()
                }}
              />
            ) : (
              <div className="space-y-6">
                {messages.map((message, index) =>
                  message.role === 'assistant' ? (
                    <AssistantMessage
                      key={message.id}
                      message={message}
                      onCitationSelect={(messageId, citation, chip) => {
                        lastChipRef.current = chip
                        setSelected({ messageId, citationIndex: citation.citation_index })
                      }}
                      selectedCitationIndex={
                        selected?.messageId === message.id ? selected.citationIndex : null
                      }
                      streaming={busy && index === messages.length - 1}
                    />
                  ) : (
                    <div className="flex justify-end" key={message.id}>
                      <div className="max-w-[75%] rounded-xl bg-primary px-3.5 py-2.5 text-primary-foreground">
                        {messageText(message)}
                      </div>
                    </div>
                  ),
                )}

                {busy ? <RunStatus stage={stage} /> : null}

                {activeError ? (
                  <ErrorNotice
                    action={
                      activeError.needsSignIn ? (
                        <Button render={<Link to="/sign-in" />} size="sm" variant="outline">
                          Sign in
                        </Button>
                      ) : null
                    }
                    description={activeError.description}
                    onRetry={
                      activeError.canRetry && historyError
                        ? () => setHistoryToken((token) => token + 1)
                        : undefined
                    }
                    title={activeError.title}
                    tone={activeError.tone}
                  />
                ) : null}
              </div>
            )}
          </ConversationContent>
          <ConversationScrollButton />
        </Conversation>

        <div className="mx-auto w-full max-w-3xl px-4 pb-4">
          <PromptInput onSubmit={submit}>
            <PromptInputTextarea
              aria-label="Ask about a filing"
              disabled={busy}
              onChange={(event) => setInput(event.target.value)}
              placeholder="Ask about a filing…"
              ref={composerRef}
              value={input}
            />
            <PromptInputToolbar>
              <span className="pl-1.5 text-[0.6875rem] text-muted-foreground">
                Answers cite the filings they come from
              </span>
              <PromptInputSubmit
                disabled={!busy && !input.trim()}
                onStop={stop}
                status={busy ? 'streaming' : 'ready'}
              />
            </PromptInputToolbar>
          </PromptInput>
        </div>
      </div>

      {selected ? <EvidencePanel onClose={closeEvidence} selection={selected} /> : null}
    </div>
  )
}
