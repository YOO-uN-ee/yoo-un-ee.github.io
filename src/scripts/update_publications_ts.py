#!/usr/bin/env python3
import re
import requests
import os
import time
import json
from datetime import datetime, timezone
from scholarly import scholarly

SCHOLAR_ID = "RpcilLMAAAAJ"
OUT_PATH = os.environ.get("OUT_PATH", "src/data/publications.generated.ts")

META_NAMES = [
    "citation_conference_title",
    "citation_book_title",
    "citation_journal_title",
    "citation_series_title",
]

_BIB_FIELD_RE = re.compile(
    r"(?im)^\s*(?P<key>[a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(?P<val>\{.*?\}|\".*?\")\s*,?\s*$"
)

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

def looks_truncated_venue(v: str) -> bool:
    v = (v or "").strip()
    if not v:
        return True
    if "…" in v:
        return True
    # common Scholar truncation symptoms (ends mid-phrase)
    bad_endings = (" for", " on", " of", " and", " in", " with", " International Workshop on AI for")
    if v.endswith(bad_endings):
        return True
    # very long "Proceedings of ..." that ends abruptly
    if v.lower().startswith("proceedings of") and len(v) < 80:
        # not perfect, but catches many "cut short" cases
        return True
    return False

def fetch_full_venue_from_url(pub_url: str) -> str:
    if not pub_url:
        return ""

    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
    }

    try:
        r = requests.get(pub_url, headers=headers, timeout=25, allow_redirects=True)
        r.raise_for_status()
        html = r.text
    except Exception:
        return ""

    # 1) Try citation_* meta tags (works well for ACM, many publishers)
    for name in META_NAMES:
        m = re.search(
            rf'<meta\s+name="{re.escape(name)}"\s+content="([^"]+)"',
            html,
            flags=re.IGNORECASE
        )
        if m:
            return m.group(1).strip()

    # 2) Try JSON-LD
    # ACM often includes structured JSON-LD with isPartOf / name fields
    ld_blocks = re.findall(
        r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>',
        html,
        flags=re.IGNORECASE | re.DOTALL
    )
    for block in ld_blocks:
        block = block.strip()
        if not block:
            continue
        try:
            data = json.loads(block)
        except Exception:
            continue

        # data can be dict or list
        candidates = data if isinstance(data, list) else [data]
        for obj in candidates:
            if not isinstance(obj, dict):
                continue
            # schema-ish patterns
            is_part_of = obj.get("isPartOf")
            if isinstance(is_part_of, dict):
                name = is_part_of.get("name")
                if isinstance(name, str) and name.strip():
                    return name.strip()
            # sometimes nested differently
            name = obj.get("name")
            # name alone is usually the paper title, so don't return that by default

    return ""


def bibtex_get_field(bibtex: str, field: str) -> str:
    if not bibtex:
        return ""
    field = field.lower()
    for m in _BIB_FIELD_RE.finditer(bibtex):
        k = m.group("key").lower()
        if k != field:
            continue
        v = m.group("val").strip()
        # strip outer { } or " "
        if (v.startswith("{") and v.endswith("}")) or (v.startswith('"') and v.endswith('"')):
            v = v[1:-1].strip()
        # clean common truncation char
        return v.replace("…", "").strip()
    return ""

def pick_venue(pub: dict) -> str:
    bib = pub.get("bib", {}) or {}

    # Try BibTeX first — often contains full booktitle/journal even when bib fields are shortened.
    try:
        bt = scholarly.bibtex(pub)  # :contentReference[oaicite:1]{index=1}
    except Exception:
        bt = ""

    venue = (
        bibtex_get_field(bt, "booktitle") or
        bibtex_get_field(bt, "journal") or
        bibtex_get_field(bt, "series") or
        bibtex_get_field(bt, "publisher")
    )
    if venue:
        return venue

    # Fallbacks (may be truncated)
    for k in ("venue", "journal", "booktitle", "conference"):
        v = (bib.get(k) or "").replace("…", "").strip()
        if v:
            return v

    # Last fallback: citation head
    cit = (bib.get("citation") or "").replace("…", "").strip()
    return cit.split(",", 1)[0].strip() if cit else ""


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
        full_url = f"https://scholar.google.com/citations?view_op=view_citation&hl=en&user={SCHOLAR_ID}&citation_for_view={p['author_pub_id']}"
        print(full_url)
        # Filling each pub adds requests; keep schedule infrequent.
        try:
            p_full = scholarly.fill(p, sortby='year')
        except Exception:
            p_full = p

        title = pick_title(p_full)
        if not title:
            continue

        venue = pick_venue(p_full)
        pub_url = (p_full.get("pub_url") or "").strip()

        if looks_truncated_venue(venue) and pub_url:
            full_venue = fetch_full_venue_from_url(pub_url)
            if full_venue:
                venue = full_venue

        record = {
            "title": title,
            "authors": pick_authors(p_full),
            "journal": venue,
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

    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
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