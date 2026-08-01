import type { ErrorTone } from '@/components/common/ErrorNotice'
import { STREAM_ERROR_CODES, type StreamErrorCode } from '@/lib/chat-api'
import { ApiError } from '@/lib/http'

export type ErrorDescription = {
  tone: ErrorTone
  title: string
  description: string
  canRetry: boolean
  /** Set when the only way forward is re-authenticating. */
  needsSignIn?: boolean
}

const streamErrors: Record<StreamErrorCode, ErrorDescription> = {
  retrieval_failed: {
    tone: 'failure',
    title: 'Filing search failed',
    description: 'The corpus could not be searched, so this question went unanswered.',
    canRetry: true,
  },
  grounding_failed: {
    tone: 'withheld',
    title: 'Answer withheld',
    description:
      'The assistant produced an answer its own evidence could not support, so it was discarded. Try narrowing the question to a specific filing or period.',
    canRetry: true,
  },
  processing_failed: {
    tone: 'failure',
    title: 'Something went wrong',
    description: 'The answer could not be generated. Your question is unchanged.',
    canRetry: true,
  },
}

export function isStreamErrorCode(value: unknown): value is StreamErrorCode {
  return STREAM_ERROR_CODES.includes(value as StreamErrorCode)
}

export function describeStreamError(code: StreamErrorCode): ErrorDescription {
  return streamErrors[code]
}

/**
 * Maps transport failures to recovery guidance. Backend exception text is never
 * read off the error — only its shape.
 */
export function describeError(error: unknown): ErrorDescription {
  if (error instanceof ApiError) {
    if (error.isNetworkError) {
      return {
        tone: 'offline',
        title: "Can't reach the backend",
        description:
          'The request never arrived. Check that the API is running and reachable, then try again.',
        canRetry: true,
      }
    }
    if (error.status === 401) {
      return {
        tone: 'failure',
        title: 'Your session expired',
        description: 'Sign in again to keep working. Your chats are saved.',
        canRetry: false,
        needsSignIn: true,
      }
    }
    if (error.status === 403 || error.status === 404) {
      return {
        tone: 'failure',
        title: 'This chat is not available',
        description: 'It was removed, or it belongs to another account.',
        canRetry: false,
      }
    }
  }

  return {
    tone: 'failure',
    title: 'Something went wrong',
    description: 'The request could not be completed. Try again in a moment.',
    canRetry: true,
  }
}
