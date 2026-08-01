import type { LucideIcon } from 'lucide-react'
import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

type EmptyStateProps = {
  icon: LucideIcon
  title: string
  description: string
  children?: ReactNode
  className?: string
}

/** An empty screen is an invitation to act, so every one of these ends in an action. */
export function EmptyState({
  icon: Icon,
  title,
  description,
  children,
  className,
}: EmptyStateProps) {
  return (
    <div className={cn('flex flex-col items-center justify-center px-6 py-12 text-center', className)}>
      <div className="mb-4 rounded-full border bg-muted/40 p-3">
        <Icon aria-hidden className="size-5 text-muted-foreground" />
      </div>
      <h2 className="text-base font-medium">{title}</h2>
      <p className="mt-1 max-w-sm text-muted-foreground">{description}</p>
      {children ? <div className="mt-6 w-full max-w-md">{children}</div> : null}
    </div>
  )
}
