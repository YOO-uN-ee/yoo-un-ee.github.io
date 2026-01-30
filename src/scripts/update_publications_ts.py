#!/usr/bin/env python3
import re
import requests
import os
import time
import json
from datetime import datetime, timezone
from scholarly import scholarly
import bibtexparser
import requests
from urllib.parse import quote
from pathlib import Path

GEN_RE = re.compile(r"Generated at:\s*([0-9T:\.\-]+)Z")
DOI_RE = re.compile(r"(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", re.I)
SCHOLAR_ID = "RpcilLMAAAAJ"
OUT_PATH = os.environ.get("OUT_PATH", "src/data/dynamic.ts")

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

def extract_doi(text: str) -> str:
    if not text:
        return ""
    m = DOI_RE.search(text)
    return m.group(1) if m else ""

def crossref_lookup(doi: str, mailto: str = "") -> dict:
    if not doi:
        return {}
    url = "https://api.crossref.org/works/" + quote(doi, safe="")
    params = {"mailto": mailto} if mailto else {}
    r = requests.get(url, params=params, timeout=20)
    r.raise_for_status()
    return r.json().get("message", {}) or {}

def venue_from_crossref(msg: dict) -> str:
    # Crossref: container-title is usually what you want for proceedings/books/journals
    ct = msg.get("container-title") or []
    if ct and isinstance(ct, list) and ct[0].strip():
        return ct[0].strip()
    # Sometimes "event" exists for conference metadata
    ev = msg.get("event") or {}
    name = (ev.get("name") or "").strip()
    return name

def bibtex_to_fields(bibtex_str: str) -> dict:
    """Parse a single-entry BibTeX string into a normalized dict of fields."""
    if not bibtex_str:
        return {}
    try:
        db = bibtexparser.loads(bibtex_str)
    except Exception:
        return {}
    if not getattr(db, "entries", None):
        return {}

    e = db.entries[0]
    out = {}
    for k, v in e.items():
        if v is None:
            continue
        out[str(k).lower().strip()] = str(v).strip()
    return out

def get_bibtex_with_fallback(p_full: dict, title: str) -> str:
    # 1) Try directly
    try:
        s = scholarly.bibtex(p_full)
        if s:
            return s
    except Exception as e:
        pass

    # 2) Fallback: search by title (search results often have the needed IDs)
    try:
        q = scholarly.search_pubs(title)
        pub2 = next(q, None)
        if not pub2:
            return ""
        pub2 = scholarly.fill(pub2)
        return scholarly.bibtex(pub2) or ""
    except Exception:
        return ""


def has_good_venue_fields(fields: dict) -> bool:
    return any((fields.get(k) or "").strip() for k in ("booktitle", "journal", "eventtitle", "series"))


def pick_venue_from_bibtex(fields: dict, fallback: str = "") -> str:
    """
    Prefer booktitle for proceedings/chapters (fixes Springer chapters),
    then journal, then venue-ish, then publisher.
    """
    for k in ("booktitle", "journal", "eventtitle", "container-title", "series"):
        v = (fields.get(k) or "").strip()
        if v:
            return v

    # Only use publisher as a last resort
    pub = (fields.get("publisher") or "").strip()
    if pub:
        return pub

    return fallback or ""

def pick_year_from_bibtex(fields: dict, fallback: str = "") -> str:
    y = (fields.get("year") or "").strip()
    if y:
        return y
    # Sometimes date like 2025-10-01
    date = (fields.get("date") or "").strip()
    if len(date) >= 4 and date[:4].isdigit():
        return date[:4]
    return fallback or ""

def normalize_authors(author_str: str) -> str:
    """
    BibTeX uses `and` as the author delimiter. Convert it to comma-separated.
    Also normalizes whitespace.
    """
    if not author_str:
        return ""
    s = re.sub(r"\s+", " ", author_str).strip()
    parts = [p.strip() for p in re.split(r"\s+and\s+", s) if p.strip()]
    return ", ".join(parts)


def pick_authors_from_bibtex(fields: dict, fallback: str = "") -> str:
    a = (fields.get("author") or "").strip()
    if a:
        # Optional: turn "A and B and C" into your preferred format.
        return normalize_authors(a)
    return normalize_authors(fallback) or ""

def pick_title_from_bibtex(fields: dict, fallback: str = "") -> str:
    t = (fields.get("title") or "").strip()
    return t or fallback or ""

def pick_url_from_bibtex(fields: dict, fallback: str = "") -> str:
    # BibTeX may have url; otherwise use fallback pub_url you already have
    return (fields.get("url") or fallback or "").strip()

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
    bad_endings = (" for", " on", " of", " and", " in", " with")
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

    # 2) Fallback: parse the citation string (this is commonly present)
    cit = (bib.get("citation") or "").strip()
    if not cit:
        return ""
    
    # Normalize whitespace
    cit = re.sub(r"\s+", " ", cit).strip()

    # If it's an arXiv-style citation, collapse to "arXiv"
    # if "arxiv" in cit.lower():
    #     return "arXiv"

    # Common pattern: "Venue, YEAR"  -> take before first comma
    head = cit.split(",", 1)[0].strip()
    if head and head.lower() != "unknown":
        return head

    # Otherwise, strip trailing year-ish or page-ish suffixes from entire citation
    # Remove " ... 2025" or " ... (2025)" or " ... pp. 12-34"
    cit2 = re.sub(r"\s*\(?\b(19|20)\d{2}\b\)?\s*$", "", cit).strip()
    cit2 = re.sub(r"\s+\bpp?\.\s*\d+.*$", "", cit2).strip()

    print(cit2)
    return cit2

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

def read_generated_year(ts_path: Path) -> int | None:
    """Reads the header line: // Generated at: 2026-...Z and returns 2026."""
    if not ts_path.exists():
        return None
    text = ts_path.read_text(encoding="utf-8")
    m = GEN_RE.search(text)
    if not m:
        return None
    try:
        dt = datetime.fromisoformat(m.group(1))  # no trailing Z in group
        return dt.year
    except Exception:
        return None

def extract_exported_array(ts_text: str) -> list[dict]:
    """
    Extracts the first exported array literal from a TS file like:
      export const dynamicPubs = [...] as const;
    Assumes the array is valid JSON (double quotes).
    """
    # Find first '[' after 'export const'
    i = ts_text.find("export const")
    if i < 0:
        return []
    j = ts_text.find("[", i)
    if j < 0:
        return []

    # Bracket match while respecting strings
    depth = 0
    in_str = False
    esc = False
    end = None
    for k in range(j, len(ts_text)):
        ch = ts_text[k]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        else:
            if ch == '"':
                in_str = True
                continue
            if ch == "[":
                depth += 1
            elif ch == "]":
                depth -= 1
                if depth == 0:
                    end = k + 1
                    break

    if end is None:
        return []

    arr_src = ts_text[j:end].strip()
    return json.loads(arr_src)

def pub_key(p: dict) -> str:
    # Adjust keys to your schema; these are common patterns:
    return (
        str(p.get("doi") or "")
        or str((p.get("links") or {}).get("paper") or "")
        or f"{p.get('title','')}__{p.get('year','')}"
    )

def dedupe_keep_order(pubs: list[dict]) -> list[dict]:
    seen = set()
    out = []
    for p in pubs:
        k = pub_key(p)
        if k in seen:
            continue
        seen.add(k)
        out.append(p)
    return out


def migrate_two_years_ago_dynamic_to_static(dynamic_path: Path, static_path: Path, now_year: int) -> None:
    """
    Example:
      now_year = 2027
      move entries with year == 2025 from dynamic.ts -> static.ts
    Only runs if dynamic.ts exists and was generated in a past year.
    """
    if not dynamic_path.exists():
        return

    dyn_gen_year = read_generated_year(dynamic_path)
    if dyn_gen_year is None:
        return

    # Only do migration if dynamic file is "old" relative to now
    if dyn_gen_year >= now_year:
        return

    target_year = now_year - 2

    dyn_text = dynamic_path.read_text(encoding="utf-8")
    dyn_items = extract_exported_array(dyn_text)

    to_move = []
    for p in dyn_items:
        try:
            y = int(p.get("year"))
        except Exception:
            continue
        if y == target_year:
            to_move.append(p)

    if not to_move:
        return

    # Load existing static (if any)
    static_items = []
    if static_path.exists():
        static_text = static_path.read_text(encoding="utf-8")
        static_items = extract_exported_array(static_text)

    merged = dedupe_keep_order(static_items + to_move)

    # Write static.ts (keep your header style)
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    static_out = (
        "// AUTO-GENERATED FILE. DO NOT EDIT.\n"
        f"// Generated at: {generated_at}\n\n"
        "export const staticPubs = "
        + json.dumps(merged, ensure_ascii=False, indent=2)
        + " as const;\n"
    )
    static_path.write_text(static_out, encoding="utf-8")


def main():
    author = scholarly.search_author_id(SCHOLAR_ID)
    author = scholarly.fill(author)

    this_year = datetime.now(timezone.utc).year
    migrate_two_years_ago_dynamic_to_static(
        dynamic_path=Path("src/data/dynamic.ts"),  # adjust to your paths
        static_path=Path("src/data/static.ts"),
        now_year=this_year,
    )

    allowed_years = {this_year, this_year - 1}

    pubs = []
    for p in (author.get("publications") or []):
        full_url = f"https://scholar.google.com/citations?view_op=view_citation&hl=en&user={SCHOLAR_ID}&citation_for_view={p['author_pub_id']}"
        # Filling each pub adds requests; keep schedule infrequent.
        try:
            p_full = scholarly.fill(p, sortby='year')
        except Exception:
            p_full = p

        if int(p_full['bib']['pub_year']) not in allowed_years:
            continue

        print(p_full)

        # 1) Try BibTeX (best for full venue + correct booktitle)
        bibtex_str = ""
        fields = {}
        try:
            bibtex_str = get_bibtex_with_fallback(p_full, title=pick_title(p_full))
            fields = bibtex_to_fields(bibtex_str)

            # inside loop, right after you compute `fields`:
            if not fields:
                print(f"[bibtex] EMPTY fields for: {title}")
            elif not has_good_venue_fields(fields):
                print(f"[bibtex] NO venue keys for: {title} | keys={sorted(fields.keys())[:15]} ...")
        except Exception:
            fields = {}

        # 2) Fall back to your current pickers if BibTeX fails
        title = pick_title(p_full)
        if not title:
            continue

        fallback_authors = pick_authors(p_full)
        fallback_year = pick_year(p_full)

        candidate_year = pick_year_from_bibtex(fields, fallback=fallback_year)

        try:
            y_int = int(candidate_year)
        except Exception:
            # If year is missing/unparseable, skip (or keep, if you prefer)
            continue

        if y_int not in allowed_years:
            continue

        fallback_venue = pick_venue(p_full)
        fallback_link = pick_link(p_full)

        record = {
            "title": pick_title_from_bibtex(fields, fallback=title),
            "authors": pick_authors_from_bibtex(fields, fallback=fallback_authors),
            "venue": pick_venue_from_bibtex(fields, fallback=fallback_venue),
            "year": candidate_year,
            "links": {
                "paper": pick_url_from_bibtex(fields, fallback=fallback_link) or None,
            }
        }

        if (not record["venue"]) or ("…" in record["venue"]):
            doi = extract_doi(record["links"]["paper"] or "") or extract_doi(bibtex_str)
            if doi:
                msg = crossref_lookup(doi, mailto=os.environ.get("CROSSREF_MAILTO", ""))
                v = venue_from_crossref(msg)
                if v:
                    record["venue"] = v

        pubs.append(record)
        time.sleep(1.0)

    # Sort newest year first (string-safe)
    def year_key(r):
        try:
            return int(r["year"])
        except Exception:
            return -1
    pubs.sort(key=year_key, reverse=True)

    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    lines = []
    lines.append("// AUTO-GENERATED FILE. DO NOT EDIT.")
    lines.append(f"// Generated at: {generated_at}")
    lines.append("")
    lines.append("export const dynamicPubs = [")
    for r in pubs:
        title = ts_escape(r["title"])
        authors = ts_escape(r["authors"])
        journal = ts_escape(r["venue"])
        year = ts_escape(r["year"])
        link = r["links"]["paper"]
        link_ts = f"'{ts_escape(link)}'" if link else "undefined"

        # Keep the same keys your site expects: title/authors/journal/time/link/github/slides/abstract
        lines.append("  {")
        lines.append(f"    title: '{title}',")
        lines.append(f"    authors: '{authors}',")
        lines.append(f"    venue: '{journal}',")
        lines.append(f"    year: '{year}',")
        lines.append("    links: {")
        lines.append(f"        paper: {link_ts}")
        lines.append("    }")
        lines.append("  },")
    lines.append("];")
    lines.append("")

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"Wrote {len(pubs)} publications -> {OUT_PATH}")

if __name__ == "__main__":
    main()