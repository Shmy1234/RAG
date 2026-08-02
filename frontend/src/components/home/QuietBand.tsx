import { motion, useReducedMotion } from 'motion/react'

import { Eyebrow } from '@/components/home/evidence-parts'

const ITEMS = [
  {
    label: 'Threads persist',
    body: 'Every conversation is saved to your account with the sources it used. Come back to a question from last quarter and the trail is still attached to it.',
  },
  {
    label: 'Evidence stays open',
    body: 'A panel beside the answer shows the retrieved passages, how they scored, and the filing each one came from.',
  },
  {
    label: 'One curated corpus',
    body: 'SEC filings, ingested and chunked ahead of time. You are searching documents prepared for retrieval, not a live web index.',
  },
]

export function QuietBand() {
  const reducedMotion = useReducedMotion()

  return (
    <section className="border-y border-border">
      <div className="mx-auto grid max-w-7xl divide-y divide-border md:grid-cols-3 md:divide-x md:divide-y-0">
        {ITEMS.map((item, index) => (
          <motion.div
            className="px-8 py-10"
            initial={reducedMotion ? false : { opacity: 0, y: 12 }}
            key={item.label}
            transition={{ delay: index * 0.08, duration: 0.5 }}
            viewport={{ once: true, margin: '-15%' }}
            whileInView={{ opacity: 1, y: 0 }}
          >
            <Eyebrow className="block">{item.label}</Eyebrow>
            <p className="mt-3 text-[0.9375rem] leading-relaxed text-muted-foreground">
              {item.body}
            </p>
          </motion.div>
        ))}
      </div>
    </section>
  )
}
