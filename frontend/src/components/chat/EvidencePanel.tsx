import { ExternalLink, X } from 'lucide-react'
import { useEffect, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { QuoteHighlight } from '@/components/chat/QuoteHighlight'
import { describeError, type ErrorDescription } from '@/components/chat/chat-errors'
import { ErrorNotice } from '@/components/common/ErrorNotice'
import { FilingMeta } from '@/components/common/FilingMeta'
import { Button } from '@/components/ui/button'
import { Sheet, SheetContent, SheetTitle } from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { useIsMobile } from '@/hooks/use-mobile'
import { chatApi, type CitationChunk, type CitationSource } from '@/lib/chat-api'

export type SelectedCitation = {
  messageId: string
  citationIndex: number
}

type EvidencePanelProps = {
  selection: SelectedCitation
  onClose: () => void
}

function useCitationSource({ messageId, citationIndex }: SelectedCitation) {
  const [source, setSource] = useState<CitationSource | null>(null)
  const [error, setError] = useState<ErrorDescription | null>(null)
  const [reloadToken, setReloadToken] = useState(0)

  // No reset needed here: the body is keyed by selection, so a different citation
  // mounts a fresh component rather than reusing this state.
  useEffect(() => {
    let cancelled = false

    chatApi
      .getCitationSource(messageId, citationIndex)
      .then((value) => {
        if (!cancelled) setSource(value)
      })
      .catch((unknownError: unknown) => {
        if (!cancelled) setError(describeError(unknownError))
      })

    return () => {
      cancelled = true
    }
  }, [messageId, citationIndex, reloadToken])

  return {
    source,
    error,
    reload: () => {
      setError(null)
      setReloadToken((token) => token + 1)
    },
  }
}

function EvidencePanelBody({ selection, onClose }: EvidencePanelProps) {
  const { source, error, reload } = useCitationSource(selection)

  return (
    <>
      <div className="flex items-start justify-between gap-3 border-b px-4 py-3">
        <div className="min-w-0">
          <h2 className="font-medium">Evidence</h2>
          {source ? (
            <FilingMeta
              citationLabel={`${source.company_name} · ${source.filing_type}`}
              className="mt-0.5"
              filingDate={source.filing_date}
              locationLabel={source.location_label}
            />
          ) : null}
        </div>
        <Button aria-label="Close evidence" onClick={onClose} size="icon-sm" variant="ghost">
          <X />
        </Button>
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
        {error ? (
          <ErrorNotice
            description={error.description}
            onRetry={error.canRetry ? reload : undefined}
            title={error.title}
            tone={error.tone}
          />
        ) : !source ? (
          <div className="space-y-2" aria-label="Loading passage" role="status">
            <Skeleton className="h-3 w-1/3" />
            <Skeleton className="h-16 w-full" />
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-4/5" />
          </div>
        ) : (
          <div className="space-y-4">
            <div>
              <p className="mb-1.5 font-mono text-[0.6875rem] tracking-tight text-muted-foreground">
                CITED
              </p>
              <blockquote className="border-l-2 border-foreground/30 pl-3 leading-relaxed">
                {source.quoted_text}
              </blockquote>
            </div>
            <div>
              <p className="mb-1.5 font-mono text-[0.6875rem] tracking-tight text-muted-foreground">
                IN CONTEXT
              </p>
              <QuoteHighlight chunkText={source.chunk_text} quotedText={source.quoted_text} />
            </div>
            <div>
              <p className="mb-1.5 font-mono text-[0.6875rem] tracking-tight text-muted-foreground">
                NEIGHBORING CHUNKS
              </p>
              <div className="space-y-3">
                {source.previous_chunks.map((chunk) => (
                  <ContextChunk chunk={chunk} key={chunk.chunk_id} label="Previous chunk" />
                ))}
                <ContextChunk
                  chunk={{
                    chunk_id: source.chunk_id,
                    chunk_index: source.chunk_index,
                    text: source.chunk_text,
                    page_number: source.page_number,
                    section: source.section,
                  }}
                  label="Cited chunk"
                />
                {source.next_chunks.map((chunk) => (
                  <ContextChunk chunk={chunk} key={chunk.chunk_id} label="Next chunk" />
                ))}
              </div>
            </div>
            {source.source_url ? (
              <a
                className="inline-flex items-center gap-1.5 text-muted-foreground underline underline-offset-2 hover:text-foreground"
                href={source.source_url}
                rel="noreferrer"
                target="_blank"
              >
                Open filing
                <ExternalLink className="size-3" />
              </a>
            ) : null}
          </div>
        )}
      </div>
    </>
  )
}

function ContextChunk({ chunk, label }: { chunk: CitationChunk; label: string }) {
  return (
    <div className="rounded-md border bg-background/60 p-3">
      <p className="mb-2 font-mono text-[0.625rem] tracking-tight text-muted-foreground">{label}</p>
      <div className="max-w-none break-words text-sm leading-relaxed [&_table]:block [&_table]:w-full [&_table]:overflow-x-auto [&_table]:text-left [&_th]:border [&_th]:border-border [&_th]:bg-muted [&_th]:px-2 [&_th]:py-1 [&_td]:border [&_td]:border-border [&_td]:px-2 [&_td]:py-1">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{chunk.text}</ReactMarkdown>
      </div>
    </div>
  )
}

/**
 * Beside the conversation on wide screens, a bottom sheet on narrow ones. Both
 * render the same body, so the verification experience does not fork by viewport.
 */
export function EvidencePanel({ selection, onClose }: EvidencePanelProps) {
  const isMobile = useIsMobile()
  const key = `${selection.messageId}-${selection.citationIndex}`

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  if (isMobile) {
    return (
      <Sheet onOpenChange={(open) => !open && onClose()} open>
        <SheetContent className="flex h-[80svh] flex-col p-0" side="bottom">
          <SheetTitle className="sr-only">Evidence</SheetTitle>
          <EvidencePanelBody key={key} onClose={onClose} selection={selection} />
        </SheetContent>
      </Sheet>
    )
  }

  return (
    <aside aria-label="Evidence" className="flex w-[26rem] shrink-0 flex-col border-l bg-sidebar/40">
      <EvidencePanelBody key={key} onClose={onClose} selection={selection} />
    </aside>
  )
}
