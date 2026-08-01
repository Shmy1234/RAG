import { ArrowUp, Square } from 'lucide-react'
import type { ComponentProps, KeyboardEvent } from 'react'

import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { cn } from '@/lib/utils'

export type PromptInputStatus = 'ready' | 'submitted' | 'streaming' | 'error'

export function PromptInput({ className, ...props }: ComponentProps<'form'>) {
  return (
    <form
      className={cn(
        'rounded-xl border bg-card shadow-sm transition-colors focus-within:border-ring focus-within:ring-3 focus-within:ring-ring/50',
        className,
      )}
      {...props}
    />
  )
}

/**
 * Enter sends, Shift+Enter inserts a newline. Height follows content via the
 * textarea's native `field-sizing-content`, capped by max-height.
 */
export function PromptInputTextarea({
  className,
  onKeyDown,
  ...props
}: ComponentProps<typeof Textarea>) {
  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    onKeyDown?.(event)
    if (event.defaultPrevented) return
    if (event.key !== 'Enter' || event.shiftKey || event.nativeEvent.isComposing) return
    event.preventDefault()
    event.currentTarget.form?.requestSubmit()
  }

  return (
    <Textarea
      className={cn(
        'max-h-48 min-h-0 resize-none border-0 bg-transparent px-3.5 py-3 shadow-none focus-visible:border-0 focus-visible:ring-0 dark:bg-transparent',
        className,
      )}
      onKeyDown={handleKeyDown}
      rows={1}
      {...props}
    />
  )
}

export function PromptInputToolbar({ className, ...props }: ComponentProps<'div'>) {
  return (
    <div className={cn('flex items-center justify-between gap-2 px-2 pb-2', className)} {...props} />
  )
}

type PromptInputSubmitProps = Omit<ComponentProps<typeof Button>, 'onClick'> & {
  status: PromptInputStatus
  onStop: () => void
}

/** One control with two jobs: send when idle, stop while the turn is running. */
export function PromptInputSubmit({ status, onStop, className, ...props }: PromptInputSubmitProps) {
  const running = status === 'submitted' || status === 'streaming'

  if (running) {
    return (
      <Button
        aria-label="Stop generating"
        className={cn('rounded-full', className)}
        onClick={onStop}
        size="icon-sm"
        type="button"
        variant="outline"
        {...props}
      >
        <Square className="size-3 fill-current" />
      </Button>
    )
  }

  return (
    <Button
      aria-label="Send message"
      className={cn('rounded-full', className)}
      size="icon-sm"
      type="submit"
      {...props}
    >
      <ArrowUp />
    </Button>
  )
}
