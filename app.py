#!/usr/bin/env python3
"""
app.py - FastAPI backend for the Chronology system.
Serves events and provides a conversational Q&A endpoint.
"""

import os
import json
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
import anthropic

app = FastAPI(title="FDA Chronology API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load events at startup
EVENTS_PATH = Path("extracted/events.json")
_events = []

def load_events():
    global _events
    if EVENTS_PATH.exists():
        with open(EVENTS_PATH) as f:
            _events = json.load(f)
        _events.sort(key=lambda e: e.get("date", "9999"))
        print(f"Loaded {len(_events)} events")
    else:
        print(f"Warning: {EVENTS_PATH} not found. Run extract.py first.")

load_events()


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/api/events")
def get_events(
    category: Optional[str] = Query(None),
    significance: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    year: Optional[int] = Query(None),
):
    """Return filtered chronology events."""
    results = _events

    if category:
        results = [e for e in results if e.get("category", "").lower() == category.lower()]
    if significance:
        results = [e for e in results if e.get("significance", "").lower() == significance.lower()]
    if year:
        results = [e for e in results if str(year) in e.get("date", "")]
    if search:
        q = search.lower()
        results = [e for e in results if q in e.get("event", "").lower() or q in e.get("reference", "").lower()]

    return {"total": len(results), "events": results}


@app.get("/api/categories")
def get_categories():
    cats = sorted(set(e.get("category", "Other") for e in _events))
    return {"categories": cats}


@app.get("/api/stats")
def get_stats():
    from collections import Counter
    cats = Counter(e.get("category", "Other") for e in _events)
    sigs = Counter(e.get("significance", "Medium") for e in _events)
    years = Counter(e.get("date", "")[:4] for e in _events if e.get("date"))
    return {
        "total_events": len(_events),
        "by_category": dict(cats),
        "by_significance": dict(sigs),
        "by_year": dict(sorted(years.items())),
    }


class ChatRequest(BaseModel):
    message: str
    history: list = []


@app.post("/api/chat")
def chat(req: ChatRequest):
    """Conversational Q&A over the chronology."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)

    # Build context: top 100 events as JSON summary (to stay within context limits)
    context_events = _events[:200]
    context = json.dumps(context_events, indent=1)

    system = f"""You are a legal research assistant helping lawyers understand the regulatory timeline 
of Pfizer-BioNTech's COMIRNATY (BNT162b2) COVID-19 vaccine.

You have access to a chronology of {len(_events)} extracted events from FDA regulatory documents.
Here are the events (sorted by date):

{context}

Answer questions accurately based on this data. Be concise and cite specific dates and document references.
If asked about something not in the data, say so clearly."""

    messages = req.history + [{"role": "user", "content": req.message}]

    response = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1000,
        system=system,
        messages=messages,
    )

    return {"response": response.content[0].text}


# Serve the frontend
if Path("static").exists():
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def index():
    if Path("static/index.html").exists():
        return FileResponse("static/index.html")
    return {"message": "Chronology API running. See /docs for API reference."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
