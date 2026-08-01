import { AlertTriangle, RefreshCw, ShieldAlert, WifiOff, type LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

export type ErrorTone = 'failure' | 'withheld' | 'offline'

const icons: Record<ErrorTone, LucideIcon> = {
  failure: AlertTriangle,
  withheld: ShieldAlert,
  offline: WifiOff,
}

type ErrorNoticeProps = {
  tone?: ErrorTone
  title: string
  description: string
  onRetry?: () => void
  retryLabel?: string
  action?: ReactNode
  className?: string
}

/**
 * Errors state what happened and how to fix it. `withheld` is deliberately not
 * destructive-red: a refused answer is the grounding contract working, not a fault.
 */
export function ErrorNotice({
  tone = 'failure',
  title,
  description,
  onRetry,
  retryLabel = 'Try again',
  action,
  className,
}: ErrorNoticeProps) {
  const Icon = icons[tone]

  return (
    <div
      className={cn(
        'flex gap-3 rounded-lg border p-3.5',
        tone === 'failure' && 'border-destructive/30 bg-destructive/5',
        tone !== 'failure' && 'bg-muted/40',
        className,
      )}
      role="alert"
    >
      <Icon
        aria-hidden
        className={cn(
          'mt-0.5 size-4 shrink-0',
          tone === 'failure' ? 'text-destructive' : 'text-muted-foreground',
        )}
      />
      <div className="min-w-0 flex-1">
        <p className="font-medium">{title}</p>
        <p className="mt-0.5 text-muted-foreground">{description}</p>
        {onRetry || action ? (
          <div className="mt-2.5 flex items-center gap-2">
            {onRetry ? (
              <Button onClick={onRetry} size="sm" type="button" variant="outline">
                <RefreshCw />
                {retryLabel}
              </Button>
            ) : null}
            {action}
          </div>
        ) : null}
      </div>
    </div>
  )
}
