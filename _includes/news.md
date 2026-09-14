<h2 class="news-home-heading">News</h2>

{% include news-list.html limit=6 %}

<p class="news-all-link"><a href="{{ '/news/' | relative_url }}">View all news <span aria-hidden="true">&rarr;</span></a></p>
