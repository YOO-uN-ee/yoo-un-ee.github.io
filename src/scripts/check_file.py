#!/usr/bin/env python3
"""
Export *raw* BibTeX entries for all publications on a Google Scholar profile.

- No field filtering or reconstruction.
- Collects all BibTeX fields exactly as returned by scholarly.bibtex().
- Fallback: search by title if direct bibtex() fails.
- Deduplicates by (ENTRYTYPE, ID) and resolves ID collisions.

Requires: scholarly, bibtexparser
"""

import os
import re
import time
from datetime import datetime

import bibtexparser
from bibtexparser.bwriter import BibTexWriter
from bibtexparser.bibdatabase import BibDatabase
from scholarly import scholarly

SCHOLAR_ID = os.environ.get("SCHOLAR_ID", "RpcilLMAAAAJ")
OUT_BIB = os.environ.get("OUT_BIB", "publications.bib")
SLEEP_SEC = float(os.environ.get("SLEEP_SEC", "1.0"))

if not SCHOLAR_ID:
    raise SystemExit("Missing SCHOLAR_ID (the `user=` value from your Scholar profile URL).")


def safe_str(x) -> str:
    """Convert scholar fields to a safe string (handles int/None/etc.)."""
    if x is None:
        return ""
    if isinstance(x, str):
        return x
    return str(x)


def pick_title(pub: dict) -> str:
    bib = pub.get("bib", {}) or {}
    return safe_str(bib.get("title")).strip()


def get_bibtex_with_fallback(p_full: dict, title: str) -> str:
    # 1) Try direct bibtex
    try:
        s = scholarly.bibtex(p_full)
        if s and s.strip():
            return s
    except Exception:
        pass

    # 2) Fallback: search by title then bibtex
    if not title:
        return ""
    try:
        q = scholarly.search_pubs(title)
        pub2 = next(q, None)
        if not pub2:
            return ""
        pub2 = scholarly.fill(pub2)
        s2 = scholarly.bibtex(pub2)
        return s2.strip() if s2 else ""
    except Exception:
        return ""


def parse_entries_from_bibtex(bibtex_str: str):
    """Parse BibTeX string into entries (usually 1). Returns list[dict]."""
    if not bibtex_str or not bibtex_str.strip():
        return []
    try:
        db = bibtexparser.loads(bibtex_str)
    except Exception:
        return []
    return list(getattr(db, "entries", []) or [])


def unique_id(base: str, used: set[str]) -> str:
    """Ensure citekey is unique by appending suffix numbers."""
    if base not in used:
        used.add(base)
        return base
    i = 2
    while f"{base}{i}" in used:
        i += 1
    new_id = f"{base}{i}"
    used.add(new_id)
    return new_id


def main():
    author = scholarly.search_author_id(SCHOLAR_ID)
    author = scholarly.fill(author)

    collected = []
    seen_sig = set()     # (ENTRYTYPE, ID) after collision handling
    used_ids = set()     # citekey uniqueness across all entries

    pubs = author.get("publications") or []
    print(f"[INFO] found {len(pubs)} publications on scholar profile")

    for idx, p in enumerate(pubs, 1):
        try:
            print(f"[dbg] about to fill pub #{idx}")
            p_full = scholarly.fill(p)
        except Exception:
            p_full = p

        title = pick_title(p_full)
        print(f"[dbg] about to bibtex pub #{idx}: {title}")
        bibtex_str = get_bibtex_with_fallback(p_full, title=title)

        if not bibtex_str:
            print(f"[WARN] no bibtex for: {title or '(no title)'}")
            time.sleep(SLEEP_SEC)
            continue

        entries = parse_entries_from_bibtex(bibtex_str)
        if not entries:
            print(f"[WARN] could not parse bibtex for: {title or '(no title)'}")
            time.sleep(SLEEP_SEC)
            continue

        for e in entries:
            # bibtexparser expects keys ENTRYTYPE and ID
            et = safe_str(e.get("ENTRYTYPE")).strip() or "misc"
            cid = safe_str(e.get("ID")).strip()

            # Some BibTeX blobs can be missing ID; fabricate a stable-ish one.
            if not cid:
                # fallback citekey: scholar_{index}
                cid = f"scholar_{idx:04d}"

            # Ensure the citekey is unique in the output file
            cid2 = unique_id(cid, used_ids)
            e["ENTRYTYPE"] = et
            e["ID"] = cid2

            sig = (et, cid2)
            if sig in seen_sig:
                continue
            seen_sig.add(sig)

            collected.append(e)

        print(f"[OK] {idx}/{len(pubs)} bibtex captured: {title or '(no title)'}")
        time.sleep(SLEEP_SEC)

    # Write .bib
    db = BibDatabase()
    db.entries = collected

    writer = BibTexWriter()
    writer.indent = "  "
    writer.order_entries_by = None  # preserve collection order
    writer.comma_first = False

    header = [
        "% AUTO-GENERATED FILE. DO NOT EDIT.",
        f"% Generated at: {datetime.utcnow().isoformat()}Z",
        f"% Scholar ID: {SCHOLAR_ID}",
        "",
    ]

    os.makedirs(os.path.dirname(OUT_BIB) or ".", exist_ok=True)
    with open(OUT_BIB, "w", encoding="utf-8") as f:
        f.write("\n".join(header))
        f.write(writer.write(db))

    print(f"[COMPLETE] wrote {len(collected)} BibTeX entries -> {OUT_BIB}")


if __name__ == "__main__":
    main()
