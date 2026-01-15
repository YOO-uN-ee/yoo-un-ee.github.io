#!/usr/bin/env python3
"""
Usage:
  pip install scholarly
  python3 scholar_profile_to_bib_scholarly.py --user_id Xf3M93cAAAAJ --out publications.bib
"""

import argparse
import sys
import time
from scholarly import scholarly


query = scholarly.search_pubs("Leveraging Large Language Models for Generating Labeled Mineral Site Record Linkage Data")
pub = next(query)
print(scholarly.bibtex(pub))

# def main():
#     ap = argparse.ArgumentParser()
#     ap.add_argument("--user_id", default="RpcilLMAAAAJ")
#     ap.add_argument("--out", default="./publications.bib")
#     ap.add_argument("--sleep", type=float, default=1.0, help="Delay between BibTeX fetches (seconds)")
#     args = ap.parse_args()

#     author = scholarly.search_author_id(args.user_id)
#     author = scholarly.fill(author, sections=["publications"])

#     pubs = author.get("publications", []) or []
#     print(f"[INFO] Found {len(pubs)} publications", file=sys.stderr)

#     with open(args.out, "w", encoding="utf-8") as f:
#         for i, pub in enumerate(pubs, 1):
#             # Fill each publication so bibtex export has enough data
#             pub_filled = scholarly.fill(pub)
#             bib = scholarly.bibtex(pub_filled)
#             f.write(bib.strip())
#             f.write("\n\n")
#             if args.sleep:
#                 time.sleep(args.sleep)

#     print(f"[INFO] Wrote {len(pubs)} entries to {args.out}", file=sys.stderr)


# if __name__ == "__main__":
#     main()