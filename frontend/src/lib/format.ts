import type { ChatThread } from '@/lib/chat-api'

const filingDateFormat = new Intl.DateTimeFormat(undefined, {
  year: 'numeric',
  month: 'short',
  day: 'numeric',
})

/** Filing dates arrive as ISO strings; never render one raw. */
export function formatFilingDate(value: string): string {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? value : filingDateFormat.format(date)
}

const TITLE_MAX = 48

/** First line of the opening question, cut at a word boundary. */
export function deriveThreadTitle(text: string): string {
  const firstLine = text.trim().split('\n')[0].trim()
  if (firstLine.length <= TITLE_MAX) return firstLine
  const clipped = firstLine.slice(0, TITLE_MAX)
  const lastSpace = clipped.lastIndexOf(' ')
  return `${(lastSpace > 20 ? clipped.slice(0, lastSpace) : clipped).trimEnd()}…`
}

export type ThreadGroup = {
  label: string
  threads: ChatThread[]
}

const DAY_MS = 86_400_000

function startOfDay(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime()
}

/**
 * Buckets threads by recency so the sidebar reads as a timeline. Threads arrive
 * newest-first from the API, so each bucket keeps that order.
 */
export function groupThreadsByRecency(threads: ChatThread[], now = new Date()): ThreadGroup[] {
  const today = startOfDay(now)
  const buckets: ThreadGroup[] = [
    { label: 'Today', threads: [] },
    { label: 'Yesterday', threads: [] },
    { label: 'Previous 7 days', threads: [] },
    { label: 'Older', threads: [] },
  ]

  for (const thread of threads) {
    const updated = new Date(thread.updated_at).getTime()
    const day = Number.isNaN(updated) ? 0 : startOfDay(new Date(updated))
    const age = today - day
    if (age <= 0) buckets[0].threads.push(thread)
    else if (age <= DAY_MS) buckets[1].threads.push(thread)
    else if (age <= DAY_MS * 7) buckets[2].threads.push(thread)
    else buckets[3].threads.push(thread)
  }

  return buckets.filter((bucket) => bucket.threads.length > 0)
}
