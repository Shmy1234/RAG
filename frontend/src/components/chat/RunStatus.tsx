import { Check } from 'lucide-react'

import type { RunStage } from '@/lib/chat-api'
import { cn } from '@/lib/utils'

type RunStatusProps = {
  stages: readonly RunStage[]
}

/** Copy lives here, not on the wire: the backend sends identifiers only. */
const labels: Record<RunStage, string> = {
  routing: 'Choosing the fastest answer path',
  searching: 'Searching filings',
  analyzing: 'Reading the evidence',
  validating: 'Checking every citation',
  saving: 'Saving the answer',
}

export function RunStatus({ stages }: RunStatusProps) {
  const current = stages.length - 1

  return (
    <div aria-live="polite" className="flex flex-wrap items-center gap-x-3 gap-y-1" role="status">
      {stages.map((item, index) => {
        const done = index < current
        const active = index === current

        return (
          <span
            className={cn(
              'inline-flex items-center gap-1.5 text-[0.8125rem]',
              active ? 'text-foreground' : 'text-muted-foreground',
            )}
            key={item}
          >
            {done ? (
              <Check aria-hidden className="size-3" />
            ) : (
              <span
                aria-hidden
                className="size-1.5 animate-pulse rounded-full bg-foreground"
              />
            )}
            {labels[item]}
          </span>
        )
      })}
      {stages.length === 0 ? (
        <span className="text-[0.8125rem] text-muted-foreground">Working…</span>
      ) : null}
    </div>
  )
}
