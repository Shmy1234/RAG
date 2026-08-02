import { Link } from 'react-router-dom'

import { Logo } from '@/components/brand/Logo'
import { StartLink } from '@/components/home/StartLink'
import { useAuth } from '@/auth/auth-context'

export function SiteFooter() {
  const { session } = useAuth()

  return (
    <footer className="border-t border-border">
      <div className="mx-auto max-w-7xl px-6 py-12">
        <div className="flex flex-col gap-8 md:flex-row md:items-start md:justify-between">
          <div className="max-w-sm">
            <Logo />
            <p className="mt-4 text-[0.9375rem] leading-relaxed text-muted-foreground">
              Grounded answers over SEC filings, with the passage attached.
            </p>
          </div>

          <div className="flex items-center gap-4">
            <StartLink className="h-11 px-5 text-sm" size="lg">
              Start asking
            </StartLink>
            {session ? null : (
              <Link
                className="font-display text-xs tracking-wide text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
                to="/sign-up"
              >
                Create an Account
              </Link>
            )}
          </div>
        </div>

        <p className="mt-10 font-display text-[10px] tracking-[0.18em] text-muted-foreground uppercase">
          {`© ${new Date().getFullYear()} Document Copilot`}
        </p>
      </div>
    </footer>
  )
}
