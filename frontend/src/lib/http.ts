import { env } from '@/lib/env'
import { supabase } from '@/lib/supabase'

const DEFAULT_TIMEOUT_MS = 15_000

export type RequestOptions = Omit<RequestInit, 'body'> & {
  body?: BodyInit | Record<string, unknown> | unknown[] | null
  timeoutMs?: number
}

export class ApiError extends Error {
  readonly status?: number
  readonly body?: unknown
  readonly isNetworkError: boolean

  constructor(
    message: string,
    options: { status?: number; body?: unknown; isNetworkError?: boolean } = {},
  ) {
    super(message)
    this.name = 'ApiError'
    this.status = options.status
    this.body = options.body
    this.isNetworkError = options.isNetworkError ?? false
  }
}

function isJsonBody(body: RequestOptions['body']): body is Record<string, unknown> | unknown[] {
  return typeof body === 'object' && body !== null && !(body instanceof Blob) && !(body instanceof FormData) && !(body instanceof ArrayBuffer)
}

async function parseResponse(response: Response): Promise<unknown> {
  if (response.status === 204) return undefined
  const text = await response.text()
  if (!text) return undefined
  if (response.headers.get('content-type')?.includes('application/json')) {
    try {
      return JSON.parse(text) as unknown
    } catch {
      return text
    }
  }
  return text
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { body, timeoutMs = DEFAULT_TIMEOUT_MS, ...init } = options
  const headers = new Headers(init.headers)
  const { data } = await supabase.auth.getSession()
  if (data.session?.access_token) {
    headers.set('Authorization', `Bearer ${data.session.access_token}`)
  }

  let requestBody: BodyInit | undefined
  if (isJsonBody(body)) {
    requestBody = JSON.stringify(body)
    if (!headers.has('Content-Type')) headers.set('Content-Type', 'application/json')
  } else {
    requestBody = body ?? undefined
  }

  const controller = new AbortController()
  const timeout = globalThis.setTimeout(() => controller.abort(), timeoutMs)
  try {
    const response = await fetch(new URL(path, `${env.apiBaseUrl}/`), {
      ...init,
      body: requestBody,
      headers,
      signal: controller.signal,
    })
    const responseBody = await parseResponse(response)
    if (!response.ok) {
      throw new ApiError(`Request failed with status ${response.status}`, {
        status: response.status,
        body: responseBody,
      })
    }
    return responseBody as T
  } catch (error) {
    if (error instanceof ApiError) throw error
    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError('Request timed out', { isNetworkError: true })
    }
    throw new ApiError('Network request failed', { isNetworkError: true })
  } finally {
    globalThis.clearTimeout(timeout)
  }
}
