#!/usr/bin/env python3
import os
import time
from datetime import datetime
from scholarly import scholarly

SCHOLAR_ID = "RpcilLMAAAAJ"
OUT_PATH = os.environ.get("OUT_PATH", "../data/publications.generated.ts")

if not SCHOLAR_ID:
    raise SystemExit("Missing SCHOLAR_ID env var (the `user=` value from your Scholar profile URL).")

def ts_escape(s: str) -> str:
    """Escape a Python string into a safe TS single-quoted string literal."""
    if s is None:
        return ""
    s = str(s)
    s = s.replace("\\", "\\\\")
    s = s.replace("'", "\\'")
    s = s.replace("\r", "")
    s = s.replace("\n", "\\n")
    return s

def pick_year(pub: dict) -> str:
    bib = pub.get("bib", {}) or {}
    y = bib.get("pub_year") or bib.get("year") or ""
    return str(y) if y is not None else ""

def pick_venue(pub: dict) -> str:
    bib = pub.get("bib", {}) or {}
    return (bib.get("venue") or bib.get("journal") or bib.get("conference") or "").strip()

def pick_authors(pub: dict) -> str:
    bib = pub.get("bib", {}) or {}
    # scholarly bib "author" is typically a string
    return (bib.get("author") or "").strip()

def pick_title(pub: dict) -> str:
    bib = pub.get("bib", {}) or {}
    return (bib.get("title") or "").strip()

def pick_link(pub: dict) -> str:
    # `pub_url` is commonly present. Sometimes bib has `url`.
    bib = pub.get("bib", {}) or {}
    return (pub.get("pub_url") or bib.get("url") or "").strip()

def main():
    author = scholarly.search_author_id(SCHOLAR_ID)
    author = scholarly.fill(author)

    pubs = []
    for p in (author.get("publications") or []):
        # Filling each pub adds requests; keep schedule infrequent.
        try:
            p_full = scholarly.fill(p)
        except Exception:
            p_full = p

        title = pick_title(p_full)
        if not title:
            continue

        record = {
            "title": title,
            "authors": pick_authors(p_full),
            "journal": pick_venue(p_full),
            "time": pick_year(p_full),
            "link": pick_link(p_full) or None,
            # you don't get these reliably from Scholar; leave empty for your UI
            "github": None,
            "slides": None,
            "abstract": "",  # Scholar usually doesn't provide abstract; keep empty
        }
        pubs.append(record)
        time.sleep(1.0)

    # Sort newest year first (string-safe)
    def year_key(r):
        try:
            return int(r["time"])
        except Exception:
            return -1
    pubs.sort(key=year_key, reverse=True)

    generated_at = datetime.utcnow().isoformat() + "Z"
    lines = []
    lines.append("// AUTO-GENERATED FILE. DO NOT EDIT.")
    lines.append(f"// Generated at: {generated_at}")
    lines.append("")
    lines.append("export const publications = [")
    for r in pubs:
        title = ts_escape(r["title"])
        authors = ts_escape(r["authors"])
        journal = ts_escape(r["journal"])
        year = ts_escape(r["time"])
        link = r["link"]
        link_ts = f"'{ts_escape(link)}'" if link else "undefined"

        # Keep the same keys your site expects: title/authors/journal/time/link/github/slides/abstract
        lines.append("  {")
        lines.append(f"    title: '{title}',")
        lines.append(f"    authors: '{authors}',")
        lines.append(f"    journal: '{journal}',")
        lines.append(f"    time: '{year}',")
        lines.append(f"    link: {link_ts},")
        lines.append("    github: undefined,")
        lines.append("    slides: undefined,")
        lines.append("    abstract: '',")
        lines.append("  },")
    lines.append("] as const;")
    lines.append("")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Wrote {len(pubs)} publications -> {OUT_PATH}")

if __name__ == "__main__":
    main()