{% for link in site.data.navigation.main reversed %}
  {% if link.right %}
    <a class="normal right" href="./{{ link.url }}"{% if page.title == link.title %} aria-current="page"{% endif %}>{{ link.title }}</a>
    {% else %}
    <a class="normal" href="./{{ link.url }}"{% if page.title == link.title %} aria-current="page"{% endif %}>{{ link.title }}</a>
  {% endif %}
{% endfor %}
