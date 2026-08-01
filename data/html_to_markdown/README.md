# HTML to Markdown

Convert the raw SEC HTML filings in `data/downloads/` into Markdown files under
`data/Markdown/` while preserving the year folders and rewriting
`manifest.json` to point at `.md` files.

Run from the repo root:

```bash
python data/html_to_markdown/convert_html_to_markdown.py --overwrite
```

If Docling is installed only in the backend `uv` environment, run:

```bash
uv run --directory backend python ../data/html_to_markdown/convert_html_to_markdown.py --overwrite
```

Run the tests:

```bash
python -m pytest data/html_to_markdown/test_convert_html_to_markdown.py -q
```
