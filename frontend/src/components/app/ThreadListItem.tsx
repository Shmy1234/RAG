import { Trash2 } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogTitle,
} from '@/components/ui/alert-dialog'
import { SidebarMenuAction, SidebarMenuButton, SidebarMenuItem } from '@/components/ui/sidebar'
import type { ChatThread } from '@/lib/chat-api'

type ThreadListItemProps = {
  thread: ChatThread
  active: boolean
  running: boolean
  onDelete: (threadId: string) => void
}

export function ThreadListItem({ thread, active, running, onDelete }: ThreadListItemProps) {
  const [confirming, setConfirming] = useState(false)
  const title = thread.title || 'New chat'

  return (
    <SidebarMenuItem>
      <SidebarMenuButton isActive={active} render={<Link to={`/app/chats/${thread.id}`} />}>
        {/* The parent only truncates its last span, so the title owns both
            truncation and the shrinking that keeps the dot in view. */}
        <span className="min-w-0 flex-1 truncate">{title}</span>
        {running ? (
          <span
            aria-label="Answering"
            className="size-1.5 shrink-0 animate-pulse rounded-full bg-primary transition-opacity group-focus-within/menu-item:opacity-0 group-hover/menu-item:opacity-0"
            role="status"
          />
        ) : null}
      </SidebarMenuButton>

      <SidebarMenuAction
        aria-label={`Delete ${title}`}
        onClick={() => setConfirming(true)}
        showOnHover
      >
        <Trash2 />
      </SidebarMenuAction>

      <AlertDialog onOpenChange={setConfirming} open={confirming}>
        <AlertDialogContent>
          <AlertDialogTitle>Delete this chat?</AlertDialogTitle>
          <AlertDialogDescription>
            {running
              ? `"${title}" is still answering. Deleting it stops the run and removes its messages and citations. This cannot be undone.`
              : `"${title}" and all of its messages and citations will be removed. This cannot be undone.`}
          </AlertDialogDescription>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={() => onDelete(thread.id)}>Delete</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </SidebarMenuItem>
  )
}
