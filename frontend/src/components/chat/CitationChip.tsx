import { forwardRef } from 'react'

import { FilingMeta } from '@/components/common/FilingMeta'
import { HoverCard, HoverCardContent, HoverCardTrigger } from '@/components/ui/hover-card'
import type { Citation } from '@/lib/chat-api'
import { cn } from '@/lib/utils'

type CitationChipProps = {
  citation: Citation
  selected: boolean
  onSelect: () => void
}

/**
 * Hover previews the evidence; click opens the rail. The preview exists so the
 * common case — a quick sanity check — never costs a panel open.
 */
export const CitationChip = forwardRef<HTMLButtonElement, CitationChipProps>(
  function CitationChip({ citation, selected, onSelect }, ref) {
    return (
      <HoverCard>
        <HoverCardTrigger
          render={
            <button
              aria-pressed={selected}
              className={cn(
                'inline-flex max-w-full items-center gap-1.5 rounded-md border px-2 py-1 font-mono text-[0.6875rem] transition-colors',
                'focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none',
                selected
                  ? 'border-foreground/25 bg-foreground text-background'
                  : 'text-muted-foreground hover:bg-muted hover:text-foreground',
              )}
              onClick={onSelect}
              ref={ref}
              type="button"
            >
              <span
                className={cn(
                  'tabular-nums',
                  selected ? 'text-background/70' : 'text-muted-foreground/70',
                )}
              >
                {citation.citation_index + 1}
              </span>
              <span className="truncate">
                {citation.citation_label} · {citation.location_label}
              </span>
            </button>
          }
        />
        <HoverCardContent align="start" className="w-80 space-y-2" side="top">
          <FilingMeta
            citationLabel={citation.citation_label}
            locationLabel={citation.location_label}
          />
          <blockquote className="border-l-2 pl-2.5 text-[0.8125rem] leading-relaxed">
            <span className="line-clamp-3">{citation.quoted_text}</span>
          </blockquote>
          <p className="text-[0.6875rem] text-muted-foreground">Click to open the full passage</p>
        </HoverCardContent>
      </HoverCard>
    )
  },
)
