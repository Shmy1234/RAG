# Citation context and markdown table rendering

## Goal

Improve citation verification in the chat UI. Clicking a citation must select its matching evidence in the existing right-side rail without opening a browser tab. The evidence rail must show the cited chunk with nearby chunks for context, and valid markdown tables in source text must render as tables.

## Design

The existing citation-source endpoint remains the single request used by the evidence rail. Its response will include the cited chunk plus ordered previous and next chunks from the same source document. The backend will reuse the existing `chunk_index` neighbor query and preserve the current user/message authorization boundary.

The frontend will extend the citation-source type with neighboring chunks. The evidence body will render the cited quote and an ordered context sequence. The cited chunk will be visually distinguished and its quote highlighted; neighboring chunks will be labeled by relative position. Source text will use the existing `react-markdown` and `remark-gfm` dependencies, which support GitHub-flavored markdown tables while preserving ordinary prose as paragraphs. Markdown is parsed at render time rather than transforming all source content into tables.

Citation chip clicks will continue to use the existing `onCitationSelect` callback and selection state. Any citation link-like interaction will be handled as an in-app selection, so the right rail opens or updates in the current tab. The existing “Open filing” link remains the only action that opens the original filing in a new tab.

## Data flow

1. A citation chip invokes `onCitationSelect(messageId, citation, chip)`.
2. `ChatThread` stores the message and citation index and renders `EvidencePanel`.
3. `EvidencePanel` requests the citation-source endpoint.
4. The backend loads the cited chunk and its immediate neighbors, returning metadata and text.
5. The panel renders previous, center, and next chunks with GFM markdown support.

## Error handling

Existing loading, retry, not-found, and authorization behavior remains unchanged. Missing neighbors are valid and simply omitted. Malformed markdown is rendered as text/paragraph content by the markdown renderer; it is not converted or rejected. If the source response is unavailable, the existing error notice and retry action are shown.

## Verification

Run backend tests covering the citation-source response and neighbor ordering, then run frontend type-check and lint. Manually verify that clicking multiple citations updates the same right rail, no citation click creates a browser tab, ordinary prose remains readable, and markdown tables render with aligned headers and cells.
