#!/usr/bin/env python3
"""
extract.py - Extract chronology events from FDA regulatory PDFs using Claude API.
Usage: python extract.py --pdf_dir data/pdfs --out extracted/events.json --api_key YOUR_KEY
"""

import os
import json
import base64
import argparse
import time
from pathlib import Path
import anthropic

SYSTEM_PROMPT = """You are a legal/regulatory document analyst. 
Extract ALL key events from this FDA regulatory document.
Return ONLY a JSON array, no markdown, no explanation.

Each event must have:
- date: ISO format if possible (YYYY-MM-DD), or partial like "2021-08" or "2021"
- date_display: human-readable e.g. "23 Aug 2021"
- event: concise descriptive summary (1-2 sentences)
- category: one of [Regulatory, Clinical, Safety Signal, Approval, Milestone, FDA Correspondence, Manufacturing, Labeling, Other]
- significance: one of [High, Medium, Low]

Return format: [{"date":"...","date_display":"...","event":"...","category":"...","significance":"..."}]
If no clear events found, return [].
"""

def extract_events_from_pdf(pdf_path: Path, client: anthropic.Anthropic) -> list:
    """Extract events from a single PDF using Claude API."""
    try:
        with open(pdf_path, "rb") as f:
            pdf_data = base64.standard_b64encode(f.read()).decode("utf-8")

        response = client.messages.create(
            model="claude-opus-4-5",
            max_tokens=2000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "document",
                            "source": {
                                "type": "base64",
                                "media_type": "application/pdf",
                                "data": pdf_data,
                            },
                        },
                        {
                            "type": "text",
                            "text": f"Extract all key chronology events from this document. Filename: {pdf_path.name}"
                        }
                    ],
                }
            ],
            system=SYSTEM_PROMPT,
        )

        raw = response.content[0].text.strip()
        # Strip markdown fences if present
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        
        events = json.loads(raw)
        # Attach source reference to each event
        for e in events:
            e["reference"] = pdf_path.name
        return events

    except json.JSONDecodeError as ex:
        print(f"  [WARN] JSON parse failed for {pdf_path.name}: {ex}")
        return []
    except Exception as ex:
        print(f"  [ERROR] {pdf_path.name}: {ex}")
        return []


def main():
    parser = argparse.ArgumentParser(description="Extract chronology events from PDFs")
    parser.add_argument("--pdf_dir", default="data/pdfs", help="Directory containing PDFs")
    parser.add_argument("--out", default="extracted/events.json", help="Output JSON file")
    parser.add_argument("--api_key", default=os.environ.get("ANTHROPIC_API_KEY"), help="Anthropic API key")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of PDFs (for testing)")
    parser.add_argument("--resume", action="store_true", help="Skip already-processed files")
    args = parser.parse_args()

    if not args.api_key:
        raise ValueError("No API key provided. Set ANTHROPIC_API_KEY or use --api_key")

    client = anthropic.Anthropic(api_key=args.api_key)
    pdf_dir = Path(args.pdf_dir)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing events if resuming
    all_events = []
    processed_files = set()
    if args.resume and out_path.exists():
        with open(out_path) as f:
            all_events = json.load(f)
        processed_files = {e["reference"] for e in all_events}
        print(f"Resuming — {len(processed_files)} files already processed, {len(all_events)} events loaded")

    pdfs = sorted(pdf_dir.glob("*.pdf"))
    if args.limit:
        pdfs = pdfs[:args.limit]

    print(f"Processing {len(pdfs)} PDFs from {pdf_dir}...")

    for i, pdf_path in enumerate(pdfs):
        if pdf_path.name in processed_files:
            print(f"  [{i+1}/{len(pdfs)}] Skipping {pdf_path.name} (already processed)")
            continue

        print(f"  [{i+1}/{len(pdfs)}] Processing {pdf_path.name}...")
        events = extract_events_from_pdf(pdf_path, client)
        print(f"    → {len(events)} events extracted")
        all_events.extend(events)

        # Save incrementally after each file
        with open(out_path, "w") as f:
            json.dump(all_events, f, indent=2)

        # Rate limit courtesy pause
        if i < len(pdfs) - 1:
            time.sleep(0.5)

    # Final sort by date
    all_events.sort(key=lambda e: e.get("date", "9999"))

    with open(out_path, "w") as f:
        json.dump(all_events, f, indent=2)

    print(f"\nDone! {len(all_events)} total events saved to {out_path}")


if __name__ == "__main__":
    main()
