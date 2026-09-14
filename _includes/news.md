<h2 style="margin: 60px 0px 10px;">News</h2>

<ul>
  {% for item in site.data.news limit:6 %}
  <li><strong>[{{ item.date }}]</strong> {{ item.content }}</li>
  {% endfor %}
</ul>

{% if site.data.news.size > 6 %}
<details class="news-archive">
  <summary>Show more</summary>
  <ul>
    {% for item in site.data.news offset:6 %}
    <li><strong>[{{ item.date }}]</strong> {{ item.content }}</li>
    {% endfor %}
  </ul>
</details>
{% endif %}
