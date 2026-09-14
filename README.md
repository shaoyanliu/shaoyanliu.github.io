# shaoyanliu.github.io

This website is based on a fork of [Yaoyao Liu's homepage](https://yaoyaoliu.web.illinois.edu/).  
Many thanks to Yaoyao for providing the original template!

For more details about the original theme, please refer to this repository:  
<https://github.com/yaoyao-liu/minimal-light>

## Publication browsing

The Publications page has single-topic filters, expandable abstracts, and a
BibTeX dialog with copy and download buttons. Filtering preserves each paper's
original number and hides year headings that have no matching papers.

Maintain `abstract` (plain text from the paper) and `topics` (a list of IDs) in
`_data/publications.yml`. Topic IDs and display labels are defined in
`_data/publication_topics.yml`. Current IDs are `thermal-runaway`,
`gas-generation`, `modeling`, `combustion`, and `review`; a paper can have several.

BibTeX content is loaded from the existing `bib/*.txt` files on this site, so
there is only one copy of each citation to maintain. Downloads use a `.bib`
filename. Without JavaScript, abstracts remain readable and BibTeX links open
the original files. If clipboard access is unavailable, the dialog selects the
citation for manual copying and keeps the download link available.

## Google Scholar statistics

The sidebar reads `_data/scholar_stats.yml`. The **Update Google Scholar statistics**
workflow checks the public profile every day at **04:17 America/New_York**
(including daylight saving time). It can also be run from the repository's
**Actions → Update Google Scholar statistics → Run workflow** page.

The updater uses the free public Google Scholar profile; no API key or paid
service is required. It reads the **All** column for citations and h-index and
counts every listed article, following pagination when needed. These are Google
Scholar's counts, which can differ from the website's curated publication list.
Google Scholar does not guarantee that its own counts change every day.

Each paper on Publications also displays **Cited by N**. Per-paper counts are
collected from the same profile response and saved in the snapshot's `articles`
mapping, so the current seven papers still need just one request per daily run.
Each entry in `_data/publications.yml` has a manually verified `scholar_id`
matching Google Scholar's full `citation_for_view` ID. When adding a paper, copy
that ID from its Scholar detail link; the site never guesses a match by title.
Papers without a matching entry omit the citation label, while a verified zero
displays **Cited by 0**. The label opens the citing-paper list, or the Scholar
article detail page when there is no list yet.

A successful check saves all three metrics, per-paper counts, and the check date together. The
compact card displays the month/year; hover over the date to see the full day.
HTTP errors, verification pages, missing metrics, and incomplete pagination fail
the workflow without replacing the previous snapshot or date. Google may block
automated requests from GitHub runners even when a local request succeeds; check
failed runs in Actions if the displayed date stops advancing.

After saving the snapshot to `main`, the workflow explicitly requests a GitHub
Pages build. This is necessary because a commit made with `GITHUB_TOKEN` does
not trigger a Pages build by itself. It uses the built-in token with `contents:
write` and `pages: write`; no personal access token is needed. The workflow does
not run on `page_build`, so publishing the new snapshot will not trigger a
second fetch. It expects Pages to continue publishing from `main`.

To activate after pushing these files to `main`, open Actions, enable the
workflow if GitHub has disabled the inherited template workflow, and run it
once. Check that both the update and the subsequent Pages build succeed.
GitHub schedules may run late and can be disabled after 60 days without
repository activity. The daily successful snapshot commits normally keep this
repository active.

Local verification (Python 3.10 or newer):

```sh
python3 -m venv /tmp/scholar-tools
/tmp/scholar-tools/bin/pip install -r scripts/requirements-scholar.txt
/tmp/scholar-tools/bin/python -m unittest discover -s tests -p 'test_scholar_stats.py'
/tmp/scholar-tools/bin/python scripts/update_scholar_stats.py --dry-run
```

References: [GitHub scheduled workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule),
[GITHUB_TOKEN and Pages](https://docs.github.com/en/actions/concepts/security/github_token),
[requesting a Pages build](https://docs.github.com/en/rest/pages/pages#request-a-github-pages-build).
