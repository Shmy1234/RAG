import { motion, useReducedMotion } from 'motion/react'
import { useState } from 'react'

import { Logo } from '@/components/brand/Logo'
import { Cite, Eyebrow } from '@/components/home/evidence-parts'
import { StartLink } from '@/components/home/StartLink'

const QUESTION = 'how did nvidia describe data center demand in 2023 vs 2024?'

/** Each clause ends on the citation that supports it — the point of the demo. */
const CLAUSES = [
  {
    text: 'Management attributed the increase to accelerating demand for its data center platforms',
    cite: 1,
    after: ',',
  },
  {
    text: 'and pointed to supply constraints easing through the year',
    cite: 2,
    after: '.',
  },
]

const SOURCES = [
  {
    n: 1,
    label: '10-K FY2024 · Item 7 · p.31',
    lead: 'Revenue for the segment increased year over year. ',
    quote:
      'The increase reflects accelerating demand for our data center computing platforms across cloud and enterprise customers.',
    tail: ' Gross margin improved over the same period.',
  },
  {
    n: 2,
    label: '10-K FY2024 · Item 7 · p.32',
    lead: 'Shipments were constrained in the prior year. ',
    quote:
      'Supply constraints eased through the period as additional capacity came online with our manufacturing partners.',
    tail: ' We expect capacity to continue expanding.',
  },
]

type Token =
  | { kind: 'word'; order: number; text: string }
  | { kind: 'cite'; order: number; n: number; after: string }

/** Flattened once at module scope: the answer composes word by word, chip last. */
const TOKENS: Token[] = CLAUSES.flatMap((clause, clauseIndex) => {
  const offset = CLAUSES.slice(0, clauseIndex).reduce(
    (total, previous) => total + previous.text.split(' ').length + 1,
    0,
  )
  const words = clause.text.split(' ')

  return [
    ...words.map((text, index) => ({ kind: 'word' as const, order: offset + index, text })),
    { kind: 'cite' as const, order: offset + words.length, n: clause.cite, after: clause.after },
  ]
})

function AnswerText({ onSelect }: { onSelect: (n: number) => void }) {
  const reducedMotion = useReducedMotion()

  return (
    <p className="text-[0.9375rem] leading-relaxed">
      {TOKENS.map((token) =>
        token.kind === 'word' ? (
          <motion.span
            animate={{ opacity: 1, y: 0 }}
            initial={reducedMotion ? false : { opacity: 0, y: '0.3em' }}
            key={token.order}
            transition={{ delay: 0.5 + token.order * 0.02, duration: 0.35 }}
          >
            {token.text}{' '}
          </motion.span>
        ) : (
          <span key={token.order}>
            <motion.button
              animate={{ opacity: 1, scale: 1 }}
              className="cursor-pointer rounded-sm outline-none focus-visible:ring-2 focus-visible:ring-ring"
              initial={reducedMotion ? false : { opacity: 0, scale: 0.6 }}
              onClick={() => onSelect(token.n)}
              onFocus={() => onSelect(token.n)}
              onMouseEnter={() => onSelect(token.n)}
              transition={{ delay: 0.65 + token.order * 0.02, duration: 0.3 }}
              type="button"
            >
              <Cite n={token.n} />
              <span className="sr-only">{`Show source ${token.n}`}</span>
            </motion.button>
            {token.after}{' '}
          </span>
        ),
      )}
    </p>
  )
}

function SourceExcerpt({ n }: { n: number }) {
  const reducedMotion = useReducedMotion()
  const source = SOURCES.find((item) => item.n === n) ?? SOURCES[0]

  return (
    <motion.div
      animate={{ opacity: 1, y: 0 }}
      className="mt-5 border-t border-border pt-4"
      initial={reducedMotion ? false : { opacity: 0, y: 6 }}
      key={source.n}
      transition={{ duration: 0.25 }}
    >
      <Eyebrow className="block">{source.label}</Eyebrow>
      <p className="mt-2 text-[0.8125rem] leading-relaxed text-muted-foreground">
        {source.lead}
        <span className="bg-highlight text-paper-foreground">{source.quote}</span>
        {source.tail}
      </p>
    </motion.div>
  )
}

export function Hero() {
  const [activeSource, setActiveSource] = useState(1)
  const reducedMotion = useReducedMotion()

  return (
    <header className="mx-auto max-w-7xl px-6 pt-6 pb-16">
      {/* Deliberately not a nav bar: a mark, a way in, and nothing else. */}
      <div className="flex items-center justify-between">
        <Logo />
        <StartLink size="sm" variant="ghost">
          Sign in
        </StartLink>
      </div>

      {/* Title Case in a monospace face is far wider than lowercase, so the
          headline takes the full column rather than sharing a row with the demo. */}
      <h1 className="mt-12 font-display text-[clamp(1.375rem,7vw,6rem)] leading-[1.05] font-medium tracking-[-0.04em] lg:mt-16">
        {'Specify the Filing. '}
        <br />
        Get the Passage Back.
      </h1>

      <div className="mt-12 grid gap-10 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.15fr)] lg:gap-16">
        {/* Stretches to the demo card's height so the two columns share a top
            and bottom edge: copy pinned to the top, actions to the bottom. */}
        <div className="flex flex-col justify-between gap-8">
          <p className="text-lg leading-relaxed text-muted-foreground lg:text-xl">
            Document Copilot answers questions about SEC filings from massive corporations like NVIDIA, AMD, and Intel, etc. 
            Built for the part of the job where you have to defend your answer from the reviewer. 
            Quickly get the passage you need to defend your answer. 
            Sign in to run it against the corpus. See how it works below. 
          </p>
          <div className="flex flex-wrap items-center gap-3">
            <StartLink className="h-11 px-5 text-sm" size="lg">
              Start asking
            </StartLink>
            <a
              className="font-display text-xs tracking-wide text-muted-foreground underline-offset-4 hover:text-foreground hover:underline"
              href="#how-it-works"
            >
              See How It Works ↓
            </a>
          </div>
        </div>

        <motion.div
          animate={{ opacity: 1, y: 0 }}
          className="rounded-xl bg-paper p-6 text-paper-foreground shadow-sm ring-1 ring-border"
          initial={reducedMotion ? false : { opacity: 0, y: 16 }}
          transition={{ duration: 0.5 }}
        >
          <div className="flex items-baseline justify-between border-b border-border pb-3">
            <Eyebrow>Example</Eyebrow>
            <Eyebrow>Hover a citation</Eyebrow>
          </div>
          <p className="mt-4 font-display text-[0.8125rem] leading-relaxed text-muted-foreground">
            <span className="text-foreground">{'> '}</span>
            {QUESTION}
          </p>
          <div className="mt-4">
            <AnswerText onSelect={setActiveSource} />
          </div>
          <SourceExcerpt n={activeSource} />
          <p className="mt-4 font-display text-[10px] tracking-wide text-muted-foreground">
            Illustrative example. Sign in to run it against the corpus.
          </p>
        </motion.div>
      </div>
    </header>
  )
}
