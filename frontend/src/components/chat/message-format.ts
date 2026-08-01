import type { UIMessage } from '@ai-sdk/react'

import type { ChatMessage } from '@/lib/chat-api'

export type InitialChatMessage = UIMessage

export function toInitialChatMessage(message: ChatMessage): InitialChatMessage {
  return {
    id: message.id,
    role: message.role,
    parts: [{ type: 'text', text: message.content }],
  }
}

export function messageText(message: { parts: ReadonlyArray<unknown> }): string {
  return message.parts.map((part) => {
    if (typeof part !== 'object' || part === null || !('type' in part) || !('text' in part)) {
      return ''
    }
    return part.type === 'text' && typeof part.text === 'string' ? part.text : ''
  }).join('')
}
