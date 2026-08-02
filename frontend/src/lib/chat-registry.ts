import { Chat, type UIMessage } from '@ai-sdk/react'

import { toInitialChatMessage } from '@/components/chat/message-format'
import { chatApi } from '@/lib/chat-api'
import { createChatTransport } from '@/lib/chat-stream'

type Entry = {
  chat: Chat<UIMessage>
  /** Cached on success only, so a failed load can be retried. */
  history: Promise<void> | null
  loaded: boolean
  /** A send that never reached the server, kept with the text so it can be resent. */
  sendFailure: SendFailure | null
}

export type SendFailure = {
  error: unknown
  text: string
}

/**
 * Owns one `Chat` per thread for the life of the signed-in session.
 *
 * The chat instances have to outlive the component that renders them: a run
 * started in one thread keeps streaming while you read another, and coming back
 * rejoins the same instance mid-stream instead of re-reading a half-written
 * thread from the database.
 */
export class ChatRegistry {
  #entries = new Map<string, Entry>()
  #running: ReadonlySet<string> = new Set()
  #listeners = new Set<() => void>()
  #transport = createChatTransport()
  #ownerId: string | null = null
  #version = 0

  /** Drops everything when the signed-in account changes. */
  setOwner(ownerId: string): void {
    if (this.#ownerId === ownerId) return
    if (this.#ownerId !== null) this.forgetAll()
    this.#ownerId = ownerId
  }

  chatFor(threadId: string): Chat<UIMessage> {
    return this.#entry(threadId).chat
  }

  /** True once stored messages are in the chat — revisits skip the skeleton. */
  isLoaded(threadId: string): boolean {
    return this.#entries.get(threadId)?.loaded ?? false
  }

  /** Resolves once the thread's stored messages are in the chat. Runs once. */
  loadHistory(threadId: string): Promise<void> {
    const entry = this.#entry(threadId)
    entry.history ??= this.#fetchHistory(threadId)
      .then(() => {
        entry.loaded = true
      })
      .catch((error: unknown) => {
        entry.history = null
        throw error
      })
    return entry.history
  }

  reloadHistory(threadId: string): Promise<void> {
    const entry = this.#entry(threadId)
    entry.history = null
    entry.loaded = false
    return this.loadHistory(threadId)
  }

  /**
   * Runs a turn and records a transport failure against the thread.
   *
   * `sendMessage` reports failures through `chat.error` rather than by throwing,
   * and it resolves after the stream ends — by which time whoever started the
   * turn may have moved on. Keeping the failure here is what lets it still be
   * there when the thread is reopened. Aborts leave `error` unset, so stopping a
   * run never reads as a failure.
   */
  async send(threadId: string, text: string): Promise<void> {
    const entry = this.#entry(threadId)
    entry.sendFailure = null
    this.#setRunning(threadId, true)
    try {
      await entry.chat.sendMessage({ text }, { body: { threadId } })
      if (entry.chat.error) entry.sendFailure = { error: entry.chat.error, text }
    } finally {
      this.#setRunning(threadId, false)
    }
  }

  sendFailure(threadId: string): SendFailure | null {
    return this.#entries.get(threadId)?.sendFailure ?? null
  }

  clearSendFailure(threadId: string): void {
    const entry = this.#entries.get(threadId)
    if (!entry?.sendFailure) return
    entry.sendFailure = null
    this.#notify()
  }

  /** Abandons a thread's run and state — for deletion and sign-out. */
  forget(threadId: string): void {
    this.#entries.get(threadId)?.chat.stop()
    this.#entries.delete(threadId)
    this.#setRunning(threadId, false)
  }

  forgetAll(): void {
    for (const threadId of [...this.#entries.keys()]) this.forget(threadId)
  }

  runningThreads = (): ReadonlySet<string> => this.#running

  /** Bumped on every change, so views can subscribe with one snapshot value. */
  version = (): number => this.#version

  subscribe = (listener: () => void): (() => void) => {
    this.#listeners.add(listener)
    return () => this.#listeners.delete(listener)
  }

  #entry(threadId: string): Entry {
    let entry = this.#entries.get(threadId)
    if (!entry) {
      entry = {
        chat: new Chat<UIMessage>({ id: threadId, transport: this.#transport }),
        history: null,
        loaded: false,
        sendFailure: null,
      }
      this.#entries.set(threadId, entry)
    }
    return entry
  }

  async #fetchHistory(threadId: string): Promise<void> {
    const rows = await chatApi.listMessages(threadId)
    const chat = this.chatFor(threadId)
    // A run that started while this was in flight owns the thread now; its
    // messages are newer than anything the fetch could have seen.
    if (this.#running.has(threadId) || chat.messages.length > 0) return
    chat.messages = rows.map(toInitialChatMessage)
  }

  #setRunning(threadId: string, running: boolean): void {
    if (this.#running.has(threadId) === running) {
      this.#notify()
      return
    }
    const next = new Set(this.#running)
    if (running) next.add(threadId)
    else next.delete(threadId)
    this.#running = next
    this.#notify()
  }

  #notify(): void {
    this.#version += 1
    for (const listener of this.#listeners) listener()
  }
}

export const chatRegistry = new ChatRegistry()
