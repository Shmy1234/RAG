import { cn } from '@/lib/utils'

/** Stand-in body text. Widths vary so a block reads as prose, not as a placeholder. */
function Lines({ widths, className }: { widths: number[]; className?: string }) {
  return (
    <div className={cn('space-y-1.5', className)}>
      {widths.map((width, index) => (
        <div
          className="h-1.5 rounded-full bg-current opacity-15"
          key={index}
          style={{ width: `${width}%` }}
        />
      ))}
    </div>
  )
}

export function Eyebrow({ children, className }: { children: string; className?: string }) {
  return (
    <span
      className={cn(
        'font-display text-[10px] tracking-[0.18em] text-muted-foreground uppercase',
        className,
      )}
    >
      {children}
    </span>
  )
}

function Sheet({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div
      className={cn(
        'rounded-lg bg-paper p-5 text-paper-foreground shadow-sm ring-1 ring-border',
        className,
      )}
    >
      {children}
    </div>
  )
}

/** Beat 01 — the whole filing, before anything has been done to it. */
export function FilingSheet({ className }: { className?: string }) {
  return (
    <Sheet className={className}>
      <div className="mb-4 flex items-baseline justify-between border-b border-border pb-2">
        <Eyebrow>10-K · FY2024</Eyebrow>
        <Eyebrow>Item 7</Eyebrow>
      </div>
      <Lines widths={[96, 88, 92, 74, 90, 85, 96, 62]} />
      <div className="my-4 h-px bg-border" />
      <Lines widths={[90, 94, 78, 88, 92, 70, 84, 96, 58]} />
    </Sheet>
  )
}

const CHUNKS = [
  { id: '0041', widths: [92, 78, 86] },
  { id: '0042', widths: [88, 94, 64] },
  { id: '0043', widths: [96, 70, 82] },
  { id: '0044', widths: [74, 90, 88] },
  { id: '0045', widths: [90, 84, 72] },
  { id: '0046', widths: [86, 92, 60] },
]

/** Beat 02 — the same document, split, each piece still knowing its origin. */
export function ChunkGrid({ className }: { className?: string }) {
  return (
    <div className={cn('grid grid-cols-2 gap-3', className)}>
      {CHUNKS.map((chunk) => (
        <Sheet className="p-3" key={chunk.id}>
          <Eyebrow className="mb-2 block">{`§${chunk.id} · p.31`}</Eyebrow>
          <Lines widths={chunk.widths} />
        </Sheet>
      ))}
    </div>
  )
}

const RANKED = [
  { score: '0.91', source: 'Item 7 · p.31', width: 91, hit: true },
  { score: '0.87', source: 'Item 7 · p.32', width: 87, hit: true },
  { score: '0.52', source: 'Item 1A · p.14', width: 52, hit: false },
  { score: '0.38', source: 'Item 8 · p.58', width: 38, hit: false },
]

/** Beat 03 — retrieval, scored. The two that clear the bar get highlighted. */
export function RankedList({ className }: { className?: string }) {
  return (
    <Sheet className={cn('space-y-2', className)}>
      <div className="mb-3 flex items-baseline justify-between border-b border-border pb-2">
        <Eyebrow>Ranked passages</Eyebrow>
        <Eyebrow>Vector + full text</Eyebrow>
      </div>
      {RANKED.map((row) => (
        <div
          className={cn(
            'flex items-center gap-3 rounded px-2 py-2 transition-colors',
            row.hit && 'bg-highlight',
          )}
          key={row.source}
        >
          <span className="font-display text-xs tabular-nums">{row.score}</span>
          <span className="font-display text-[10px] tracking-wide text-muted-foreground">
            {row.source}
          </span>
          <div className="ml-auto h-1 w-24 overflow-hidden rounded-full bg-border">
            <div
              className="h-full rounded-full bg-current opacity-40"
              style={{ width: `${row.width}%` }}
            />
          </div>
        </div>
      ))}
    </Sheet>
  )
}

export function Cite({ n, className }: { n: number; className?: string }) {
  return (
    <sup
      className={cn(
        'ml-0.5 rounded-[3px] bg-highlight px-1 py-px align-super font-display text-[10px] leading-none',
        className,
      )}
    >
      {n}
    </sup>
  )
}

/** Beat 04 — the answer, with every claim still attached to its passage. */
export function AnswerCard({ className }: { className?: string }) {
  return (
    <Sheet className={className}>
      <Eyebrow className="mb-3 block">Answer</Eyebrow>
      <p className="text-sm leading-relaxed">
        Management attributed the increase to accelerating demand for its data center platforms
        <Cite n={1} />, and pointed to supply constraints easing across the year
        <Cite n={2} />.
      </p>
      <div className="mt-4 space-y-2 border-t border-border pt-3">
        {[
          { n: 1, source: '10-K FY2024 · Item 7 · p.31' },
          { n: 2, source: '10-K FY2024 · Item 7 · p.32' },
        ].map((source) => (
          <div className="flex items-center gap-2" key={source.n}>
            <Cite n={source.n} />
            <span className="font-display text-[10px] tracking-wide text-muted-foreground">
              {source.source}
            </span>
          </div>
        ))}
      </div>
    </Sheet>
  )
}
