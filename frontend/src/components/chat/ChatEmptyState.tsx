import { MessageSquareText } from 'lucide-react'

import { EmptyState } from '@/components/common/EmptyState'

/** Straight from the client brief, so the first click lands on a real question. */
const examples = [
  'How did Apple’s Services revenue mix change between fiscal 2023 and 2024?',
  'What risk factors does NVIDIA cite around export controls?',
  'What does Microsoft disclose about capital expenditure on AI infrastructure?',
]

type ChatEmptyStateProps = {
  onPick: (question: string) => void
}

export function ChatEmptyState({ onPick }: ChatEmptyStateProps) {
  return (
    <EmptyState
      description="Ask about the filings in the corpus. Every claim comes back with the passage it came from."
      icon={MessageSquareText}
      title="Ask about a filing"
    >
      <ul className="space-y-1.5 text-left">
        {examples.map((example) => (
          <li key={example}>
            <button
              className="w-full rounded-lg border px-3 py-2 text-left text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 focus-visible:outline-none"
              onClick={() => onPick(example)}
              type="button"
            >
              {example}
            </button>
          </li>
        ))}
      </ul>
    </EmptyState>
  )
}
