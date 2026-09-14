"""Offline checks for complete Scholar snapshots and preservation on failure."""

from datetime import datetime
from contextlib import redirect_stderr, redirect_stdout
from html import escape
from http.client import IncompleteRead
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlencode, urlparse
from zoneinfo import ZoneInfo

import yaml

from scripts import update_scholar_stats as scholar


PROFILE = "TEST_AUTHOR"
TODAY = "2026-09-14"
NOW = datetime(2026, 9, 14, 4, 17, tzinfo=ZoneInfo("America/New_York"))


def profile_page(ids=("paper_a", "paper_b"), citations="172", h_index="2",
                 has_more=False, include_metrics=True, article_counts=None,
                 article_hrefs=None):
    """Small synthetic markup containing only the public fields we consume."""
    statistics = ""
    if include_metrics:
        statistics = f"""
        <table id="gsc_rsb_st">
          <thead><tr><th></th><th>All</th><th>Since 2021</th></tr></thead>
          <tbody>
            <tr><td>Citations</td><td>{citations}</td><td>1</td></tr>
            <tr><td>h-index</td><td>{h_index}</td><td>1</td></tr>
            <tr><td>i10-index</td><td>0</td><td>0</td></tr>
          </tbody>
        </table>"""
    articles = []
    for index, paper in enumerate(ids):
        count = article_counts[index] if article_counts is not None else "2"
        if article_hrefs is None:
            href = (f"https://scholar.google.com/scholar?cites={1000 + index}"
                    if count.strip() and count != "0" else "")
        else:
            href = article_hrefs[index]
        href_attr = f' href="{escape(href)}"' if href is not None else ""
        articles.append(
            '<tr class="gsc_a_tr"><td><a class="gsc_a_at" '
            f'href="/citations?citation_for_view={escape(PROFILE + ":" + paper)}">'
            f"Synthetic {escape(paper)}</a></td>"
            f'<td class="gsc_a_c"><a class="gsc_a_ac"{href_attr}>'
            f"{escape(count)}</a></td></tr>")
    disabled = "" if has_more else " disabled"
    return (f'<div id="gsc_prf_in">Synthetic Author</div>{statistics}'
            f'<table><tbody id="gsc_a_b">{"".join(articles)}</tbody></table>'
            f'<button id="gsc_bpf_more"{disabled}>Show more</button>')


def expected_articles():
    return {
        f"{PROFILE}:paper_a": {"title": "Synthetic paper_a", "citations": 2,
                                "cited_by_url": "https://scholar.google.com/scholar?hl=en&cites=1000"},
        f"{PROFILE}:paper_b": {"title": "Synthetic paper_b", "citations": 2,
                                "cited_by_url": "https://scholar.google.com/scholar?hl=en&cites=1001"},
    }


def serpapi_page(ids=("paper_a", "paper_b"), start=0, next_start=None, offset_name="start"):
    """Synthetic English response based on the documented Author API fields."""
    payload = {
        "search_metadata": {"status": "Success"},
        "search_parameters": {"engine": "google_scholar_author", "author_id": PROFILE,
                              "hl": "en", "start": start},
        "author": {"name": "Synthetic Author"},
        "cited_by": {"table": [{"citations": {"all": 172, "since_2021": 1}},
                               {"h_index": {"all": 2, "since_2021": 1}}]},
        "articles": [{"citation_id": f"{PROFILE}:{paper}", "title": f"Synthetic {paper}",
                      "cited_by": {"value": 2, "link":
                                   f"https://scholar.google.com/scholar?cites={1000 + start + index}"}}
                     for index, paper in enumerate(ids)],
    }
    if next_start is not None:
        payload["serpapi_pagination"] = {"next": "https://serpapi.com/search.json?" + urlencode({
            "engine": "google_scholar_author", "author_id": PROFILE,
            "hl": "en", offset_name: next_start})}
    return payload


def json_response(payload):
    return io.BytesIO(json.dumps(payload).encode("utf-8"))


class ScholarParsingTests(unittest.TestCase):
    def test_all_time_column_and_thousands_separator(self):
        stats = scholar.collect_stats(
            PROFILE, fetch=lambda *_: profile_page(citations="1,234"))
        self.assertEqual(stats["citations"], 1234)
        self.assertEqual(stats["h_index"], 2)
        self.assertEqual(stats["papers"], 2)

    def test_noninteger_and_malformed_counts_are_rejected(self):
        for count in ("", "N/A", "1,23", "-1", "2.5", "1K", "1 234"):
            with self.subTest(count=count), self.assertRaises(scholar.ScholarError):
                scholar.collect_stats(
                    PROFILE, fetch=lambda *_: profile_page(citations=count))

    def test_recent_column_cannot_be_used_as_all_time(self):
        html = profile_page().replace("<th>All</th>", "<th>Since 2021</th>")
        with self.assertRaises(scholar.ScholarError):
            scholar.collect_stats(PROFILE, fetch=lambda *_: html)

    def test_counts_complete_paginated_article_list(self):
        first = profile_page(
            ids=tuple(f"paper_{index}" for index in range(100)), has_more=True)
        second = profile_page(ids=("paper_100",), include_metrics=False)
        fetch = Mock(side_effect=[first, second])
        result = scholar.collect_stats(PROFILE, fetch=fetch)
        self.assertEqual(result["papers"], 101)
        self.assertEqual(len(result["articles"]), 101)
        self.assertIn(f"{PROFILE}:paper_100", result["articles"])
        self.assertEqual(list(result["articles"]), sorted(result["articles"]))
        self.assertEqual([call.args for call in fetch.call_args_list],
                         [(PROFILE, 0), (PROFILE, 100)])

    def test_duplicates_within_a_page_are_rejected(self):
        with self.assertRaises(scholar.ScholarError):
            scholar.collect_stats(
                PROFILE, fetch=lambda *_: profile_page(ids=("same", "same")))

    def test_repeated_articles_across_pages_are_rejected(self):
        fetch = Mock(side_effect=[profile_page(has_more=True), profile_page()])
        with self.assertRaises(scholar.ScholarError):
            scholar.collect_stats(PROFILE, fetch=fetch)

    def test_cross_account_article_is_rejected(self):
        html = profile_page().replace(
            "citation_for_view=TEST_AUTHOR:paper_a",
            "citation_for_view=OTHER_AUTHOR:paper_a")
        with self.assertRaises(scholar.ScholarError):
            scholar.collect_stats(PROFILE, fetch=lambda *_: html)

    def test_empty_article_identifier_is_rejected(self):
        with self.assertRaises(scholar.ScholarError):
            scholar.collect_stats(
                PROFILE, fetch=lambda *_: profile_page(ids=("", "paper_b")))

    def test_missing_pagination_cannot_be_treated_as_final_page(self):
        html = profile_page().replace('id="gsc_bpf_more"', 'id="unknown"')
        with self.assertRaises(scholar.ScholarError):
            scholar.collect_stats(PROFILE, fetch=lambda *_: html)

    def test_inconsistent_metrics_are_rejected(self):
        for citations, h_index in (("3", "2"), ("172", "3")):
            with self.subTest(citations=citations, h_index=h_index):
                with self.assertRaises(scholar.ScholarError):
                    scholar.collect_stats(
                        PROFILE,
                        fetch=lambda *_: profile_page(citations=citations,
                                                      h_index=h_index))

    def test_unending_pagination_is_bounded(self):
        def fetch(_profile, start):
            return profile_page(ids=(f"paper_{start}",), has_more=True,
                                citations="1", h_index="1")

        with patch.object(scholar, "MAX_PAGES", 2):
            with self.assertRaises(scholar.ScholarError):
                scholar.collect_stats(PROFILE, fetch=fetch)

    def test_article_counts_include_thousands_and_zero(self):
        result = scholar.collect_stats(PROFILE, fetch=lambda *_: profile_page(
            citations="1,999", article_counts=("1,234", "")))
        self.assertEqual(result["articles"][f"{PROFILE}:paper_a"]["citations"], 1234)
        zero = result["articles"][f"{PROFILE}:paper_b"]
        self.assertEqual(zero["citations"], 0)
        self.assertIsNone(zero["cited_by_url"])
        self.assertEqual(result["citations"], 1999)

    def test_explicit_zero_and_number_without_link_are_valid(self):
        result = scholar.collect_stats(PROFILE, fetch=lambda *_: profile_page(
            article_counts=("0", "2"), article_hrefs=("", "")))
        self.assertEqual(result["articles"][f"{PROFILE}:paper_a"]["citations"], 0)
        self.assertEqual(result["articles"][f"{PROFILE}:paper_b"]["citations"], 2)
        self.assertTrue(all(article["cited_by_url"] is None
                            for article in result["articles"].values()))

    def test_article_title_is_plain_text(self):
        html = profile_page().replace("Synthetic paper_a", "Battery <em>Safety</em> &amp; Gas")
        result = scholar.collect_stats(PROFILE, fetch=lambda *_: html)
        self.assertEqual(result["articles"][f"{PROFILE}:paper_a"]["title"],
                         "Battery Safety & Gas")

    def test_cluster_links_are_validated_and_normalized(self):
        href = "https://scholar.google.com/scholar?hl=fr&cites=123,456&oi=bibs"
        result = scholar.collect_stats(PROFILE, fetch=lambda *_: profile_page(
            article_hrefs=(href, "")))
        self.assertEqual(result["articles"][f"{PROFILE}:paper_a"]["cited_by_url"],
                         "https://scholar.google.com/scholar?hl=en&cites=123%2C456")

    def test_invalid_citation_links_are_rejected(self):
        invalid_links = (
            "https://example.com/scholar?cites=123",
            "https://scholar.google.com.evil.test/scholar?cites=123",
            "https://scholar.google.com@evil.test/scholar?cites=123",
            "http://scholar.google.com/scholar?cites=123",
            "javascript:alert(1)",
            "/scholar?cites=123",
            "https://scholar.google.com/citations?cites=123",
            "https://scholar.google.com/scholar?cites=",
            "https://scholar.google.com/scholar?cites=123&cites=456",
            "https://scholar.google.com/scholar?cites=123,bad",
        )
        for href in invalid_links:
            with self.subTest(href=href), self.assertRaises(scholar.ScholarError):
                scholar.collect_stats(PROFILE, fetch=lambda *_: profile_page(
                    article_hrefs=(href, "")))


class ScholarSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "scholar_stats.yml"
        self.previous = {
            "profile_id": PROFILE, "papers": 7, "citations": 172,
            "h_index": 6, "updated": "2026-09-13",
            "articles": expected_articles(),
        }
        self.write_previous()
        self.clock = patch.object(scholar, "datetime")
        self.mock_clock = self.clock.start()
        self.addCleanup(self.clock.stop)
        self.mock_clock.now.return_value = NOW

    def write_previous(self):
        self.path.write_text("# Previous successful snapshot\n" +
                             yaml.safe_dump(self.previous), encoding="utf-8")

    def assert_unchanged_after_failure(self, fetch):
        before = self.path.read_bytes()
        with self.assertRaises(scholar.ScholarError):
            scholar.update_snapshot(self.path, fetch=fetch)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_verification_page_preserves_file_and_date(self):
        self.assert_unchanged_after_failure(
            lambda *_: "<html><h1>Verify you are human</h1></html>")

    def test_missing_metric_preserves_file_and_date(self):
        html = profile_page().replace("<td>h-index</td>", "<td>unknown</td>")
        self.assert_unchanged_after_failure(lambda *_: html)

    def test_missing_statistics_table_preserves_file_and_date(self):
        self.assert_unchanged_after_failure(
            lambda *_: profile_page(include_metrics=False))

    def test_later_page_failure_preserves_entire_previous_snapshot(self):
        fetch = Mock(side_effect=[profile_page(has_more=True),
                                 scholar.ScholarError("Second page unavailable")])
        self.assert_unchanged_after_failure(fetch)

    def test_http_and_network_failures_preserve_file_and_date(self):
        errors = [HTTPError("https://scholar.google.com", 429, "Limited", {}, None),
                  HTTPError("https://scholar.google.com", 403, "Forbidden", {}, None),
                  URLError("Offline"), TimeoutError("Timeout")]
        for error in errors:
            with self.subTest(error=error):
                with patch.object(scholar, "urlopen", side_effect=error):
                    self.assert_unchanged_after_failure(scholar.fetch_page)

    def test_valid_decrease_is_saved_with_success_date(self):
        result = scholar.update_snapshot(
            self.path, fetch=lambda *_: profile_page(citations="100", h_index="2"))
        self.assertEqual(result, {
            "profile_id": PROFILE, "papers": 2, "citations": 100,
            "h_index": 2, "updated": TODAY,
            "articles": expected_articles(),
        })
        self.assertEqual(yaml.safe_load(self.path.read_text()), result)
        self.mock_clock.now.assert_called_once_with(ZoneInfo("America/New_York"))

    def test_zero_citations_are_saved(self):
        result = scholar.update_snapshot(
            self.path, fetch=lambda *_: profile_page(
                citations="0", h_index="0", article_counts=("", "0")))
        self.assertEqual(result["citations"], 0)
        self.assertEqual(result["h_index"], 0)
        self.assertEqual(result["updated"], TODAY)
        self.assertTrue(all(article["citations"] == 0
                            for article in result["articles"].values()))

    def test_same_day_identical_snapshot_does_not_rewrite_file(self):
        self.previous.update(papers=2, h_index=2, updated=TODAY)
        self.write_previous()
        before = self.path.read_bytes()
        with patch.object(scholar.tempfile, "NamedTemporaryFile") as temporary:
            result = scholar.update_snapshot(
                self.path, fetch=lambda *_: profile_page())
        temporary.assert_not_called()
        self.assertEqual(result, self.previous)
        self.assertEqual(self.path.read_bytes(), before)

    def test_successful_check_updates_date_when_metrics_stay_same(self):
        self.previous.update(papers=2, h_index=2)
        self.write_previous()
        result = scholar.update_snapshot(self.path, fetch=lambda *_: profile_page())
        self.assertEqual(result["updated"], TODAY)
        self.assertEqual(yaml.safe_load(self.path.read_text())["updated"], TODAY)

    def test_dry_run_never_replaces_saved_file(self):
        before = self.path.read_bytes()
        result = scholar.update_snapshot(
            self.path, dry_run=True, fetch=lambda *_: profile_page())
        self.assertEqual(result["updated"], TODAY)
        self.assertEqual(self.path.read_bytes(), before)

    def test_atomic_replace_failure_preserves_previous_file_and_cleans_temp(self):
        before = self.path.read_bytes()
        with patch.object(Path, "replace", side_effect=OSError("Cannot replace")):
            with self.assertRaises(OSError):
                scholar.update_snapshot(self.path, fetch=lambda *_: profile_page())
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(list(self.path.parent.iterdir()), [self.path])

    def test_incomplete_article_does_not_replace_any_saved_metrics(self):
        malformed_pages = (
            profile_page().replace('class="gsc_a_c"', 'class="missing"', 1),
            profile_page().replace('class="gsc_a_ac"', 'class="missing"', 1),
            profile_page(article_hrefs=(None, "")),
            profile_page().replace("Synthetic paper_a", " "),
            profile_page(article_counts=("N/A", "2")),
            profile_page(article_counts=("1,23", "2")),
            profile_page(article_counts=("-1", "2")),
            profile_page(article_counts=("", "2"), article_hrefs=(
                "https://scholar.google.com/scholar?cites=1000", "")),
        )
        for index, html in enumerate(malformed_pages):
            with self.subTest(case=index):
                self.assert_unchanged_after_failure(lambda *_: html)

    def test_later_page_article_error_preserves_aggregate_date_and_articles(self):
        first = profile_page(has_more=True)
        second = profile_page(ids=("paper_c",), include_metrics=False,
                              article_hrefs=(None,))
        self.assert_unchanged_after_failure(Mock(side_effect=[first, second]))

    def test_same_day_article_change_is_saved_when_totals_do_not_change(self):
        self.previous.update(papers=2, h_index=2, updated=TODAY)
        self.write_previous()
        result = scholar.update_snapshot(self.path, fetch=lambda *_: profile_page(
            article_counts=("3", "2")))
        self.assertEqual(result["updated"], TODAY)
        self.assertEqual(result["citations"], self.previous["citations"])
        self.assertEqual(result["articles"][f"{PROFILE}:paper_a"]["citations"], 3)
        self.assertEqual(yaml.safe_load(self.path.read_text()), result)

    def test_valid_article_citation_decrease_is_saved(self):
        result = scholar.update_snapshot(self.path, fetch=lambda *_: profile_page(
            article_counts=("1", "2")))
        self.assertEqual(result["articles"][f"{PROFILE}:paper_a"]["citations"], 1)
        self.assertEqual(yaml.safe_load(self.path.read_text()), result)

    def test_legacy_snapshot_gains_article_data_after_success(self):
        del self.previous["articles"]
        self.write_previous()
        result = scholar.update_snapshot(self.path, fetch=lambda *_: profile_page())
        self.assertEqual(result["articles"], expected_articles())
        self.assertEqual(yaml.safe_load(self.path.read_text()), result)


class SerpApiTests(unittest.TestCase):
    KEY = "synthetic-key+/not-a-real-key"

    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "scholar_stats.yml"
        self.summary = Path(self.directory.name) / "summary.md"
        self.previous = {"profile_id": PROFILE, "papers": 2, "citations": 172,
                         "h_index": 2, "updated": "2026-09-13", "articles": expected_articles()}
        self.path.write_text(yaml.safe_dump(self.previous), encoding="utf-8")
        environment = patch.dict(os.environ, {"SERPAPI_API_KEY": self.KEY,
                                             "GITHUB_STEP_SUMMARY": str(self.summary)})
        environment.start()
        self.addCleanup(environment.stop)
        clock = patch.object(scholar, "datetime")
        clock.start().now.side_effect = lambda tz: NOW.astimezone(tz)
        self.addCleanup(clock.stop)

    def assert_preserved(self, payload):
        before = self.path.read_bytes()
        with self.assertRaises(scholar.ScholarError) as failure:
            scholar.update_snapshot(self.path, provider="serpapi", serpapi_fetch=lambda *_: payload)
        self.assertNotIn(self.KEY, str(failure.exception))
        self.assertEqual(self.path.read_bytes(), before)

    def test_author_response_preserves_existing_snapshot_schema(self):
        result = scholar.update_snapshot(self.path, provider="serpapi",
                                         serpapi_fetch=lambda *_: serpapi_page())
        self.assertEqual(result, {**self.previous, "updated": TODAY})
        self.assertEqual(yaml.safe_load(self.path.read_text()), result)

    def test_all_time_values_and_explicit_zero_citations(self):
        payload = serpapi_page()
        payload["cited_by"]["table"][0]["citations"]["all"] = 1234
        payload["cited_by"]["table"][1]["h_index"]["all"] = 1
        payload["articles"][0]["cited_by"] = {"value": 1234}
        payload["articles"][1]["cited_by"] = {"value": 0}
        result = scholar.collect_serpapi_stats(PROFILE, fetch=lambda *_: payload)
        self.assertEqual(result["citations"], 1234)
        self.assertEqual(result["h_index"], 1)
        self.assertEqual(result["articles"][f"{PROFILE}:paper_b"]["citations"], 0)
        self.assertIsNone(result["articles"][f"{PROFILE}:paper_b"]["cited_by_url"])

    def test_missing_or_invalid_counts_never_become_zero(self):
        for value in (None, False, True, -1, 1.5, "0", "1,234", [], {}):
            for aggregate in (False, True):
                with self.subTest(value=value, aggregate=aggregate):
                    payload = serpapi_page()
                    if aggregate:
                        payload["cited_by"]["table"][0]["citations"]["all"] = value
                    else:
                        payload["articles"][0]["cited_by"]["value"] = value
                    self.assert_preserved(payload)
        payload = serpapi_page()
        del payload["articles"][0]["cited_by"]
        self.assert_preserved(payload)

    def test_observed_null_only_article_citations_mean_zero(self):
        payload = serpapi_page()
        payload["articles"][1]["cited_by"] = {"value": None}
        payload["cited_by"]["table"][1]["h_index"]["all"] = 1
        result = scholar.update_snapshot(self.path, provider="serpapi",
                                         serpapi_fetch=lambda *_: payload)
        article = result["articles"][f"{PROFILE}:paper_b"]
        self.assertEqual(article["citations"], 0)
        self.assertIsNone(article["cited_by_url"])
        self.assertEqual(result["updated"], TODAY)
        self.assertEqual(yaml.safe_load(self.path.read_text()), result)

    def test_null_with_extra_fields_and_missing_values_remain_invalid(self):
        for cited_by in (None, {}, {"link": ""},
                         {"value": None, "link": ""},
                         {"value": None, "link": "https://scholar.google.com/scholar?cites=1"},
                         {"value": None, "cites_id": "1"},
                         {"value": None, "serpapi_link": "https://serpapi.com/search.json"}):
            with self.subTest(cited_by=cited_by):
                payload = serpapi_page()
                payload["articles"][0]["cited_by"] = cited_by
                self.assert_preserved(payload)
        payload = serpapi_page()
        payload["cited_by"]["table"][1]["h_index"]["all"] = None
        self.assert_preserved(payload)

    def test_unexpected_response_identity_or_structure_is_rejected(self):
        mutations = (
            lambda p: p.update(error="Provider error with " + self.KEY),
            lambda p: p.update(search_metadata={"status": "Processing"}),
            lambda p: p.update(search_parameters={}),
            lambda p: p["search_parameters"].update(author_id="OTHER_AUTHOR"),
            lambda p: p["search_parameters"].update(engine="google_scholar"),
            lambda p: p["search_parameters"].update(hl="fr"),
            lambda p: p["search_parameters"].update(start=5),
            lambda p: p.update(author={"name": " "}),
            lambda p: p.update(cited_by={}),
            lambda p: p["cited_by"].update(table=[{"citations": {"all": 172}}]),
            lambda p: p["cited_by"]["table"].append({"h_index": {"all": 1}}),
            lambda p: p.update(articles=[]),
            lambda p: p["articles"][0].update(citation_id="OTHER_AUTHOR:paper_a"),
            lambda p: p["articles"][0].update(citation_id=PROFILE + ":"),
            lambda p: p["articles"][0].update(title=""),
            lambda p: p["articles"][0]["cited_by"].update(link="https://example.com/?cites=1"),
        )
        for index, mutate in enumerate(mutations):
            with self.subTest(case=index):
                payload = serpapi_page()
                mutate(payload)
                self.assert_preserved(payload)
        self.assert_preserved([])

    def test_start_and_cstart_pagination_collect_complete_article_mapping(self):
        for offset_name in ("start", "cstart"):
            with self.subTest(offset=offset_name):
                first = serpapi_page(tuple(f"paper_{i}" for i in range(100)),
                                     next_start=100, offset_name=offset_name)
                second = serpapi_page(("paper_100",), start=100)
                del second["cited_by"]
                fetch = Mock(side_effect=[first, second])
                result = scholar.collect_serpapi_stats(PROFILE, fetch=fetch)
                self.assertEqual(result["papers"], 101)
                self.assertEqual(len(result["articles"]), 101)
                self.assertEqual(list(result["articles"]), sorted(result["articles"]))
                self.assertEqual([call.args for call in fetch.call_args_list],
                                 [(PROFILE, 0), (PROFILE, 100)])

    def test_untrusted_next_url_cannot_change_destination_key_or_parameters(self):
        first = serpapi_page(next_start=2)
        first["serpapi_pagination"]["next"] += "&api_key=UNTRUSTED&extra=ignored"
        second = serpapi_page(("paper_c",), start=2)
        with patch.object(scholar, "_open_serpapi", side_effect=[
                json_response(first), json_response(second)]) as network:
            result = scholar.collect_serpapi_stats(PROFILE)
        self.assertEqual(result["papers"], 3)
        for index, call in enumerate(network.call_args_list):
            url = urlparse(call.args[0].full_url)
            self.assertEqual(url.scheme + "://" + url.netloc + url.path, scholar.SERPAPI_ENDPOINT)
            self.assertEqual(parse_qs(url.query), {
                "engine": ["google_scholar_author"], "author_id": [PROFILE],
                "hl": ["en"], "num": ["100"], "start": [str(index * 2)], "api_key": [self.KEY]})

    def test_repeated_skipped_or_cross_account_pagination_is_rejected(self):
        valid = serpapi_page(next_start=2)["serpapi_pagination"]["next"]
        links = (valid.replace("start=2", "start=0"),
                 valid.replace("start=2", "start=3"),
                 valid.replace("start=2", "start=2&cstart=3"),
                 valid.replace("start=2", "start=2&start=2"),
                 valid.replace(PROFILE, "OTHER_AUTHOR"),
                 valid.replace("google_scholar_author", "google_scholar"),
                 valid.replace("serpapi.com", "example.com"),
                 valid.replace("https:", "http:"),
                 valid.replace("search.json", "account.json"), "https://[")
        for link in links:
            with self.subTest(link=link):
                payload = serpapi_page()
                payload["serpapi_pagination"] = {"next": link}
                self.assert_preserved(payload)

    def test_duplicate_articles_and_later_page_failure_preserve_entire_snapshot(self):
        self.assert_preserved(serpapi_page(("same", "same")))
        for second in (serpapi_page(start=2), {"error": "quota " + self.KEY}):
            before = self.path.read_bytes()
            fetch = Mock(side_effect=[serpapi_page(next_start=2), second])
            with self.assertRaises(scholar.ScholarError):
                scholar.update_snapshot(self.path, provider="serpapi", serpapi_fetch=fetch)
            self.assertEqual(self.path.read_bytes(), before)

    def test_pagination_is_bounded(self):
        def fetch(_profile, start):
            return serpapi_page((f"paper_{start}", f"paper_{start + 1}"),
                                start=start, next_start=start + 2)
        with patch.object(scholar, "MAX_PAGES", 2), self.assertRaises(scholar.ScholarError):
            scholar.collect_serpapi_stats(PROFILE, fetch=fetch)

    def test_transient_http_and_network_errors_retry_once(self):
        for error in (HTTPError("secret-url", 429, "rate limited", {}, io.BytesIO(b"{}")),
                      HTTPError("secret-url", 503, "unavailable", {}, None),
                      URLError(self.KEY), TimeoutError(self.KEY), IncompleteRead(b"partial")):
            with self.subTest(kind=type(error).__name__):
                with patch.object(scholar, "_open_serpapi", side_effect=[
                        error, json_response(serpapi_page())]) as network:
                    with patch.object(scholar.time, "sleep") as sleep:
                        self.assertIsInstance(scholar.fetch_serpapi_page(PROFILE, 0), dict)
                self.assertEqual(network.call_count, 2)
                sleep.assert_called_once_with(2)

    def test_repeated_transient_failure_is_bounded_and_redacted(self):
        with patch.object(scholar, "_open_serpapi", side_effect=URLError(self.KEY)) as network:
            with patch.object(scholar.time, "sleep"), self.assertRaises(scholar.ScholarError) as error:
                scholar.fetch_serpapi_page(PROFILE, 0)
        self.assertEqual(network.call_count, 2)
        self.assertNotIn(self.KEY, str(error.exception))

    def test_auth_quota_and_redirect_errors_do_not_retry_or_echo_provider_text(self):
        cases = [(status, {"error": "Invalid key " + self.KEY}) for status in (400, 401, 403, 302)]
        cases.append((429, {"error": "Your account has run out of searches. " + self.KEY}))
        for status, body in cases:
            with self.subTest(status=status):
                error = HTTPError("https://serpapi.com/?api_key=" + self.KEY,
                                  status, self.KEY, {}, json_response(body))
                with patch.object(scholar, "_open_serpapi", side_effect=error) as network:
                    with patch.object(scholar.time, "sleep") as sleep:
                        with self.assertRaises(scholar.ScholarError) as failure:
                            scholar.fetch_serpapi_page(PROFILE, 0)
                self.assertEqual(network.call_count, 1)
                sleep.assert_not_called()
                self.assertNotIn(self.KEY, str(failure.exception))
                self.assertNotIn("https://", str(failure.exception))

    def test_redirects_are_disabled_and_request_timeout_is_60_seconds(self):
        with patch.object(scholar, "build_opener") as build:
            request = Mock()
            scholar._open_serpapi(request)
        handler = build.call_args.args[0]
        self.assertIsNone(handler.redirect_request(request, None, 302, "Found", {}, "https://example.com"))
        build.return_value.open.assert_called_once_with(request, timeout=60)

    def test_malformed_json_does_not_retry_or_leak_response_body(self):
        with patch.object(scholar, "_open_serpapi", return_value=io.BytesIO(
                ("not json " + self.KEY).encode())) as network:
            with self.assertRaises(scholar.ScholarError) as error:
                scholar.fetch_serpapi_page(PROFILE, 0)
        self.assertEqual(network.call_count, 1)
        self.assertNotIn(self.KEY, str(error.exception))

    def test_provider_selection_and_missing_key_fail_before_network(self):
        self.assertEqual(scholar.resolve_provider("auto"), "serpapi")
        self.assertEqual(scholar.resolve_provider("direct"), "direct")
        with patch.dict(os.environ, {"SERPAPI_API_KEY": ""}):
            self.assertEqual(scholar.resolve_provider("auto"), "direct")
            with patch.object(scholar, "_open_serpapi") as network:
                with self.assertRaisesRegex(scholar.ScholarError, "SERPAPI_API_KEY"):
                    scholar.fetch_serpapi_page(PROFILE, 0)
            network.assert_not_called()

    def test_explicit_direct_provider_ignores_configured_api_key(self):
        api_fetch = Mock(side_effect=AssertionError("SerpApi must not be called"))
        result = scholar.update_snapshot(self.path, provider="direct", fetch=lambda *_: profile_page(),
                                         serpapi_fetch=api_fetch)
        self.assertEqual(result["articles"], expected_articles())
        api_fetch.assert_not_called()

    def test_dry_run_and_identical_same_day_snapshot_do_not_write(self):
        before = self.path.read_bytes()
        scholar.update_snapshot(self.path, dry_run=True, provider="serpapi",
                                serpapi_fetch=lambda *_: serpapi_page())
        self.assertEqual(self.path.read_bytes(), before)
        self.previous["updated"] = TODAY
        self.path.write_text(yaml.safe_dump(self.previous), encoding="utf-8")
        with patch.object(scholar.tempfile, "NamedTemporaryFile") as temporary:
            scholar.update_snapshot(self.path, provider="serpapi", serpapi_fetch=lambda *_: serpapi_page())
        temporary.assert_not_called()

    def test_cli_defaults_to_auto_and_reports_provider_utc_and_metrics(self):
        snapshot = {**self.previous, "updated": TODAY}
        output = io.StringIO()
        with patch("sys.argv", ["update_scholar_stats.py", "--data", str(self.path)]):
            with patch.object(scholar, "update_snapshot", return_value=snapshot) as update:
                with redirect_stdout(output):
                    self.assertEqual(scholar.main(), 0)
        update.assert_called_once_with(self.path, False, provider="serpapi")
        message = output.getvalue()
        for expected in ("succeeded", "serpapi", "08:17:00 UTC", "2 papers", "172 citations", "h-index 2"):
            self.assertIn(expected, message)
        self.assertNotIn(self.KEY, message)
        self.assertEqual(self.summary.read_text(), message)

    def test_failure_summary_redacts_raw_and_encoded_key(self):
        encoded_key = urlencode({"api_key": self.KEY}).split("=", 1)[1]
        error = scholar.ScholarError("Synthetic failure " + self.KEY + " " + encoded_key)
        output = io.StringIO()
        with patch("sys.argv", ["update_scholar_stats.py", "--provider", "serpapi"]):
            with patch.object(scholar, "update_snapshot", side_effect=error):
                with redirect_stdout(output), redirect_stderr(output):
                    self.assertEqual(scholar.main(), 1)
        for text in (output.getvalue(), self.summary.read_text()):
            self.assertIn("failed (serpapi", text)
            self.assertIn("Saved statistics were not replaced", text)
            self.assertNotIn(self.KEY, text)
            self.assertNotIn(encoded_key, text)


if __name__ == "__main__":
    unittest.main()
