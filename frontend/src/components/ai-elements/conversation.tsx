import { ArrowDown } from 'lucide-react'
import type { ComponentProps } from 'react'
import { StickToBottom, useStickToBottomContext } from 'use-stick-to-bottom'

import { Button } from '@/components/ui/button'
import { cn } from '@/lib/utils'

/**
 * Scroll container that keeps the newest message pinned while tokens stream, and
 * releases the pin the moment the reader scrolls up to check earlier evidence.
 */
export function Conversation({ className, ...props }: ComponentProps<typeof StickToBottom>) {
  return (
    <StickToBottom
      className={cn('relative flex-1 overflow-y-auto', className)}
      initial="instant"
      resize="smooth"
      role="log"
      {...props}
    />
  )
}

export function ConversationContent({
  className,
  children,
  ...props
}: ComponentProps<typeof StickToBottom.Content>) {
  return (
    <StickToBottom.Content className={cn('p-4', className)} {...props}>
      {children}
    </StickToBottom.Content>
  )
}

export function ConversationScrollButton({ className, ...props }: ComponentProps<typeof Button>) {
  const { isAtBottom, scrollToBottom } = useStickToBottomContext()
  if (isAtBottom) return null

  return (
    <Button
      aria-label="Scroll to latest message"
      className={cn(
        'absolute bottom-4 left-1/2 z-10 -translate-x-1/2 rounded-full shadow-md',
        className,
      )}
      onClick={() => void scrollToBottom()}
      size="icon-sm"
      type="button"
      variant="outline"
      {...props}
    >
      <ArrowDown />
    </Button>
  )
}
