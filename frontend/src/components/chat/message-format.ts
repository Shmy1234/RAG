import type { UIMessage } from '@ai-sdk/react'

import { isStreamErrorCode } from '@/components/chat/chat-errors'
import {
  CHAT_ROUTES,
  RUN_STAGES,
  type ChatMessage,
  type ChatRoute,
  type Citation,
  type RunStage,
  type StreamErrorCode,
} from '@/lib/chat-api'

export type InitialChatMessage = UIMessage

/**
 * Rebuilds the parts a live stream would have produced. Route and error code are
 * carried alongside the text so a reloaded thread renders exactly like the run
 * that produced it — an uncited direct answer stays uncited rather than reading
 * as a grounding refusal, and a failed turn stays visibly failed.
 */
export function toInitialChatMessage(message: ChatMessage): InitialChatMessage {
  const citations = parseCitations(message.message_data.citations)
  const route = parseRoute(message.message_data.route)
  const errorCode = message.message_data.error_code
  return {
    id: message.id,
    role: message.role,
    parts: [
      { type: 'text', text: message.content },
      ...(route ? [{ type: 'data-route' as const, data: { route } }] : []),
      ...(citations.length ? [{ type: 'data-citations' as const, data: citations }] : []),
      ...(isStreamErrorCode(errorCode)
        ? [{ type: 'data-error' as const, data: { code: errorCode } }]
        : []),
    ],
  }
}

function parseRoute(value: unknown): ChatRoute | null {
  return CHAT_ROUTES.includes(value as ChatRoute) ? (value as ChatRoute) : null
}

/** Null when the route is unknown — older rows predate the field. */
export function messageRoute(message: { parts: ReadonlyArray<unknown> }): ChatRoute | null {
  for (const part of message.parts) {
    const data = partData(part, 'data-route')
    if (typeof data !== 'object' || data === null) continue
    const route = parseRoute((data as { route?: unknown }).route)
    if (route) return route
  }
  return null
}

/** `message_data` is untrusted JSON: drop malformed citations, keep the thread. */
export function parseCitations(value: unknown): Citation[] {
  if (!Array.isArray(value)) return []
  return value.filter((item): item is Citation => {
    if (typeof item !== 'object' || item === null) return false
    const candidate = item as Record<string, unknown>
    return (
      typeof candidate.chunk_id === 'string' &&
      typeof candidate.citation_index === 'number' &&
      typeof candidate.quoted_text === 'string' &&
      typeof candidate.citation_label === 'string' &&
      typeof candidate.location_label === 'string'
    )
  })
}

function partData(part: unknown, type: string): unknown {
  if (typeof part !== 'object' || part === null) return undefined
  const candidate = part as { type?: unknown; data?: unknown }
  return candidate.type === type ? candidate.data : undefined
}

export function messageCitations(message: { parts: ReadonlyArray<unknown> }): Citation[] {
  return message.parts.flatMap((part) => parseCitations(partData(part, 'data-citations')))
}

function isRunStage(value: unknown): value is RunStage {
  return RUN_STAGES.includes(value as RunStage)
}

/** Unique stages reported by the server, in arrival order. */
export function messageStages(message: { parts: ReadonlyArray<unknown> }): RunStage[] {
  const stages: RunStage[] = []
  for (const part of message.parts) {
    const data = partData(part, 'data-status')
    if (typeof data !== 'object' || data === null) continue
    const candidate = (data as { stage?: unknown }).stage
    if (isRunStage(candidate) && !stages.includes(candidate)) stages.push(candidate)
  }
  return stages
}

export function messageErrorCode(message: {
  parts: ReadonlyArray<unknown>
}): StreamErrorCode | null {
  for (const part of message.parts) {
    const data = partData(part, 'data-error')
    if (typeof data !== 'object' || data === null) continue
    const candidate = (data as { code?: unknown }).code
    if (isStreamErrorCode(candidate)) return candidate
  }
  return null
}

export function messageText(message: { parts: ReadonlyArray<unknown> }): string {
  return message.parts
    .map((part) => {
      if (typeof part !== 'object' || part === null || !('type' in part) || !('text' in part)) {
        return ''
      }
      return part.type === 'text' && typeof part.text === 'string' ? part.text : ''
    })
    .join('')
}
