import { cn } from '@/lib/utils'

/**
 * The monogram: a D followed by a squared C — which is also a citation bracket.
 * Monoline, square caps, one stroke weight, legible down to 16px.
 * Strokes use currentColor so it inherits whatever surface it sits on.
 */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg
      aria-hidden="true"
      className={cn('size-6', className)}
      fill="none"
      stroke="currentColor"
      strokeLinecap="square"
      strokeWidth={2}
      viewBox="0 0 24 24"
    >
      <path d="M3 5v14" />
      <path d="M3 5h4a7 7 0 0 1 0 14H3" />
      <path d="M21 5h-3v14h3" />
    </svg>
  )
}

export function Logo({ className }: { className?: string }) {
  return (
    <span className={cn('inline-flex items-center gap-2', className)}>
      <LogoMark className="size-5" />
      <span className="font-display text-[0.9375rem] font-medium tracking-tight">
        Document Copilot
      </span>
    </span>
  )
}
