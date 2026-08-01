import { Plus } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import type { ChatThread } from '@/lib/chat-api'

type ThreadSidebarProps = {
  threads: ChatThread[]
  creating: boolean
  onCreateThread: () => Promise<void>
}

export function ThreadSidebar({ threads, creating, onCreateThread }: ThreadSidebarProps) {
  const { threadId } = useParams()

  return (
    <aside className="flex h-full w-72 shrink-0 flex-col border-r bg-background">
      <div className="flex h-14 items-center justify-between border-b px-4">
        <span className="text-sm font-medium">Chats</span>
        <Button
          aria-label="New chat"
          title="New chat"
          size="sm"
          variant="outline"
          onClick={() => void onCreateThread()}
          disabled={creating}
        >
          <Plus className="size-4" />
        </Button>
      </div>
      <nav className="flex-1 overflow-y-auto p-2">
        {threads.map((thread) => (
          <Link
            key={thread.id}
            to={`/app/chats/${thread.id}`}
            className={
              thread.id === threadId
                ? 'mb-1 block rounded-md bg-muted px-3 py-2 text-left text-sm font-medium'
                : 'mb-1 block rounded-md px-3 py-2 text-left text-sm text-muted-foreground hover:bg-muted'
            }
          >
            {thread.title || 'Untitled chat'}
          </Link>
        ))}
      </nav>
    </aside>
  )
}
