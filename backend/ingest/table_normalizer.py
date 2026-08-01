"""Normalize SEC presentation-grid HTML tables into logical financial rows."""

import re

from lxml import html

from ingest.models import ExtractedTable, ExtractedTableRow, SourceLocator

_NUMBER = re.compile(r"^\(?-?\d[\d,.]*\)?$")


def _text(element) -> str:
    return " ".join(element.text_content().replace("\u00a0", " ").split())


def _visible_tokens(row) -> list[str]:
    return [value for cell in row.xpath("./td|./th") if (value := _text(cell))]


def _combine_values(tokens: list[str]) -> tuple[str, ...]:
    values: list[str] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token == "$" and index + 1 < len(tokens) and _NUMBER.match(tokens[index + 1]):
            values.append(f"${tokens[index + 1]}")
            index += 2
            continue
        if _NUMBER.match(token):
            if index + 1 < len(tokens) and tokens[index + 1] == "%":
                values.append(f"{token}%")
                index += 2
            else:
                values.append(token)
                index += 1
            continue
        index += 1
    return tuple(values)


def _is_header_row(tokens: list[str]) -> bool:
    def is_header_token(token: str) -> bool:
        return (
            token.casefold() in {"change", "years ended", "year ended"}
            or bool(re.fullmatch(r"(?:19|20)\d{2}", token))
        )

    return bool(tokens) and (
        all(is_header_token(token) for token in tokens)
        or (len(tokens) > 1 and all(is_header_token(token) for token in tokens[1:]))
    )


def _headers(header_tokens: list[str], value_count: int, title: str | None) -> tuple[str, ...]:
    if len(header_tokens) == value_count + 1:
        header_tokens = header_tokens[1:]
    logical: list[str] = []
    period: str | None = None
    for token in header_tokens:
        if token.casefold() == "change" and period:
            logical.append(f"{period} Change")
        else:
            logical.append(token)
            if re.search(r"\b(?:19|20)\d{2}\b", token):
                period = token
    logical = logical[:value_count]
    if len(logical) < value_count:
        logical.extend(f"Value {index}" for index in range(len(logical) + 1, value_count + 1))
    row_header = "Segment" if title and "segment" in title.casefold() else "Row"
    return (row_header, *logical)


def normalize_table_html(
    table_html: str,
    *,
    table_index: int,
    title: str | None = None,
    units: str | None = None,
    section_path: tuple[str, ...] = (),
) -> ExtractedTable | None:
    """Return a semantic table, or ``None`` for non-numeric layout tables."""
    element = html.fromstring(table_html)
    if element.tag.lower() != "table":
        candidates = element.xpath(".//table")
        if not candidates:
            return None
        element = candidates[0]

    html_id = element.get("id")
    rows = element.xpath("./tr|./thead/tr|./tbody/tr|./tfoot/tr")
    if len(rows) < 2:
        return None

    extracted_rows: list[ExtractedTableRow] = []
    header_rows: list[list[str]] = []
    for row in rows:
        tokens = _visible_tokens(row)
        if _is_header_row(tokens) and not extracted_rows:
            header_rows.append(tokens)
            continue
        values = _combine_values(tokens)
        if not values:
            if tokens and not extracted_rows:
                header_rows.append(tokens)
            continue
        label = next(
            (token for token in tokens if token not in {"$", "%"} and not _NUMBER.match(token)), ""
        )
        if not label:
            continue
        extracted_rows.append(
            ExtractedTableRow(
                label=label,
                values=values,
                is_total="total" in label.casefold(),
                source_locator=SourceLocator(html_id=html_id),
            )
        )

    if not extracted_rows:
        return None
    value_count = max(len(row.values) for row in extracted_rows)
    if value_count < 2 or any(len(row.values) != value_count for row in extracted_rows):
        return None
    matching_headers = [
        tokens for tokens in header_rows if len(tokens) in {value_count, value_count + 1}
    ]
    if not matching_headers:
        return None
    header_tokens = matching_headers[-1]

    return ExtractedTable(
        table_index=table_index,
        title=title,
        units=units,
        section_path=section_path,
        headers=_headers(header_tokens, value_count, title),
        rows=tuple(extracted_rows),
        source_locator=SourceLocator(html_id=html_id),
        validation={"logical_columns": value_count + 1, "status": "passed"},
    )
