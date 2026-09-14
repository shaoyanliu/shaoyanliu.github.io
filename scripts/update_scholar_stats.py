#!/usr/bin/env python3
"""Save a complete, validated snapshot of a public Google Scholar profile."""

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
import yaml

DEFAULT_DATA = Path(__file__).resolve().parents[1] / "_data/scholar_stats.yml"
PAGE_SIZE = 100
MAX_PAGES = 20


class ScholarError(ValueError):
    """An incomplete or unexpected response must never replace saved data."""


def parse_count(text):
    text = text.strip()
    if not re.fullmatch(r"(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)", text):
        raise ScholarError("A citation metric is missing or is not an integer.")
    return int(text.replace(",", ""))


def fetch_page(profile_id, start):
    query = urlencode({"user": profile_id, "hl": "en", "cstart": start,
                       "pagesize": PAGE_SIZE})
    request = Request("https://scholar.google.com/citations?" + query,
                      headers={"User-Agent": "Mozilla/5.0",
                               "Accept-Language": "en-US,en;q=0.9"})
    try:
        with urlopen(request, timeout=30) as response:
            return response.read().decode("utf-8")
    except HTTPError as error:
        raise ScholarError(f"Google Scholar returned HTTP {error.code}.") from None
    except (URLError, TimeoutError, UnicodeError):
        raise ScholarError("Could not read Google Scholar; try again later.") from None


def parse_page(html, profile_id, first_page):
    soup = BeautifulSoup(html, "html.parser")
    if not soup.select_one("#gsc_prf_in"):
        raise ScholarError("No public profile found (possibly a verification page).")

    metrics = {}
    if first_page:
        table = soup.select_one("#gsc_rsb_st")
        if table is None:
            raise ScholarError("The citation statistics table is missing.")
        headings = table.select("thead th")
        if len(headings) < 2 or headings[1].get_text(strip=True) != "All":
            raise ScholarError("Could not identify the all-time statistics column.")
        for row in table.select("tbody tr"):
            cells = row.select("td")
            if len(cells) < 2:
                continue
            key = {"Citations": "citations", "h-index": "h_index"}.get(
                cells[0].get_text(strip=True))
            if key:
                metrics[key] = parse_count(cells[1].get_text(strip=True))
        if set(metrics) != {"citations", "h_index"}:
            raise ScholarError("Citations or h-index is missing.")

    article_ids = []
    for row in soup.select("#gsc_a_b .gsc_a_tr"):
        link = row.select_one("a.gsc_a_at[href]")
        if link is None:
            raise ScholarError("An article has no identifiable title link.")
        ids = parse_qs(urlparse(link["href"]).query).get("citation_for_view", [])
        if len(ids) != 1 or not re.fullmatch(re.escape(profile_id) + r":[A-Za-z0-9_-]+", ids[0]):
            raise ScholarError("An article does not match the requested profile.")
        article_ids.append(ids[0])
    more = soup.select_one("#gsc_bpf_more")
    if more is None or not article_ids:
        raise ScholarError("The article list or its pagination is missing.")
    return metrics, article_ids, not more.has_attr("disabled")


def collect_stats(profile_id, fetch=fetch_page):
    if not isinstance(profile_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", profile_id):
        raise ScholarError("The saved Google Scholar profile ID is invalid.")
    seen = set()
    metrics = {}
    for page_number in range(MAX_PAGES):
        page_metrics, article_ids, has_more = parse_page(
            fetch(profile_id, len(seen)), profile_id, first_page=page_number == 0)
        if page_number == 0:
            metrics = page_metrics
        if len(set(article_ids)) != len(article_ids) or seen.intersection(article_ids):
            raise ScholarError("Repeated articles found; pagination may have failed.")
        seen.update(article_ids)
        if not has_more:
            if metrics["h_index"] > len(seen) or metrics["citations"] < metrics["h_index"] ** 2:
                raise ScholarError("The profile returned inconsistent statistics.")
            return {"profile_id": profile_id, "papers": len(seen), **metrics,
                    "updated": datetime.now(ZoneInfo("America/New_York")).date().isoformat()}
    raise ScholarError("The article list exceeded the page limit; snapshot unchanged.")


def update_snapshot(path=DEFAULT_DATA, dry_run=False, fetch=fetch_page):
    previous = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(previous, dict):
        raise ScholarError("The saved statistics file is invalid.")
    snapshot = collect_stats(previous.get("profile_id"), fetch)
    if not dry_run and snapshot != previous:
        contents = (
            "# Updated by scripts/update_scholar_stats.py after a successful fetch.\n"
            "# updated is the last successful check date in America/New_York.\n"
            + yaml.safe_dump(snapshot, sort_keys=False)
        )
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                             prefix=".scholar-stats-", delete=False) as output:
                temporary = Path(output.name)
                output.write(contents)
            temporary.replace(path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
    return snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--dry-run", action="store_true", help="Fetch and validate without saving")
    args = parser.parse_args()
    try:
        snapshot = update_snapshot(args.data, args.dry_run)
    except (ScholarError, OSError, yaml.YAMLError) as error:
        print(f"Scholar update failed: {error} Saved statistics were not replaced.", file=sys.stderr)
        return 1
    print(json.dumps(snapshot, indent=2))
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
            summary.write(f"Google Scholar checked {snapshot['updated']}: "
                          f"{snapshot['papers']} papers, {snapshot['citations']} citations, "
                          f"h-index {snapshot['h_index']}.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
