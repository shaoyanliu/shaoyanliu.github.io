#!/usr/bin/env python3
"""Save a complete, validated snapshot of a public Google Scholar profile."""

import argparse
from datetime import datetime, timezone
from http.client import HTTPException
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
import yaml

DEFAULT_DATA = Path(__file__).resolve().parents[1] / "_data/scholar_stats.yml"
PAGE_SIZE = 100
MAX_PAGES = 20
SERPAPI_ENDPOINT = "https://serpapi.com/search.json"
SERPAPI_ATTEMPTS = 2


class ScholarError(ValueError):
    """An incomplete or unexpected response must never replace saved data."""


def parse_count(text):
    text = text.strip()
    if not re.fullmatch(r"(?:[0-9]+|[0-9]{1,3}(?:,[0-9]{3})+)", text):
        raise ScholarError("A citation metric is missing or is not an integer.")
    return int(text.replace(",", ""))


def validate_profile_id(profile_id):
    if not isinstance(profile_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", profile_id):
        raise ScholarError("The saved Google Scholar profile ID is invalid.")


def citation_url(href):
    if href is None or href == "":
        return None
    if not isinstance(href, str):
        raise ScholarError("An article citation link is invalid.")
    try:
        target = urlparse(href.strip())
    except ValueError:
        raise ScholarError("An article citation link is invalid.") from None
    clusters = parse_qs(target.query, keep_blank_values=True).get("cites", [])
    if (target.scheme != "https" or target.netloc != "scholar.google.com"
            or target.path != "/scholar" or len(clusters) != 1
            or not re.fullmatch(r"[0-9]+(?:,[0-9]+)*", clusters[0])):
        raise ScholarError("An article citation link is invalid.")
    return "https://scholar.google.com/scholar?" + urlencode(
        {"hl": "en", "cites": clusters[0]})


def resolve_provider(provider):
    if provider == "auto":
        provider = "serpapi" if os.environ.get("SERPAPI_API_KEY", "").strip() else "direct"
    if provider not in {"direct", "serpapi"}:
        raise ScholarError("Choose the direct, serpapi, or auto provider.")
    if provider == "serpapi" and not os.environ.get("SERPAPI_API_KEY", "").strip():
        raise ScholarError("Set the SERPAPI_API_KEY repository secret before using the serpapi provider.")
    return provider


class _RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, request, response, code, message, headers, new_url):
        # The API key must only be sent to the fixed SerpApi endpoint.
        return None


def _open_serpapi(request):
    return build_opener(_RejectRedirects()).open(request, timeout=60)


def _quota_exhausted(payload):
    error = payload.get("error", "") if isinstance(payload, dict) else ""
    return isinstance(error, str) and any(phrase in error.lower() for phrase in (
        "run out of searches", "no searches remaining", "searches exhausted",
        "monthly quota", "monthly limit"))


def fetch_serpapi_page(profile_id, start):
    resolve_provider("serpapi")
    query = urlencode({"engine": "google_scholar_author", "author_id": profile_id,
                       "hl": "en", "num": PAGE_SIZE, "start": start,
                       "api_key": os.environ["SERPAPI_API_KEY"].strip()})
    request = Request(SERPAPI_ENDPOINT + "?" + query,
                      headers={"Accept": "application/json", "User-Agent": "ScholarStats/1.0"})
    for attempt in range(SERPAPI_ATTEMPTS):
        try:
            with _open_serpapi(request) as response:
                payload = json.loads(response.read().decode("utf-8"))
            return payload
        except HTTPError as error:
            status = error.code
            exhausted = False
            if status == 429:
                try:
                    exhausted = _quota_exhausted(json.loads(error.read(8192).decode("utf-8")))
                except (ValueError, UnicodeError, OSError):
                    pass
            error.close()
            if exhausted:
                raise ScholarError("SerpApi search quota is exhausted. Check your SerpApi search balance.") from None
            if status in {401, 403}:
                raise ScholarError(
                    f"SerpApi authentication or access failed (HTTP {status}). Check SERPAPI_API_KEY.") from None
            transient = status == 429 or 500 <= status <= 599
            if not transient or attempt + 1 == SERPAPI_ATTEMPTS:
                raise ScholarError(
                    f"SerpApi returned HTTP {status}. Check API status, rate limits, and search balance.") from None
        except (OSError, HTTPException):
            if attempt + 1 == SERPAPI_ATTEMPTS:
                raise ScholarError("Could not reach SerpApi after two attempts. Try again later.") from None
        except (ValueError, UnicodeError):
            raise ScholarError("SerpApi returned an invalid JSON response.") from None
        # Only network failures, 429 throughput errors, and 5xx are retried.
        time.sleep(2)


def _json_count(value):
    if type(value) is not int or value < 0:
        raise ScholarError("A SerpApi citation metric is missing or is not a nonnegative integer.")
    return value


def _page_offset(parameters, default=None):
    offsets = []
    for key in ("start", "cstart"):
        if key not in parameters:
            continue
        values = parameters[key]
        values = values if isinstance(values, list) else [values]
        if len(values) != 1 or isinstance(values[0], bool):
            raise ScholarError("SerpApi pagination has an invalid offset.")
        value = values[0]
        if not isinstance(value, (str, int)) or not re.fullmatch(r"[0-9]+", str(value)):
            raise ScholarError("SerpApi pagination has an invalid offset.")
        offsets.append(int(value))
    if not offsets:
        return default
    if len(set(offsets)) != 1:
        raise ScholarError("SerpApi pagination contains conflicting offsets.")
    return offsets[0]


def parse_serpapi_page(payload, profile_id, start):
    if not isinstance(payload, dict):
        raise ScholarError("SerpApi returned an unexpected response structure.")
    if _quota_exhausted(payload):
        raise ScholarError("SerpApi search quota is exhausted. Check your SerpApi search balance.")
    metadata = payload.get("search_metadata")
    if "error" in payload or not isinstance(metadata, dict) or metadata.get("status") != "Success":
        # Never include provider error text: it may echo a URL containing the key.
        raise ScholarError("SerpApi did not complete the author search successfully. Check API status and account limits.")
    parameters = payload.get("search_parameters")
    if (not isinstance(parameters, dict) or parameters.get("engine") != "google_scholar_author"
            or parameters.get("author_id") != profile_id or parameters.get("hl") != "en"
            or _page_offset(parameters, default=0) != start):
        raise ScholarError("SerpApi returned a different profile, language, or result page.")
    author = payload.get("author")
    if not isinstance(author, dict) or not isinstance(author.get("name"), str) or not author["name"].strip():
        raise ScholarError("SerpApi did not return a named public author profile.")

    metrics = {}
    if start == 0:
        cited_by = payload.get("cited_by")
        table = cited_by.get("table") if isinstance(cited_by, dict) else None
        if not isinstance(table, list):
            raise ScholarError("SerpApi citation statistics are missing.")
        for row in table:
            if not isinstance(row, dict):
                raise ScholarError("SerpApi citation statistics are malformed.")
            for key in ("citations", "h_index"):
                if key in row:
                    if key in metrics or not isinstance(row[key], dict):
                        raise ScholarError("SerpApi citation statistics are ambiguous.")
                    metrics[key] = _json_count(row[key].get("all"))
        if set(metrics) != {"citations", "h_index"}:
            raise ScholarError("SerpApi all-time citations or h-index is missing.")

    entries = payload.get("articles")
    if not isinstance(entries, list) or not entries or len(entries) > PAGE_SIZE:
        raise ScholarError("SerpApi article results are missing or incomplete.")
    articles = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ScholarError("A SerpApi article is malformed.")
        article_id, title = entry.get("citation_id"), entry.get("title")
        if not isinstance(article_id, str) or not re.fullmatch(
                re.escape(profile_id) + r":[A-Za-z0-9_-]+", article_id):
            raise ScholarError("A SerpApi article does not match the requested profile.")
        cited_by = entry.get("cited_by")
        if not isinstance(title, str) or not title.strip() or not isinstance(cited_by, dict):
            raise ScholarError("A SerpApi article title or citation field is missing.")
        articles.append({"id": article_id, "title": " ".join(title.split()),
                         "citations": _json_count(cited_by.get("value")),
                         "cited_by_url": citation_url(cited_by.get("link"))})

    pagination = payload.get("serpapi_pagination", {})
    if not isinstance(pagination, dict):
        raise ScholarError("SerpApi pagination is malformed.")
    next_url = pagination.get("next")
    if next_url is None:
        return metrics, articles, None
    if not isinstance(next_url, str):
        raise ScholarError("SerpApi pagination link is invalid.")
    try:
        target = urlparse(next_url)
    except ValueError:
        raise ScholarError("SerpApi pagination link is invalid.") from None
    query = parse_qs(target.query, keep_blank_values=True)
    if (target.scheme != "https" or target.netloc != "serpapi.com" or target.path != "/search.json"
            or query.get("engine") != ["google_scholar_author"]
            or query.get("author_id") != [profile_id]
            or query.get("hl", ["en"]) != ["en"]):
        raise ScholarError("SerpApi pagination points to an unexpected endpoint or profile.")
    next_start = _page_offset(query)
    if next_start != start + len(articles):
        raise ScholarError("SerpApi pagination repeated or skipped part of the article list.")
    return metrics, articles, next_start


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

    articles = []
    for row in soup.select("#gsc_a_b .gsc_a_tr"):
        link = row.select_one("a.gsc_a_at[href]")
        if link is None:
            raise ScholarError("An article has no identifiable title link.")
        ids = parse_qs(urlparse(link["href"]).query).get("citation_for_view", [])
        if len(ids) != 1 or not re.fullmatch(re.escape(profile_id) + r":[A-Za-z0-9_-]+", ids[0]):
            raise ScholarError("An article does not match the requested profile.")
        title = link.get_text(" ", strip=True)
        citation = row.select_one(".gsc_a_c a.gsc_a_ac")
        if not title or citation is None or not citation.has_attr("href"):
            raise ScholarError("An article title or citation field is missing.")
        count_text = citation.get_text(strip=True)
        href = citation["href"].strip()
        # Scholar represents a genuine zero with an empty citation anchor.
        # A missing field or an empty count with a link is not a zero.
        count = 0 if not count_text and not href else parse_count(count_text)
        articles.append({"id": ids[0], "title": title, "citations": count,
                         "cited_by_url": citation_url(href)})
    more = soup.select_one("#gsc_bpf_more")
    if more is None or not articles:
        raise ScholarError("The article list or its pagination is missing.")
    return metrics, articles, not more.has_attr("disabled")


def collect_stats(profile_id, fetch=fetch_page):
    validate_profile_id(profile_id)
    articles = {}
    metrics = {}
    for page_number in range(MAX_PAGES):
        page_metrics, page_articles, has_more = parse_page(
            fetch(profile_id, len(articles)), profile_id, first_page=page_number == 0)
        if page_number == 0:
            metrics = page_metrics
        merge_articles(articles, page_articles)
        if not has_more:
            return make_snapshot(profile_id, metrics, articles)
    raise ScholarError("The article list exceeded the page limit; snapshot unchanged.")


def merge_articles(articles, page_articles):
    article_ids = [article["id"] for article in page_articles]
    if len(set(article_ids)) != len(article_ids) or articles.keys() & set(article_ids):
        raise ScholarError("Repeated articles found; pagination may have failed.")
    for article in page_articles:
        articles[article["id"]] = {key: value for key, value in article.items() if key != "id"}


def make_snapshot(profile_id, metrics, articles):
    if metrics["h_index"] > len(articles) or metrics["citations"] < metrics["h_index"] ** 2:
        raise ScholarError("The profile returned inconsistent statistics.")
    return {"profile_id": profile_id, "papers": len(articles), **metrics,
            "updated": datetime.now(ZoneInfo("America/New_York")).date().isoformat(),
            "articles": dict(sorted(articles.items()))}


def collect_serpapi_stats(profile_id, fetch=fetch_serpapi_page):
    resolve_provider("serpapi")
    validate_profile_id(profile_id)
    articles, metrics = {}, {}
    start = 0
    for _ in range(MAX_PAGES):
        page_metrics, page_articles, next_start = parse_serpapi_page(
            fetch(profile_id, start), profile_id, start)
        if start == 0:
            metrics = page_metrics
        merge_articles(articles, page_articles)
        if next_start is None:
            return make_snapshot(profile_id, metrics, articles)
        start = next_start
    raise ScholarError("The article list exceeded the page limit; snapshot unchanged.")


def update_snapshot(path=DEFAULT_DATA, dry_run=False, fetch=fetch_page, *,
                    provider="direct", serpapi_fetch=fetch_serpapi_page):
    provider = resolve_provider(provider)
    previous = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(previous, dict):
        raise ScholarError("The saved statistics file is invalid.")
    snapshot = (collect_serpapi_stats(previous.get("profile_id"), serpapi_fetch)
                if provider == "serpapi" else collect_stats(previous.get("profile_id"), fetch))
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


def report_result(message):
    # Defense in depth: no API response, URL, or key belongs in the logs.
    secret = os.environ.get("SERPAPI_API_KEY", "").strip()
    if secret:
        for value in (secret, urlencode({"api_key": secret}).split("=", 1)[1]):
            message = message.replace(value, "[redacted]")
    print(message)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        try:
            with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as summary:
                summary.write(message + "\n")
        except OSError:
            print("Could not write the GitHub step summary; see the job log.", file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA)
    parser.add_argument("--dry-run", action="store_true", help="Fetch and validate without saving")
    parser.add_argument("--provider", choices=("auto", "direct", "serpapi"), default="auto",
                        help="auto uses SerpApi when SERPAPI_API_KEY is set; otherwise direct")
    args = parser.parse_args()
    provider = args.provider
    error_message = None
    try:
        provider = resolve_provider(provider)
        snapshot = update_snapshot(args.data, args.dry_run, provider=provider)
    except ScholarError as error:
        error_message = str(error)
    except (OSError, yaml.YAMLError):
        error_message = "Could not read or write the local statistics snapshot."
    checked_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    if error_message:
        report_result(f"Scholar update failed ({provider}, {checked_at}): "
                      f"{error_message} Saved statistics were not replaced.")
        return 1
    mode = " (dry run; file unchanged)" if args.dry_run else ""
    report_result(f"Google Scholar check succeeded via {provider} at {checked_at}: "
                  f"{snapshot['papers']} papers, {snapshot['citations']} citations, "
                  f"h-index {snapshot['h_index']}; snapshot date {snapshot['updated']}{mode}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
