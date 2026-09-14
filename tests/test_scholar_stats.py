"""Offline checks for complete Scholar snapshots and preservation on failure."""

from datetime import datetime
from html import escape
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError, URLError
from zoneinfo import ZoneInfo

import yaml

from scripts import update_scholar_stats as scholar


PROFILE = "TEST_AUTHOR"
TODAY = "2026-09-14"
NOW = datetime(2026, 9, 14, 4, 17, tzinfo=ZoneInfo("America/New_York"))


def profile_page(ids=("paper_a", "paper_b"), citations="172", h_index="2",
                 has_more=False, include_metrics=True):
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
    articles = "".join(
        '<tr class="gsc_a_tr"><td><a class="gsc_a_at" '
        f'href="/citations?citation_for_view={escape(PROFILE + ":" + paper)}">'
        f"Synthetic paper {index}</a></td></tr>"
        for index, paper in enumerate(ids)
    )
    disabled = "" if has_more else " disabled"
    return (f'<div id="gsc_prf_in">Synthetic Author</div>{statistics}'
            f'<table><tbody id="gsc_a_b">{articles}</tbody></table>'
            f'<button id="gsc_bpf_more"{disabled}>Show more</button>')


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


class ScholarSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "scholar_stats.yml"
        self.previous = {
            "profile_id": PROFILE, "papers": 7, "citations": 172,
            "h_index": 6, "updated": "2026-09-13",
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
        })
        self.assertEqual(yaml.safe_load(self.path.read_text()), result)
        self.mock_clock.now.assert_called_once_with(ZoneInfo("America/New_York"))

    def test_zero_citations_are_saved(self):
        result = scholar.update_snapshot(
            self.path, fetch=lambda *_: profile_page(citations="0", h_index="0"))
        self.assertEqual(result["citations"], 0)
        self.assertEqual(result["h_index"], 0)
        self.assertEqual(result["updated"], TODAY)

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


if __name__ == "__main__":
    unittest.main()
