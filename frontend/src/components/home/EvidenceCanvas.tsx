import { motion, useReducedMotion } from 'motion/react'
import { useCallback, useEffect, useRef, useState } from 'react'

import {
  AnswerCard,
  ChunkGrid,
  Eyebrow,
  FilingSheet,
  RankedList,
} from '@/components/home/evidence-parts'
import { cn } from '@/lib/utils'

/**
 * Four beats of one pipeline. The numbering is load-bearing here — order is the
 * information — which is why it appears in this section and nowhere else.
 */
const BEATS = [
  {
    n: '01',
    title: 'The Filing',
    body: 'A 10-K runs a few hundred pages. The answer is in two paragraphs of it. Ingestion keeps the whole document rather than a summary of it, so nothing is lost before you ask.',
    Stage: FilingSheet,
  },
  {
    n: '02',
    title: 'Split in Place',
    body: 'Each chunk keeps the filing, the item, and the page it came from. That provenance is what makes a citation possible later — it is recorded at ingest, not reconstructed at answer time.',
    Stage: ChunkGrid,
  },
  {
    n: '03',
    title: 'Retrieved Two Ways',
    body: 'Vector search finds passages that mean the same thing. Full-text search finds the ones that say it. Both run against the corpus, and the results are ranked together.',
    Stage: RankedList,
  },
  {
    n: '04',
    title: 'Answered with Sources',
    body: 'Every claim carries the passage it came from. Open a citation and you are reading the filing itself, not a paraphrase of it.',
    Stage: AnswerCard,
  },
]

/** The pinned layout needs real horizontal room; below this it degrades to a stack. */
function useIsWide() {
  const [isWide, setIsWide] = useState(false)

  useEffect(() => {
    const query = window.matchMedia('(min-width: 1024px)')
    const update = () => setIsWide(query.matches)
    update()
    query.addEventListener('change', update)
    return () => query.removeEventListener('change', update)
  }, [])

  return isWide
}

/**
 * The beat whose copy crosses the middle of the viewport is the active one, and
 * it drives both the copy and the canvas — they cannot drift apart. Measured
 * directly rather than with IntersectionObserver, which reports incoherently
 * when the page jumps several viewports at once (anchor links, restored scroll).
 */
function useActiveBeat(blocks: React.RefObject<(HTMLDivElement | null)[]>) {
  const [activeBeat, setActiveBeat] = useState(0)

  useEffect(() => {
    let frame = 0

    const measure = () => {
      frame = 0
      const centre = window.innerHeight / 2
      let next = 0
      blocks.current.forEach((block, index) => {
        if (!block) return
        const rect = block.getBoundingClientRect()
        if (rect.top <= centre && rect.bottom > centre) next = index
      })
      setActiveBeat(next)
    }

    const schedule = () => {
      if (!frame) frame = requestAnimationFrame(measure)
    }

    measure()
    window.addEventListener('scroll', schedule, { passive: true })
    window.addEventListener('resize', schedule)
    return () => {
      window.removeEventListener('scroll', schedule)
      window.removeEventListener('resize', schedule)
      if (frame) cancelAnimationFrame(frame)
    }
  }, [blocks])

  return activeBeat
}

function BeatCopy({
  beat,
  active,
  attach,
}: {
  beat: (typeof BEATS)[number]
  active: boolean
  attach: (block: HTMLDivElement | null) => void
}) {
  return (
    <div className="flex min-h-[72svh] flex-col justify-center" ref={attach}>
      <motion.div
        animate={{ opacity: active ? 1 : 0.3 }}
        className="max-w-lg"
        initial={false}
        transition={{ duration: 0.4 }}
      >
        <Eyebrow className="block">{beat.n}</Eyebrow>
        <h2 className="mt-3 font-display text-3xl font-medium tracking-tight">{beat.title}</h2>
        <p className="mt-4 text-[0.9375rem] leading-relaxed text-muted-foreground">{beat.body}</p>
      </motion.div>
    </div>
  )
}

function PinnedEvidence() {
  const blocks = useRef<(HTMLDivElement | null)[]>([])
  const activeBeat = useActiveBeat(blocks)

  const attach = useCallback(
    (index: number) => (block: HTMLDivElement | null) => {
      blocks.current[index] = block
    },
    [],
  )

  return (
    <div className="mx-auto grid max-w-7xl grid-cols-2 gap-16 px-6">
      <div>
        {BEATS.map((beat, index) => (
          <BeatCopy
            active={index === activeBeat}
            attach={attach(index)}
            beat={beat}
            key={beat.n}
          />
        ))}
      </div>

      <div aria-hidden="true">
        <div className="sticky top-0 flex h-svh items-center">
          <div className="relative min-h-[34rem] w-full">
            {BEATS.map((beat, index) => {
              const active = index === activeBeat
              return (
                <div className="absolute inset-0 flex items-center" key={beat.n}>
                  <motion.div
                    animate={{
                      opacity: active ? 1 : 0,
                      scale: active ? 1 : 0.97,
                      y: active ? 0 : index < activeBeat ? -32 : 32,
                    }}
                    className="w-full"
                    initial={false}
                    transition={{ duration: 0.45, ease: 'easeOut' }}
                  >
                    <beat.Stage />
                  </motion.div>
                </div>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}

/** Narrow screens and reduced-motion readers get the same four states, stacked. */
function StackedEvidence() {
  return (
    <div className="mx-auto max-w-xl space-y-12 px-6">
      {BEATS.map((beat) => (
        <div key={beat.n}>
          <Eyebrow className="block">{beat.n}</Eyebrow>
          <h2 className="mt-2 font-display text-2xl font-medium tracking-tight">{beat.title}</h2>
          <p className="mt-3 text-[0.9375rem] leading-relaxed text-muted-foreground">{beat.body}</p>
          <beat.Stage className="mt-6" />
        </div>
      ))}
    </div>
  )
}

export function EvidenceCanvas({ className }: { className?: string }) {
  const isWide = useIsWide()
  const reducedMotion = useReducedMotion()

  return (
    <section className={cn('py-12', className)} id="how-it-works">
      {isWide && !reducedMotion ? <PinnedEvidence /> : <StackedEvidence />}
    </section>
  )
}
