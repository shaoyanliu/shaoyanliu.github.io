# Shaoyan Liu · Academic Website

Personal academic website of **Shaoyan Liu (劉 少言)**, a Ph.D. student in Mechanical Engineering at **The Pennsylvania State University**, working with Prof. Jun Xu in the Energy Mechanics and Sustainability Laboratory. My research focuses on **battery safety**, including lithium-ion battery thermal runaway, gas generation, and combustion.

[Website](https://shaoyanliu.github.io/) · [Publications](https://shaoyanliu.github.io/publications/) · [Google Scholar](https://scholar.google.com/citations?user=Yw_kFE4AAAAJ&hl=en) · [CV](https://shaoyanliu.github.io/cv/)

Built with Jekyll and hosted on GitHub Pages, with a compact layout for sharing research, publications, teaching, and academic service.

## Features

- **Penn State blue, light and dark themes:** a persistent theme switch and responsive navigation.
- **Browsable publications:** year dividers, paper numbers, keyword search, topic filters, and lowercase colored topic badges.
- **Research at a glance:** expandable abstracts, DOI and PDF links, BibTeX preview with copy/download, and per-paper Google Scholar citations.
- **Scholar statistics:** a compact sidebar with paper count, total citations, h-index, and the last successful check date.
- **Dedicated CV page:** a continuously scrolling PDF preview with a Sections menu, zoom controls, open/download links, and a CV entry in the top navigation.
- **News and activities:** six recent news items with an expandable archive, plus dedicated Teaching and Services pages.
- **Visitor statistics:** GoatCounter tracks the homepage and subpages, with a total visitor display on the homepage.

## Content maintenance

| Content | Where to edit |
| --- | --- |
| Name, affiliation, profile links, and site metadata | [`_config.yml`](_config.yml) |
| Biography and personal introduction | [`index.md`](index.md) |
| Publications, abstracts, resource links, and Scholar article IDs | [`_data/publications.yml`](_data/publications.yml) |
| Topic IDs, labels, and full names | [`_data/publication_topics.yml`](_data/publication_topics.yml) |
| News, newest first | [`_data/news.yml`](_data/news.yml) |
| Teaching and academic service | [`_includes/teaching.md`](_includes/teaching.md), [`_includes/services.md`](_includes/services.md) |
| CV page and PDF | [`cv.md`](cv.md), [`cv/cv_shaoyan.pdf`](cv/cv_shaoyan.pdf); PDF path is configured as `cv_pdf` in `_config.yml` |
| CV section navigation | [`_data/cv_sections.yml`](_data/cv_sections.yml); headings are located in the PDF automatically, so page numbers need no manual updates |
| BibTeX files | [`bib/`](bib/) |
| Navigation | [`_data/navigation.yml`](_data/navigation.yml) |
| Theme and publication styles | [`assets/css/theme.css`](assets/css/theme.css), [`assets/css/pub.css`](assets/css/pub.css) |
| Saved Scholar statistics | [`_data/scholar_stats.yml`](_data/scholar_stats.yml), maintained by the updater |

For a new publication, add its metadata, a plain-text `abstract`, and a list of `topics` using IDs from the topic file. A paper can have several topics. BibTeX is read from its existing `bib/*.txt` file and downloaded as `.bib`, so only one citation file needs maintenance.

Set `scholar_id` to the full `citation_for_view` ID from the paper's Google Scholar detail link. Citation counts are matched by this verified ID, not by title. A missing match hides the citation label; a verified zero displays **Cited by 0**. Search and topic filters preserve each paper's original number.

## Daily Google Scholar updates

The [Update Google Scholar statistics](.github/workflows/google_scholar_crawler.yaml) workflow is scheduled for **05:16 America/New_York every day**, following daylight saving time. GitHub may start scheduled jobs later than the specified time.

The cloud workflow uses **SerpApi's Google Scholar Author API**, a third-party service, to retrieve profile statistics and per-paper citations together. It requires a SerpApi account and API key; any free allowance is subject to the provider's current plan and quota. This is not an official Google API. Additional article pages may require additional requests.

### Set up cloud synchronization

1. Obtain a key from [SerpApi](https://serpapi.com/google-scholar-author-api).
2. In this repository, open **Settings → Secrets and variables → Actions → New repository secret** and save it as **`SERPAPI_API_KEY`**. Keep the key out of source files.
3. Ensure GitHub Pages publishes from `main`. Open **Actions**, enable the workflow if needed, and select **Update Google Scholar statistics → Run workflow**.
4. Confirm that both the update and the following Pages build succeed. Adding the key or enabling the schedule alone does not verify a successful cloud update.

For a fork, update the owner-specific job condition in the workflow, the Scholar profile and article IDs, and the site's personal content before enabling Actions.

A successful run validates the all-time metrics, article counts, and check date as one snapshot, saves and commits any changes to `main`, and requests a GitHub Pages rebuild. Each run records its provider, check time, and result in the Actions summary, including successful checks with no data changes. Failed requests, missing data, and incomplete pagination leave the previous snapshot and date intact. The webpage reads this saved snapshot rather than making API requests for each visitor. Google Scholar's own data may stay unchanged between daily checks.

### Verify locally

With Python 3.10 or newer:

```sh
python3 -m venv /tmp/scholar-tools
/tmp/scholar-tools/bin/pip install -r scripts/requirements-scholar.txt
/tmp/scholar-tools/bin/python -m unittest discover -s tests -p 'test_scholar_stats.py'
/tmp/scholar-tools/bin/python scripts/update_scholar_stats.py --provider direct --dry-run
```

The `direct` provider reads the public Google Scholar HTML without an API key. It is useful for local verification, but Google can limit or block these requests. `--dry-run` validates and prints the result without changing the saved data; local success does not establish that the cloud workflow works.

## Preview locally

With Ruby and Bundler installed, run these commands from the repository root:

```sh
bundle install
bundle exec jekyll serve --host 127.0.0.1 --port 4000
```

Open [http://127.0.0.1:4000](http://127.0.0.1:4000). To check a production build without starting a server:

```sh
bundle exec jekyll build --strict_front_matter
```

## Credits

Based on the [Minimal Light](https://github.com/yaoyao-liu/minimal-light) theme, customized for Shaoyan Liu's academic website.

The repository includes the original [CC0 1.0 Universal license](LICENSE). The CV reader uses [PDF.js](https://mozilla.github.io/pdf.js/), distributed separately under its [Apache 2.0 license](assets/vendor/pdfjs/LICENSE).
