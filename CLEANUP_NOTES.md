# Cleanup Notes

This is the deep-cleaned version of the Shaoyan Liu academic website.

## Removed legacy/template content

- Old generated `html_source_file/` copy
- Yaoyao Liu Google Scholar crawler and its GitHub Actions workflow
- Legacy Talks page/include
- Unused `simple` layout
- Unused images and scripts
- macOS `.DS_Store` / `__MACOSX` metadata
- Entire `assets/Illinois/` branding/favicon package
- Illinois Brand CSS dependency
- Unused jQuery 1.5
- Unused `github-stars.js`
- Unneeded `favicon-switcher.js`
- Obsolete iPhone viewport helper `scale.fix.js`
- Legacy `enable_hopkins_logo` configuration

## Preserved current functionality

- Home / Publications / Teaching / Services pages
- Penn State logo and current avatar
- CV, publication PDFs and BibTeX files
- Responsive navigation
- Back-to-top button
- GoatCounter visitor tracking/statistics
- Current favicon (`assets/img/favicon.png`)

## SEO fixes

`robots.txt` and `sitemap.xml` use `https://shaoyanliu.github.io/` rather than the original template author's domain.
