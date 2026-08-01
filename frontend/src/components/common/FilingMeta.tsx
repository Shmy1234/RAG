import { formatFilingDate } from '@/lib/format'
import { cn } from '@/lib/utils'

type FilingMetaProps = {
  citationLabel: string
  locationLabel?: string
  filingDate?: string
  className?: string
}

/**
 * The filing stamp. Monospace and dot-separated so an identity reads as a record
 * rather than a sentence — the one place this UI borrows the vocabulary of EDGAR.
 */
export function FilingMeta({
  citationLabel,
  locationLabel,
  filingDate,
  className,
}: FilingMetaProps) {
  const parts = [citationLabel, filingDate && formatFilingDate(filingDate), locationLabel].filter(
    (part): part is string => Boolean(part),
  )

  return (
    <p className={cn('font-mono text-[0.6875rem] tracking-tight text-muted-foreground', className)}>
      {parts.join(' · ')}
    </p>
  )
}
