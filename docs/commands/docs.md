# docs

Manage reference documents — import PDFs or Markdown files and make them searchable.

```
provenance docs [COMMAND]
```

---

## list

List all tracked documents.

```bash
provenance docs list
provenance docs list --json
```

---

## import

Import a `.md` or `.pdf` file into `notes/docs/` and register it in the database.

```bash
provenance docs import ~/Downloads/ai-strategy.pdf
provenance docs import ~/Documents/onboarding.md --title "Company Onboarding Guide" --tags "onboarding,reference"
provenance docs import report.pdf --notes "Q1 strategy doc from the Dean's office"
```

| Argument / Flag | Short | Description |
|-----------------|-------|-------------|
| `FILE` | | Path to `.md` or `.pdf` (required) |
| `--title` | `-t` | Title (defaults to filename stem, title-cased) |
| `--tags` | | Comma-separated tags |
| `--notes` | `-n` | Your notes about this document |
| `--json` | | Output result as JSON |

**PDF conversion:** PDFs are converted to Markdown using [PyMuPDF](https://pymupdf.readthedocs.io/). Each page becomes a `## Page N` section. The converted file is saved to `notes/docs/<slug>.md` so it's indexed by `ck` and searchable.

!!! warning "Scanned PDFs"
    PDFs that are scanned images (no embedded text layer) cannot be converted. You'll get an error and need to OCR the file first.

!!! info "Auto-indexing"
    The search index is updated automatically in the background after each import.

---

## add

Register an existing `.md` file you placed manually in `notes/docs/`.

```bash
provenance docs add "Team Handbook" --file notes/docs/handbook.md
provenance docs add "AI Ethics Policy" --file notes/docs/ethics.md --tags "policy,ai"
```

| Argument / Flag | Short | Description |
|-----------------|-------|-------------|
| `TITLE` | | Document title (required) |
| `--file` | `-f` | Path to the `.md` file (required) |
| `--tags` | | Comma-separated tags |
| `--notes` | `-n` | Your notes about this document |
| `--json` | | Output result as JSON |

Use this when you've already placed a file in `notes/docs/` and just want to register it without copying.

---

## show

Show document details and a content preview.

```bash
provenance docs show ai-strategy
provenance docs show ai-strategy --json
```

| Argument | Description |
|----------|-------------|
| `SLUG` | Document slug (see `list`) |
| `--json` | Output as JSON |
