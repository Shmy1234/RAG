import { Link } from 'react-router-dom'
import type { VariantProps } from 'class-variance-authority'

import { useAuth } from '@/auth/auth-context'
import { buttonVariants } from '@/components/ui/button'
import { cn } from '@/lib/utils'

type StartLinkProps = VariantProps<typeof buttonVariants> & {
  children: string
  className?: string
}

/**
 * Every call to action on the page routes the same way: to the workspace if you
 * already have a session, to sign-in if you don't. Signed-in visitors see one
 * label everywhere, so the action keeps its name across the whole page.
 */
export function StartLink({ children, className, size, variant }: StartLinkProps) {
  const { session } = useAuth()

  return (
    <Link
      className={cn(buttonVariants({ size, variant }), className)}
      to={session ? '/app' : '/sign-in'}
    >
      {session ? 'Open workspace' : children}
    </Link>
  )
}
