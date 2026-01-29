#!/usr/bin/env python3
"""
Option 2: Scholar-free BibTeX exporter (no Google Scholar scraping).

Goal:
- Avoid Scholar ellipses/truncation.
- Get full venue/booktitle/journal from authoritative metadata.
- Produce a merged .bib.

Inputs:
- A list of "records" where each record can include a DOI, an arXiv id, or at least a title.
  You can hand-maintain a small list, or generate it from your existing TS/JSON.

Sources:
- Crossref Works API (best for DOI + full container-title / event / proceedings, etc.)
- arXiv Atom API (best for arXiv IDs + abstract)
- Fallback: Crossref title query (works?query.title=...)

Requires:
- requests
- bibtexparser

Usage:
  python3 export_bib_option2.py

Env:
  OUT_BIB=publications.bib
  CROSSREF_MAILTO=you@umn.edu   (recommended per Crossref etiquette)
"""

import os
import re
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, List, Dict, Any
from urllib.parse import quote

import requests
import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase

OUT_BIB = os.environ.get("OUT_BIB", "publications.bib")
CROSSREF_MAILTO = os.environ.get("CROSSREF_MAILTO", "")
SLEEP_SEC = float(os.environ.get("SLEEP_SEC", "0.5"))

DOI_RE = re.compile(r"(10\.\d{4,9}/[-._;()/:A-Z0-9]+)", re.I)
ARXIV_ID_RE = re.compile(
    r"(?:arxiv\.org/(?:abs|pdf)/|arxiv:)\s*([0-9]{4}\.[0-9]{4,5}(?:v\d+)?|[a-z\-]+/[0-9]{7}(?:v\d+)?)",
    re.I,
)
ARXIV_PLAIN_RE = re.compile(
    r"^\s*([0-9]{4}\.[0-9]{4,5}(?:v\d+)?|[a-z\-]+/[0-9]{7}(?:v\d+)?)\s*$",
    re.I,
)


# -----------------------------
# Your input list (edit this)
# -----------------------------
# -----------------------------
# Auto-populate RECORDS from Google Scholar (scholarly)
# -----------------------------
# Usage:
#   SCHOLAR_ID=RpcilLMAAAAJ python3 export_bib_option2.py
# Optional:
#   SCHOLAR_MAX_PUBS=200  (default: no limit)
#   SCHOLAR_SLEEP_SEC=1.0 (default: 0.8)

SCHOLAR_ID = os.environ.get("SCHOLAR_ID", "RpcilLMAAAAJ").strip()
SCHOLAR_MAX_PUBS = os.environ.get("SCHOLAR_MAX_PUBS", "").strip()
SCHOLAR_SLEEP_SEC = float(os.environ.get("SCHOLAR_SLEEP_SEC", "0.8"))

# -----------------------------
# Utilities
# -----------------------------
def build_records_from_scholar(scholar_id: str) -> List[Dict[str, str]]:
    """
    Build RECORDS list from Google Scholar using scholarly.
    Priority:
      1) DOI (from bib fields or URLs)
      2) arXiv id (from eprint_url/pub_url/bib url)
      3) title
    De-dupes by (doi|arxiv|title).
    """
    if not scholar_id:
        return []

    try:
        from scholarly import scholarly  # pip install scholarly
    except Exception as e:
        raise SystemExit("Missing dependency 'scholarly'. Install with: pip install scholarly") from e

    # Helper: gather candidate text to mine DOI/arXiv from
    def _candidate_texts(pub: Dict[str, Any]) -> List[str]:
        bib = pub.get("bib") or {}
        cands = []
        for k in ("doi", "url", "eprint", "title"):
            if bib.get(k):
                cands.append(safe_str(bib.get(k)))
        for k in ("pub_url", "eprint_url", "author_pub_url"):
            if pub.get(k):
                cands.append(safe_str(pub.get(k)))
        # sometimes urls are nested
        if isinstance(pub.get("source"), str):
            cands.append(safe_str(pub.get("source")))
        return [c for c in cands if c]

    # Fetch author + publications list
    author = scholarly.search_author_id(scholar_id)
    author = scholarly.fill(author, sections=["publications"])

    pubs = author.get("publications") or []
    if SCHOLAR_MAX_PUBS.isdigit():
        pubs = pubs[: int(SCHOLAR_MAX_PUBS)]

    records: List[Dict[str, str]] = []
    seen = set()

    for i, p in enumerate(pubs, 1):
        # Fill each publication to get more complete bib fields (may be slower)
        try:
            p_full = scholarly.fill(p)
        except Exception:
            # If fill fails (rate limit/captcha), fall back to unfilled pub
            p_full = p

        title = safe_str((p_full.get("bib") or {}).get("title") or p_full.get("bib", {}).get("citation") or "")
        texts = _candidate_texts(p_full)

        doi = ""
        arxiv_id = ""
        for t in texts:
            if not doi:
                doi = extract_doi(t)
            if not arxiv_id:
                arxiv_id = extract_arxiv_id(t)
            if doi and arxiv_id:
                break

        # Decide record type
        if doi:
            key = f"doi:{doi.lower()}"
            rec = {"doi": doi}
        elif arxiv_id:
            key = f"arxiv:{arxiv_id.lower()}"
            rec = {"arxiv": arxiv_id}
        else:
            if not title:
                # as a last resort, skip empty entries
                time.sleep(SCHOLAR_SLEEP_SEC)
                continue
            key = f"title:{title.lower()}"
            rec = {"title": title}

        if key not in seen:
            seen.add(key)
            records.append(rec)

        time.sleep(SCHOLAR_SLEEP_SEC)

    return records


def safe_str(x) -> str:
    if x is None:
        return ""
    if isinstance(x, str):
        return x.strip()
    if isinstance(x, (int, float)):
        return str(x).strip()
    if isinstance(x, (list, tuple)):
        return " ".join(safe_str(v) for v in x if v is not None).strip()
    return str(x).strip()

def normalize_ws(s: str) -> str:
    s = safe_str(s)
    s = s.replace("\r", "")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r"\s*\n\s*", "\n", s).strip()
    return s

def slug(s: str) -> str:
    s = safe_str(s).lower()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r"[^a-z0-9]+", "", s)
    return s[:40] or "pub"

def extract_doi(text: str) -> str:
    if not text:
        return ""
    m = DOI_RE.search(text)
    return m.group(1) if m else ""

def extract_arxiv_id(text: str) -> str:
    if not text:
        return ""
    text = safe_str(text)

    # 1) prefixed forms: arxiv:XXXX or arxiv.org/abs/XXXX
    m = ARXIV_ID_RE.search(text)
    if m:
        return m.group(1)

    # 2) plain id: "2512.08016" or "cs/0501001"
    m = ARXIV_PLAIN_RE.match(text)
    return m.group(1) if m else ""


def make_citekey(author_last: str, year: str, title: str) -> str:
    y = year if (year or "").isdigit() else "nd"
    return f"{slug(author_last)}{y}{slug(title)}"

def unique_id(base: str, used: set) -> str:
    base = base or "pub"
    if base not in used:
        used.add(base)
        return base
    i = 2
    while f"{base}{i}" in used:
        i += 1
    new_id = f"{base}{i}"
    used.add(new_id)
    return new_id

# -----------------------------
# Crossref
# -----------------------------
def crossref_get(doi: str, session: requests.Session) -> Dict[str, Any]:
    url = "https://api.crossref.org/works/" + quote(doi, safe="")
    params = {"mailto": CROSSREF_MAILTO} if CROSSREF_MAILTO else {}
    r = session.get(url, params=params, timeout=25)
    r.raise_for_status()
    return (r.json() or {}).get("message", {}) or {}

def crossref_search_by_title(title: str, session: requests.Session, rows: int = 5) -> Optional[Dict[str, Any]]:
    """
    Try to find the best Crossref work for a title.
    This is not perfect, but it's a solid fallback when DOI isn't available.
    """
    if not title:
        return None
    url = "https://api.crossref.org/works"
    params = {
        "query.title": title,
        "rows": rows,
    }
    if CROSSREF_MAILTO:
        params["mailto"] = CROSSREF_MAILTO
    r = session.get(url, params=params, timeout=25)
    r.raise_for_status()
    items = (((r.json() or {}).get("message") or {}).get("items") or [])
    return items[0] if items else None

def cr_pick_year(msg: Dict[str, Any]) -> str:
    for key in ("published-print", "published-online", "issued", "created"):
        dp = (msg.get(key) or {}).get("date-parts")
        if dp and isinstance(dp, list) and dp[0] and isinstance(dp[0], list) and dp[0][0]:
            y = str(dp[0][0])
            if y.isdigit():
                return y
    return ""

def cr_pick_title(msg: Dict[str, Any]) -> str:
    t = msg.get("title")
    if isinstance(t, list) and t:
        return safe_str(t[0])
    return safe_str(t)

def cr_pick_authors(msg: Dict[str, Any]) -> str:
    authors = msg.get("author") or []
    parts = []
    for a in authors:
        if not isinstance(a, dict):
            continue
        family = safe_str(a.get("family"))
        given = safe_str(a.get("given"))
        if family and given:
            parts.append(f"{family}, {given}")
        elif family:
            parts.append(family)
        elif given:
            parts.append(given)
    return " and ".join(parts)

def cr_first_author_last(msg: Dict[str, Any]) -> str:
    authors = msg.get("author") or []
    for a in authors:
        if isinstance(a, dict):
            fam = safe_str(a.get("family"))
            if fam:
                return fam
    return "unknown"

def cr_pick_url(msg: Dict[str, Any], doi: str) -> str:
    return safe_str(msg.get("URL")) or (f"https://doi.org/{doi}" if doi else "")

def cr_pick_doi(msg: Dict[str, Any]) -> str:
    return safe_str(msg.get("DOI"))

def cr_pick_container(msg: Dict[str, Any]) -> str:
    """
    container-title is typically journal or proceedings series.
    """
    ct = msg.get("container-title")
    if isinstance(ct, list) and ct:
        return safe_str(ct[0])
    return safe_str(ct)

def cr_pick_event_name(msg: Dict[str, Any]) -> str:
    ev = msg.get("event") or {}
    if isinstance(ev, dict):
        return safe_str(ev.get("name"))
    return ""

def cr_pick_publisher(msg: Dict[str, Any]) -> str:
    return safe_str(msg.get("publisher"))

def cr_pick_pages(msg: Dict[str, Any]) -> str:
    return safe_str(msg.get("page"))

def cr_pick_volume(msg: Dict[str, Any]) -> str:
    return safe_str(msg.get("volume"))

def cr_pick_issue(msg: Dict[str, Any]) -> str:
    return safe_str(msg.get("issue"))

def cr_pick_isbn(msg: Dict[str, Any]) -> str:
    isbn = msg.get("ISBN")
    if isinstance(isbn, list) and isbn:
        return safe_str(isbn[0])
    return safe_str(isbn)

def cr_pick_abstract(msg: Dict[str, Any]) -> str:
    a = safe_str(msg.get("abstract"))
    if not a:
        return ""
    # Crossref abstracts can be JATS XML; strip tags lightly
    a = re.sub(r"<[^>]+>", "", a)
    a = re.sub(r"\s+", " ", a).strip()
    return a

def cr_guess_entrytype(msg: Dict[str, Any]) -> str:
    t = safe_str(msg.get("type")).lower()
    # Crossref 'type' examples: journal-article, proceedings-article, posted-content, book-chapter
    if "proceedings" in t:
        return "inproceedings"
    if "journal" in t or "article" in t:
        return "article"
    if "book-chapter" in t or "chapter" in t:
        return "incollection"
    if "book" in t:
        return "book"
    return "misc"

def crossref_to_bib_entry(msg: Dict[str, Any]) -> Dict[str, str]:
    doi = cr_pick_doi(msg)
    title = cr_pick_title(msg)
    author = cr_pick_authors(msg)
    year = cr_pick_year(msg)
    url = cr_pick_url(msg, doi=doi)
    container = cr_pick_container(msg)
    event = cr_pick_event_name(msg)
    publisher = cr_pick_publisher(msg)
    pages = cr_pick_pages(msg)
    volume = cr_pick_volume(msg)
    issue = cr_pick_issue(msg)
    isbn = cr_pick_isbn(msg)
    abstract = cr_pick_abstract(msg)

    entrytype = cr_guess_entrytype(msg)
    citekey = make_citekey(cr_first_author_last(msg), year, title)

    entry: Dict[str, str] = {
        "ENTRYTYPE": entrytype,
        "ID": citekey,
        "title": title,
        "author": author,
        "year": year,
    }

    # Venue handling:
    # - inproceedings: booktitle is the primary venue field
    # - article: journal is the primary venue field
    if entrytype == "inproceedings":
        # Prefer event name when present; else container-title
        if event:
            entry["booktitle"] = event
        elif container:
            entry["booktitle"] = container
        elif publisher:
            entry["booktitle"] = publisher
    elif entrytype in ("article",):
        if container:
            entry["journal"] = container
    else:
        # fallback: store container as journal if present
        if container:
            entry["journal"] = container

    if url:
        entry["url"] = url
    if doi:
        entry["doi"] = doi
    if publisher:
        entry["publisher"] = publisher
    if pages:
        entry["pages"] = pages
    if volume:
        entry["volume"] = volume
    if issue:
        entry["number"] = issue
    if isbn and entrytype in ("book", "incollection", "inproceedings"):
        entry["isbn"] = isbn
    if abstract:
        entry["abstract"] = abstract

    # Keep a few other useful fields if present
    issn = msg.get("ISSN")
    if isinstance(issn, list) and issn:
        entry["issn"] = safe_str(issn[0])

    return {k: normalize_ws(v) for k, v in entry.items() if safe_str(v)}

# -----------------------------
# arXiv
# -----------------------------
def arxiv_get(arxiv_id: str, session: requests.Session) -> Dict[str, Any]:
    api = f"https://export.arxiv.org/api/query?id_list={quote(arxiv_id)}"
    r = session.get(api, timeout=25)
    r.raise_for_status()
    xml = r.text or ""

    def _tag(tag: str) -> str:
        m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", xml, re.S | re.I)
        return (m.group(1) or "").strip() if m else ""

    title = re.sub(r"\s+", " ", _tag("title")).strip()
    summary = re.sub(r"\s+", " ", _tag("summary")).strip()
    updated = _tag("updated")
    year = updated[:4] if len(updated) >= 4 and updated[:4].isdigit() else ""

    authors = re.findall(r"<name[^>]*>(.*?)</name>", xml, re.S | re.I)
    authors = [re.sub(r"\s+", " ", a).strip() for a in authors if a.strip()]

    entry_id = re.search(r"<id[^>]*>(.*?)</id>", xml, re.S | re.I)
    url = re.sub(r"\s+", " ", entry_id.group(1)).strip() if entry_id else ""
    if not url:
        url = f"https://arxiv.org/abs/{arxiv_id}"
    if "/pdf/" in url:
        url = url.replace("/pdf/", "/abs/").replace(".pdf", "")

    return {"title": title, "authors": authors, "year": year, "url": url, "abstract": summary, "arxiv": arxiv_id}

def arxiv_to_bib_entry(ax: Dict[str, Any]) -> Dict[str, str]:
    title = safe_str(ax.get("title"))
    authors = ax.get("authors") or []
    author = " and ".join(authors)
    year = safe_str(ax.get("year"))
    url = safe_str(ax.get("url"))
    arxiv_id = safe_str(ax.get("arxiv"))
    abstract = safe_str(ax.get("abstract"))

    first_last = "unknown"
    if authors:
        # "First Last" -> Last
        first_last = authors[0].split()[-1]

    entry = {
        "ENTRYTYPE": "article",
        "ID": make_citekey(first_last, year, title),
        "title": title,
        "author": author,
        "year": year,
        "journal": f"arXiv preprint arXiv:{arxiv_id}" if arxiv_id else "arXiv preprint",
        "url": url,
    }
    if arxiv_id:
        entry["eprint"] = arxiv_id
        entry["archiveprefix"] = "arXiv"
    if abstract:
        entry["abstract"] = abstract

    return {k: normalize_ws(v) for k, v in entry.items() if safe_str(v)}

# -----------------------------
# Build entries
# -----------------------------
def entry_from_record(rec: Dict[str, Any], session: requests.Session) -> Optional[Dict[str, str]]:
    doi = extract_doi(safe_str(rec.get("doi") or rec.get("url") or ""))
    arxiv_id = extract_arxiv_id(safe_str(rec.get("arxiv") or rec.get("url") or ""))
    title = safe_str(rec.get("title"))

    # 1) DOI -> Crossref (best)
    if doi:
        msg = crossref_get(doi, session)
        return crossref_to_bib_entry(msg)

    # 2) arXiv -> arXiv API
    if arxiv_id:
        ax = arxiv_get(arxiv_id, session)
        return arxiv_to_bib_entry(ax)

    # 3) Title -> Crossref search fallback
    if title:
        msg = crossref_search_by_title(title, session)
        if msg:
            return crossref_to_bib_entry(msg)

    return None


# -----------------------------
# Your input list (edit this)
# -----------------------------
RECORDS = [
    # You can still manually add/override entries here if you want, e.g.:
    # {"doi": "10.1145/3764915.3770723"},
]

# If empty, auto-populate from Scholar
if not RECORDS and SCHOLAR_ID:
    RECORDS = build_records_from_scholar(SCHOLAR_ID)



def main():
    if not RECORDS:
        raise SystemExit(
            "RECORDS is empty. Add items like:\n"
            "  {'doi': '10.1145/...'} or {'arxiv': '2503.07871'} or {'title': '...'}\n"
            "If you have your publications list in TS/JSON, paste it and I can generate RECORDS automatically."
        )

    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    })

    used_ids = set()
    entries: List[Dict[str, str]] = []

    for i, rec in enumerate(RECORDS, 1):
        try:
            e = entry_from_record(rec, session)
        except Exception as ex:
            print(f"[WARN] record #{i} failed: {rec}\n       -> {ex}")
            time.sleep(SLEEP_SEC)
            continue

        if not e:
            print(f"[WARN] record #{i} produced no entry: {rec}")
            time.sleep(SLEEP_SEC)
            continue

        # ensure unique citekey
        e["ID"] = unique_id(e.get("ID", "pub"), used_ids)
        entries.append(e)

        print(f"[OK] {i}/{len(RECORDS)} {e.get('ID')} | {e.get('title','')[:80]}")
        time.sleep(SLEEP_SEC)

    db = BibDatabase()
    db.entries = entries

    writer = BibTexWriter()
    writer.indent = "  "
    writer.order_entries_by = None

    header = [
        "% AUTO-GENERATED FILE. DO NOT EDIT.",
        f"% Generated at: {datetime.utcnow().isoformat()}Z",
        "",
    ]

    os.makedirs(os.path.dirname(OUT_BIB) or ".", exist_ok=True)
    with open(OUT_BIB, "w", encoding="utf-8") as f:
        f.write("\n".join(header))
        f.write(writer.write(db))

    print(f"[DONE] wrote {len(entries)} entries -> {OUT_BIB}")

if __name__ == "__main__":
    main()
