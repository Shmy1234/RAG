import { Check } from 'lucide-react'

import { RUN_STAGES, type RunStage } from '@/lib/chat-api'
import { cn } from '@/lib/utils'

type RunStatusProps = {
  stage: RunStage | null
}

/** Copy lives here, not on the wire: the backend sends identifiers only. */
const labels: Record<RunStage, string> = {
  searching: 'Searching filings',
  analyzing: 'Reading the evidence',
  validating: 'Checking every citation',
  saving: 'Saving the answer',
}

export function RunStatus({ stage }: RunStatusProps) {
  const current = stage ? RUN_STAGES.indexOf(stage) : -1

  return (
    <div aria-live="polite" className="flex flex-wrap items-center gap-x-3 gap-y-1" role="status">
      {RUN_STAGES.map((item, index) => {
        const done = index < current
        const active = index === current
        if (!done && !active) return null

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
      {current === -1 ? <span className="text-[0.8125rem] text-muted-foreground">Working…</span> : null}
    </div>
  )
}
