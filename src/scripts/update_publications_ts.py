#!/usr/bin/env python3
import json
import logging
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from urllib.parse import quote

import bibtexparser
import json5
import requests
from scholarly import scholarly

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
    r = requests.get(url, params=params, timeout=15)
    r.raise_for_status()
    data = r.json()
    message = data.get("message") if isinstance(data, dict) else None
    return message if isinstance(message, dict) else {}

def venue_from_crossref(msg: dict) -> str:
    # Crossref: container-title is usually what you want for proceedings/books/journals
    ct = msg.get("container-title") or []
    if isinstance(ct, list) and ct and isinstance(ct[0], str) and ct[0].strip():
        return ct[0].strip()
    # Sometimes "event" exists for conference metadata
    ev = msg.get("event") or {}
    name = ev.get("name") if isinstance(ev, dict) else None
    return name.strip() if isinstance(name, str) else ""

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
    except Exception as exc:
        logging.info("Direct BibTeX lookup failed for %r: %s", title, exc)

    # 2) Fallback: search by title (search results often have the needed IDs)
    try:
        q = scholarly.search_pubs(title)
        pub2 = next(q, None)
        if not pub2:
            return ""
        pub2 = scholarly.fill(pub2)
        return scholarly.bibtex(pub2) or ""
    except Exception as exc:
        logging.warning("BibTeX lookup failed for %r: %s", title, exc)
        return ""


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

def publication_year(value: object) -> int | None:
    try:
        return int(str(value).strip())
    except ValueError:
        return None


def read_publications(path: Path, export_name: str) -> list[dict]:
    if not path.exists():
        return []

    ts_text = path.read_text(encoding="utf-8")
    match = re.search(
        rf"^export const {export_name}\s*=\s*(\[.*\])\s*(?:as const)?\s*;?\s*$",
        ts_text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if not match:
        raise ValueError(f"Could not read {export_name} in {path}")

    # Older generated files use single quotes, unquoted keys and paper: undefined.
    source = re.sub(
        r"(?m)^([ \t]*paper:[ \t]*)undefined(?=\s*[,}])",
        r"\g<1>null",
        match.group(1),
    )
    publications = json5.loads(source)
    if not all(isinstance(pub, dict) for pub in publications):
        raise ValueError(f"Invalid publication entries in {path}")
    return publications


def write_publications(path: Path, export_name: str, publications: list[dict]) -> None:
    generated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    data = json.dumps(publications, ensure_ascii=False, indent=2)
    content = (
        "// AUTO-GENERATED FILE. DO NOT EDIT.\n"
        f"// Generated at: {generated_at}\n\n"
        f"export const {export_name} = {data};\n"
    )

    path.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=path.parent, delete=False,
    ) as temp_file:
        temp_path = Path(temp_file.name)
        try:
            temp_file.write(content)
            temp_file.close()
            temp_path.replace(path)
        finally:
            temp_path.unlink(missing_ok=True)


def title_key(pub: dict) -> str:
    return " ".join(pub["title"].casefold().split())


def archive_old_publications(
    static_path: Path, existing_pubs: list[dict], first_dynamic_year: int,
) -> None:
    to_move = []
    for pub in existing_pubs:
        year = publication_year(pub.get("year"))
        if year is not None and year < first_dynamic_year:
            to_move.append(pub)
    if not to_move:
        return

    static_pubs = read_publications(static_path, "staticPubs")
    original_count = len(static_pubs)
    known_titles = {title_key(pub) for pub in static_pubs}
    for pub in to_move:
        key = title_key(pub)
        if key not in known_titles:
            static_pubs.append(pub)
            known_titles.add(key)
    if len(static_pubs) != original_count:
        write_publications(static_path, "staticPubs", static_pubs)


def fetch_publication_record(pub: dict, allowed_years: set[int]) -> dict | None:
    year = publication_year(pick_year(pub))
    if year is not None and year not in allowed_years:
        return None

    try:
        full_pub = scholarly.fill(pub) if pub.get("author_pub_id") else pub
    except Exception as exc:
        logging.warning("Scholar details unavailable for %r: %s", pick_title(pub), exc)
        full_pub = pub

    title = pick_title(full_pub)
    if not title:
        return None

    bibtex = get_bibtex_with_fallback(full_pub, title)
    fields = bibtex_to_fields(bibtex)
    year = publication_year(pick_year_from_bibtex(fields, fallback=pick_year(full_pub)))
    if year not in allowed_years:
        return None

    venue = pick_venue_from_bibtex(fields, fallback=pick_venue(full_pub))
    link = pick_url_from_bibtex(fields, fallback=pick_link(full_pub))
    if not venue or "…" in venue:
        doi = extract_doi(link) or extract_doi(bibtex)
        if doi:
            try:
                message = crossref_lookup(doi, mailto=os.environ.get("CROSSREF_MAILTO", ""))
                venue = venue_from_crossref(message) or venue
            except (requests.RequestException, ValueError) as exc:
                logging.warning("Crossref lookup failed for %r: %s", title, exc)

    return {
        "title": pick_title_from_bibtex(fields, fallback=title),
        "authors": pick_authors_from_bibtex(fields, fallback=pick_authors(full_pub)),
        "venue": venue,
        "year": str(year),
        "links": {"paper": link or None},
    }


def main() -> int:
    scholarly.set_timeout(12)
    scholarly.set_retries(2)

    print("[scholarly] Fetching publication list directly from Google Scholar")
    try:
        author = scholarly.search_author_id(SCHOLAR_ID)
        author = scholarly.fill(author, sections=["publications"], sortby="year")
    except Exception as exc:
        logging.warning("Google Scholar profile unavailable. Keeping publication files: %s", exc)
        return 75

    this_year = datetime.now(timezone.utc).year
    allowed_years = {this_year, this_year - 1}
    fetched_pubs = []
    for pub in author.get("publications") or []:
        record = fetch_publication_record(pub, allowed_years)
        if record:
            fetched_pubs.append(record)
            time.sleep(1.0)

    if not fetched_pubs:
        logging.warning("Google Scholar returned no usable recent publications. Keeping publication files.")
        return 75

    print(f"[scholarly] Fetched {len(fetched_pubs)} usable recent publications")

    dynamic_path = Path(OUT_PATH)
    existing_pubs = read_publications(dynamic_path, "dynamicPubs")
    previous_by_title = {title_key(pub): pub for pub in existing_pubs}
    recent_pubs = {
        key: pub for key, pub in previous_by_title.items()
        if publication_year(pub.get("year")) in allowed_years
    }
    for record in fetched_pubs:
        key = title_key(record)
        previous = previous_by_title.get(key, {})
        previous_links = previous.get("links") or {}
        venue = record["venue"]
        if not venue or "…" in venue:
            venue = previous.get("venue") or venue
        recent_pubs[key] = {
            **previous,
            **record,
            "authors": record["authors"] or previous.get("authors", ""),
            "venue": venue,
            "links": {
                **previous_links,
                "paper": record["links"]["paper"] or previous_links.get("paper"),
            },
        }

    pubs = sorted(recent_pubs.values(), key=lambda pub: int(pub["year"]), reverse=True)
    archive_old_publications(
        dynamic_path.with_name("static.ts"),
        [pub for pub in existing_pubs if title_key(pub) not in recent_pubs],
        this_year - 1,
    )
    if pubs == existing_pubs:
        print(f"[scholarly] {len(pubs)} publications already up to date")
        return 0

    write_publications(dynamic_path, "dynamicPubs", pubs)
    print(f"Wrote {len(pubs)} publications -> {dynamic_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
