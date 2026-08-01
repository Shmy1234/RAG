import { useEffect, useRef } from 'react'

type QuoteHighlightProps = {
  chunkText: string
  quotedText: string
}

/** Collapses whitespace so a quote still matches when the chunk wraps differently. */
function findQuote(chunkText: string, quotedText: string): [number, number] | null {
  const needle = quotedText.trim()
  if (!needle) return null

  const direct = chunkText.indexOf(needle)
  if (direct !== -1) return [direct, direct + needle.length]

  const normalizedNeedle = needle.replace(/\s+/g, ' ').toLowerCase()
  let normalized = ''
  const indexMap: number[] = []
  let lastWasSpace = false

  for (let index = 0; index < chunkText.length; index += 1) {
    const isSpace = /\s/.test(chunkText[index])
    if (isSpace) {
      if (lastWasSpace) continue
      normalized += ' '
      lastWasSpace = true
    } else {
      normalized += chunkText[index].toLowerCase()
      lastWasSpace = false
    }
    indexMap.push(index)
  }

  const found = normalized.indexOf(normalizedNeedle)
  if (found === -1) return null
  const end = found + normalizedNeedle.length - 1
  return [indexMap[found], indexMap[Math.min(end, indexMap.length - 1)] + 1]
}

/**
 * The signature moment: the cited quote shown inside its surrounding chunk rather
 * than lifted out of it. Falls back to plain text when the quote cannot be located,
 * because a wrong highlight is worse than none.
 */
export function QuoteHighlight({ chunkText, quotedText }: QuoteHighlightProps) {
  const markRef = useRef<HTMLElement>(null)
  const range = findQuote(chunkText, quotedText)

  useEffect(() => {
    markRef.current?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [chunkText, quotedText])

  if (!range) {
    return <p className="whitespace-pre-wrap leading-relaxed">{chunkText}</p>
  }

  const [start, end] = range
  return (
    <p className="whitespace-pre-wrap leading-relaxed">
      <span className="text-muted-foreground">{chunkText.slice(0, start)}</span>
      <mark
        className="rounded-sm bg-foreground/10 px-0.5 text-foreground ring-1 ring-foreground/20"
        ref={markRef}
      >
        {chunkText.slice(start, end)}
      </mark>
      <span className="text-muted-foreground">{chunkText.slice(end)}</span>
    </p>
  )
}
