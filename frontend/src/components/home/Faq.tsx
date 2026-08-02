import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion'
import { Eyebrow } from '@/components/home/evidence-parts'

const QUESTIONS = [
  {
    q: 'What can I ask about?',
    a: 'A curated corpus of SEC filings, ingested and chunked ahead of time. Questions about what a company said, where it said it, and how that changed between filings are what the retrieval is built for.',
  },
  {
    q: 'How do I check an answer?',
    a: 'Each claim carries a citation to the passage behind it, and the retrieved passages stay open beside the answer with the filing, item, and page they came from. You read the source, not a summary of it.',
  },
  {
    q: 'Where do my chats go?',
    a: 'Into your own account, in Postgres, visible only to you. Threads keep their messages and their sources, so an old question is still answerable months later.',
  },
  {
    q: 'How does retrieval actually work?',
    a: 'Two passes over the same corpus. Vector search over OpenAI embeddings finds passages that mean what you asked; Postgres full-text search finds the ones that use your exact language. The results are ranked together before anything is written.',
  },
  {
    q: 'Can I sign in with Google?',
    a: 'No. Email and password only, through Supabase Auth.',
  },
  {
    q: 'Is there an API?',
    a: 'Not yet. The workspace is the only supported way in today.',
  },
]

export function Faq() {
  return (
    <section className="mx-auto max-w-4xl px-6 py-16">
      <Eyebrow className="block">Questions</Eyebrow>
      <h2 className="mt-3 font-display text-3xl font-medium tracking-tight">Before You Sign In</h2>

      <Accordion className="mt-8" multiple={false}>
        {QUESTIONS.map((item) => (
          <AccordionItem key={item.q}>
            <AccordionTrigger className="py-4 font-display text-base font-medium tracking-tight">
              {item.q}
            </AccordionTrigger>
            <AccordionContent className="max-w-2xl pr-8 pb-5 leading-relaxed text-muted-foreground">
              {item.a}
            </AccordionContent>
          </AccordionItem>
        ))}
      </Accordion>
    </section>
  )
}
