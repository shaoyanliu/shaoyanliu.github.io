{% if include.selected_only %}
<h2 id="selected-publications" class="selected-publications-heading"><a href="{{ '/publications/' | relative_url }}">Selected Publications</a></h2>
{% else %}
<h1 id="publications" class="page-title">Publications</h1>
<p class="publication-legend">[<a href="https://scholar.google.com/citations?&user=Yw_kFE4AAAAJ" target="_blank" rel="noopener noreferrer">Google Scholar</a> | Corresponding author = <sup><i class="fa-regular fa-envelope fa-xs"></i></sup>]</p>
{% endif %}


<div class="publications{% if include.selected_only %} selected-publications{% endif %}" data-publication-list>
{% unless include.selected_only %}
<div class="publication-search" data-publication-search-controls role="search" aria-label="Search publications" hidden>
  <input type="search" data-publication-search aria-label="Search publications by title, author, journal, or keyword" placeholder="Search publications by title, author, journal, or keyword" autocomplete="off" spellcheck="false" aria-describedby="publication-filter-status">
  <button type="button" class="publication-search-clear" data-search-clear aria-label="Clear search" title="Clear search" hidden>&times;</button>
</div>
<div class="publication-filters" data-publication-filters role="group" aria-label="Filter publications by topic" hidden>
  <button type="button" data-topic-filter="all" aria-pressed="true">All</button>
  {% for topic in site.data.publication_topics %}
  <button type="button" data-topic-filter="{{ topic.id | escape }}" title="{{ topic.name | default: topic.label | escape }}" aria-pressed="false">{{ topic.label | escape }}</button>
  {% endfor %}
</div>
<p class="publication-filter-status" id="publication-filter-status" data-filter-status role="status" aria-live="polite" hidden></p>
{% endunless %}
{% assign publication_years = site.data.publications.main | group_by: "year" | sort: "name" | reverse %}
{% assign publication_number = site.data.publications.main.size %}

{% if include.selected_only %}<ol class="bibliography" role="list">{% endif %}
{% for year_group in publication_years %}
{% unless include.selected_only %}
<div class="publication-year-group" data-publication-year>
<h3 class="year" id="publications-{{ year_group.name }}"><span>{{ year_group.name }}</span></h3>
<ol class="bibliography" reversed start="{{ publication_number }}">
{% endunless %}

{% for link in year_group.items %}
{% if include.selected_only and link.selected != true %}
{% assign publication_number = publication_number | minus: 1 %}
{% continue %}
{% endif %}

{% capture search_text %}{{ link.title | strip_html }} {{ link.authors | strip_html }} {{ link.conference | strip_html }} {{ link.conference_short }} {{ link.year }} {{ link.abstract }} {% for topic in site.data.publication_topics %}{% if link.topics contains topic.id %} {{ topic.id }} {{ topic.label }} {{ topic.name }}{% endif %}{% endfor %}{% endcapture %}
<li{% unless include.selected_only %} value="{{ publication_number }}"{% endunless %} data-publication data-topics="{{ link.topics | join: ' ' | escape }}" data-search-text="{{ search_text | strip_newlines | escape }}">
<div class="pub-row">
  <div class="col-sm-3 abbr" style="position: relative;padding-right: 15px;padding-left: 15px;">
    <img src="{{ link.image }}" class="teaser img-fluid z-depth-1" style="width=100;height=40%">
            <abbr class="badge">{{ link.conference_short }}</abbr>
  </div>
  <div class="col-sm-9" style="position: relative;padding-right: 15px;padding-left: 20px;">
      <div class="title">{% unless include.selected_only %}<span class="publication-number">{{ publication_number }}.</span> {% endunless %}<a href="{{ link.doi }}">{{ link.title }}</a></div>
      <div class="author">{{ link.authors }}</div>
      <div class="periodical"><em>{{ link.conference }}</em>
      </div>
    <div class="links">
      {% for topic in site.data.publication_topics %}
      {% if link.topics contains topic.id %}
      <span class="publication-topic" data-topic="{{ topic.id | escape }}" title="{{ topic.name | default: topic.label | escape }}">{{ topic.label | downcase | escape }}</span>
      {% endif %}
      {% endfor %}
      {% if link.abstract %}
      <button class="publication-action" type="button" data-abstract-toggle aria-expanded="false" aria-controls="abstract-{{ publication_number }}" hidden>Abstract</button>
      {% endif %}
      {% if link.doi %} 
      <a href="{{ link.doi }}" class="btn btn-sm z-depth-0" role="button" target="_blank">HTML</a>
      {% endif %}
      {% if link.pdf %} 
      <a href="{{ link.pdf }}" class="btn btn-sm z-depth-0" role="button" target="_blank">PDF</a>
      {% endif %}
      {% if link.code %} 
      <a href="{{ link.code }}" class="btn btn-sm z-depth-0" role="button" target="_blank">Code</a>
      {% endif %}
      {% if link.page %} 
      <a href="{{ link.page }}" class="btn btn-sm z-depth-0" role="button" target="_blank">Project Page</a>
      {% endif %}
      {% if link.data %} 
      <a href="{{ link.data }}" class="btn btn-sm z-depth-0" role="button" target="_blank">Dataset</a>
      {% endif %}
      {% if link.bibtex %} 
      {% assign bibtex_filename = link.bibtex | split: '/' | last %}
      {% assign bibtex_path = '/bib/' | append: bibtex_filename %}
      <a href="{{ bibtex_path | relative_url }}" class="btn btn-sm z-depth-0" data-bibtex-link data-paper-title="{{ link.title | strip_html | escape }}">BibTeX</a>
      {% endif %}
      {% if link.scholar_id and site.data.scholar_stats.articles %}
      {% assign scholar_article = site.data.scholar_stats.articles[link.scholar_id] %}
      {% if scholar_article and scholar_article.citations != nil %}
      <a class="publication-citations" href="{% if scholar_article.cited_by_url %}{{ scholar_article.cited_by_url | escape }}{% else %}https://scholar.google.com/citations?view_op=view_citation&amp;hl=en&amp;user={{ site.data.scholar_stats.profile_id | url_encode }}&amp;citation_for_view={{ link.scholar_id | url_encode }}{% endif %}" target="_blank" rel="noopener noreferrer" title="Google Scholar citations · checked {{ site.data.scholar_stats.updated | date: '%B %-d, %Y' }}" aria-label="{{ scholar_article.citations }} Google Scholar citations for {{ link.title | strip_html | escape }}">Cited by <span>{{ scholar_article.citations }}</span></a>
      {% endif %}
      {% endif %}
      {% if link.notes %} 
      <strong> <i style="color:#e74d3c; font-weight:600">{{ link.notes }}</i></strong>
      {% endif %}
      {% if link.others %} 
      {{ link.others }}
      {% endif %}
    </div>
    {% if link.abstract %}
    <div class="publication-abstract" id="abstract-{{ publication_number }}">
      <h4>Abstract</h4>
      <p>{{ link.abstract | escape }}</p>
    </div>
    {% endif %}
  </div>
</div>
</li>

{% assign publication_number = publication_number | minus: 1 %}
{% endfor %}

{% unless include.selected_only %}
</ol>
</div>
{% endunless %}
{% endfor %}
{% if include.selected_only %}</ol>{% endif %}
</div>
{% if include.selected_only %}
<p class="selected-publications-all"><a href="{{ '/publications/' | relative_url }}">View all publications <span aria-hidden="true">&rarr;</span></a></p>
{% endif %}

<dialog class="publication-bibtex-dialog" id="publication-bibtex-dialog" aria-labelledby="bibtex-dialog-title" aria-describedby="bibtex-paper-title">
  <div class="bibtex-dialog-heading">
    <h2 id="bibtex-dialog-title">BibTeX</h2>
    <button type="button" class="bibtex-close" data-bibtex-close aria-label="Close citation">&times;</button>
  </div>
  <p class="bibtex-paper-title" id="bibtex-paper-title" data-bibtex-title></p>
  <pre class="bibtex-content" data-bibtex-content tabindex="0" aria-label="BibTeX citation"></pre>
  <p class="bibtex-status" data-bibtex-status role="status" aria-live="polite"></p>
  <div class="bibtex-dialog-actions">
    <button type="button" data-bibtex-copy disabled>Copy BibTeX</button>
    <a data-bibtex-download download>Download .bib</a>
  </div>
</dialog>
<script src="{{ '/assets/js/publications.js' | relative_url }}?v={{ site.time | date: '%s' }}" defer></script>
