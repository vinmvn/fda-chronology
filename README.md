# FDA Chronology — COMIRNATY (BNT162b2)

An AI-powered chronology system that extracts and explores regulatory events from FDA documents related to Pfizer-BioNTech's COMIRNATY COVID-19 vaccine (IND 019736 → BLA 125742).

Built for Slater and Gordon — AI Engineer case study.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   FDA Regulatory PDFs                    │
│          (~400 files across 3 S3 ZIP archives)          │
└──────────────────────┬──────────────────────────────────┘
                       │
                  extract.py
                       │  Claude API (claude-opus-4-5)
                       │  PDF → structured JSON events
                       ▼
              extracted/events.json
              (date, event, reference,
               category, significance)
                       │
                    app.py
                  (FastAPI backend)
                       │
          ┌────────────┼────────────┐
          │            │            │
     GET /api/      POST /api/   GET /api/
      events         chat         stats
          │            │
          └────────────┘
               │
        static/index.html
        (Table + Chat UI)
```

**Key design decisions:**
- **Incremental extraction**: `--resume` flag allows processing to continue after interruption — critical for 400+ PDFs
- **Claude as extractor**: Sending raw PDF bytes via the document API gives better accuracy than naive text extraction, especially for scanned/complex regulatory docs
- **Stateless API**: All events stored in JSON; no DB dependency for the POC — swap to PostgreSQL for production
- **Context-window chat**: Top 200 events injected into system prompt for Q&A; for production, use embeddings + RAG

---

## Quickstart

### 1. Clone & install

```bash
git clone <repo-url>
cd chronology
pip install -r requirements.txt
```

### 2. Download PDFs

```bash
mkdir -p data/pdfs

# BLA 125742 package (~200 files) — recommended starting point
curl -L https://pdata0916.s3.us-east-2.amazonaws.com/pdocs/110123/pd-production-110123.zip \
  -o data/bla.zip && unzip data/bla.zip -d data/pdfs/

# IND 019736 submissions (~190 files)
curl -L https://pdata0916.s3.us-east-2.amazonaws.com/pdocs/multiple/pd-production-100123.zip \
  -o data/ind.zip && unzip data/ind.zip -d data/pdfs/
```

### 3. Extract events

```bash
export ANTHROPIC_API_KEY=your_key_here

# Process all PDFs (use --limit 20 for a quick test)
python extract.py --pdf_dir data/pdfs --out extracted/events.json

# Resume if interrupted
python extract.py --pdf_dir data/pdfs --out extracted/events.json --resume
```

### 4. Run the app

```bash
uvicorn app:app --reload
# Open http://localhost:8000
```

---

## Features

### Chronology Table
- Sortable columns (date, category, significance)
- Filter by category, significance level, year
- Full-text search across events and document filenames
- Colour-coded categories and significance indicators

### Conversational Q&A
- Ask natural language questions over the full chronology
- Multi-turn conversation with history
- Quick-prompt suggestions for common queries
- Cites specific dates and source documents

### API Endpoints

| Endpoint | Description |
|---|---|
| `GET /api/events` | Filtered event list (`?category=`, `?year=`, `?search=`, `?significance=`) |
| `GET /api/stats` | Breakdown by category, significance, year |
| `GET /api/categories` | List of all categories present |
| `POST /api/chat` | Conversational Q&A `{"message": "...", "history": [...]}` |

---

## Extracted Event Schema

```json
{
  "date": "2021-08-23",
  "date_display": "23 Aug 2021",
  "event": "FDA approves BLA 125742 — COMIRNATY licensed for individuals 16+",
  "category": "Approval",
  "significance": "High",
  "reference": "123_Courtesy_Copy_BLA_125742-0_August_23_2021_Approval_Letter.pdf"
}
```

**Categories:** Regulatory, Clinical, Safety Signal, Approval, Milestone, FDA Correspondence, Manufacturing, Labeling, Other

**Significance:** High / Medium / Low

---

## Bonus Features

- **Resume extraction**: `--resume` flag skips already-processed files — safe to interrupt and restart
- **Incremental save**: Events written to disk after each PDF — no data loss on crash
- **Stats endpoint**: Category/year breakdown for dashboard widgets
- **Significance scoring**: AI assigns High/Medium/Low importance to each event
- **Production path**: Replace JSON store with PostgreSQL + pgvector; use embeddings for semantic chat search over all events

---

## Tech Stack

- **Extraction**: Python + Anthropic Claude API (`claude-opus-4-5`)
- **Backend**: FastAPI + Uvicorn
- **Frontend**: Vanilla HTML/CSS/JS (no build step)
- **Storage**: JSON file (POC) → PostgreSQL ready

---

## Author

Vinod Moorkoth  
Senior Staff Data Engineer | AI Engineer candidate  
