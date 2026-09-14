---
layout: default
title: CV
permalink: /cv/
full_width: true
---

<div class="cv-heading">
  <h1>Curriculum Vitae</h1>
  <a class="cv-download" href="{{ site.cv_pdf | relative_url }}" download="Shaoyan_Liu_CV.pdf" aria-label="Download Shaoyan Liu's CV (PDF)" title="Download CV (PDF)">
    <i class="fa-solid fa-file-pdf" aria-hidden="true"></i>
  </a>
</div>

<a class="cv-view-link" href="{{ site.cv_pdf | relative_url }}" target="_blank" rel="noopener noreferrer">View PDF <i class="fa-solid fa-arrow-up-right-from-square" aria-hidden="true"></i></a>

<div class="cv-reader" data-pdf-url="{{ site.cv_pdf | relative_url }}" aria-label="CV PDF reader">
  <div class="cv-toolbar" hidden>
    <span class="cv-page-count"><span data-cv-total>–</span> pages</span>
    <span class="cv-toolbar-divider" aria-hidden="true"></span>
    <button type="button" data-cv-action="out" aria-label="Zoom out">−</button>
    <button type="button" data-cv-action="fit">Fit width</button>
    <button type="button" data-cv-action="in" aria-label="Zoom in">+</button>
  </div>
  <p class="cv-reader-status" role="status">Loading PDF…</p>
  <div class="cv-reader-body">
    <button class="cv-sections-toggle" type="button" aria-expanded="false" aria-controls="cv-sections" hidden><i class="fa-solid fa-list" aria-hidden="true"></i> Sections</button>
    <nav id="cv-sections" class="cv-sections-panel" aria-label="CV sections" hidden>
      {% for item in site.data.cv_sections %}
      <button type="button" data-cv-heading="{{ item.heading | escape }}" hidden>{{ item.title }}</button>
      {% endfor %}
    </nav>
    <div class="cv-page-viewport" role="region" aria-label="CV pages, scroll to read" tabindex="0" hidden></div>
  </div>
  <noscript><p>Please use View PDF above to read the CV.</p></noscript>
</div>
<script type="module" src="{{ '/assets/js/cv.js' | relative_url }}?v={{ site.time | date: '%s' }}"></script>
