import { MessageSquarePlus, Search } from 'lucide-react'
import { useMemo, useState } from 'react'
import { useParams } from 'react-router-dom'

import { ThreadListItem } from '@/components/app/ThreadListItem'
import { UserMenu } from '@/components/app/UserMenu'
import { LogoMark } from '@/components/brand/Logo'
import { Skeleton } from '@/components/ui/skeleton'
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInput,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarRail,
  SidebarTrigger,
  useSidebar,
} from '@/components/ui/sidebar'
import type { ChatThread } from '@/lib/chat-api'
import { groupThreadsByRecency } from '@/lib/format'

type AppSidebarProps = {
  threads: ChatThread[]
  loading: boolean
  creating: boolean
  runningThreadIds: ReadonlySet<string>
  onCreateThread: () => void
  onDeleteThread: (threadId: string) => void
}

export function AppSidebar({
  threads,
  loading,
  creating,
  runningThreadIds,
  onCreateThread,
  onDeleteThread,
}: AppSidebarProps) {
  const { threadId } = useParams()
  const { state } = useSidebar()
  const [query, setQuery] = useState('')
  const collapsed = state === 'collapsed'

  const groups = useMemo(() => {
    const term = query.trim().toLowerCase()
    const matched = term
      ? threads.filter((thread) => (thread.title ?? '').toLowerCase().includes(term))
      : threads
    return groupThreadsByRecency(matched)
  }, [threads, query])

  return (
    <Sidebar collapsible="icon">
      <SidebarHeader>
        <div className="flex items-center gap-2 px-1 py-0.5 group-data-[collapsible=icon]:px-0">
          <div className="flex size-7 shrink-0 items-center justify-center rounded-md bg-primary text-primary-foreground">
            <LogoMark className="size-3.5" />
          </div>
          <span className="min-w-0 flex-1 truncate font-medium group-data-[collapsible=icon]:hidden">
            Document Copilot
          </span>
          <SidebarTrigger className="group-data-[collapsible=icon]:hidden" />
        </div>

        <SidebarMenu>
          <SidebarMenuItem>
            <SidebarMenuButton
              disabled={creating}
              onClick={onCreateThread}
              tooltip="New chat"
              variant="outline"
            >
              <MessageSquarePlus />
              <span>New chat</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>

        {collapsed ? (
          <SidebarMenu>
            <SidebarMenuItem>
              <SidebarTrigger
                render={
                  <SidebarMenuButton tooltip="Search chats">
                    <Search />
                    <span>Search</span>
                  </SidebarMenuButton>
                }
              />
            </SidebarMenuItem>
          </SidebarMenu>
        ) : (
          <div className="relative">
            <Search
              aria-hidden
              className="pointer-events-none absolute top-1/2 left-2 size-3.5 -translate-y-1/2 text-muted-foreground"
            />
            <SidebarInput
              aria-label="Search chats"
              className="pl-7"
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search chats"
              value={query}
            />
          </div>
        )}
      </SidebarHeader>

      <SidebarContent className="group-data-[collapsible=icon]:hidden">
        {loading ? (
          <SidebarGroup>
            <SidebarGroupContent className="space-y-1.5 px-2">
              {[70, 90, 55, 80].map((width, index) => (
                <Skeleton key={index} className="h-7" style={{ width: `${width}%` }} />
              ))}
            </SidebarGroupContent>
          </SidebarGroup>
        ) : groups.length === 0 ? (
          <p className="px-4 py-3 text-muted-foreground">
            {query.trim() ? 'No chats match that search.' : 'No chats yet.'}
          </p>
        ) : (
          groups.map((group) => (
            <SidebarGroup key={group.label}>
              <SidebarGroupLabel>{group.label}</SidebarGroupLabel>
              <SidebarGroupContent>
                <SidebarMenu>
                  {group.threads.map((thread) => (
                    <ThreadListItem
                      active={thread.id === threadId}
                      key={thread.id}
                      onDelete={onDeleteThread}
                      running={runningThreadIds.has(thread.id)}
                      thread={thread}
                    />
                  ))}
                </SidebarMenu>
              </SidebarGroupContent>
            </SidebarGroup>
          ))
        )}
      </SidebarContent>

      <SidebarFooter>
        <UserMenu />
      </SidebarFooter>
      <SidebarRail />
    </Sidebar>
  )
}
