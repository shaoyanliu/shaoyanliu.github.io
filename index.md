---
layout: homepage
title: About
seo_title: Shaoyan Liu | Penn State | Battery Safety Research
---

<div class="about-heading">
  <h1 id="about-me">{{ site.title }}</h1>
  <p class="about-tagline">Battery safety, thermal runaway, and data-driven modeling</p>
</div>

<div class="about-intro" markdown="1">

<figure class="about-portrait">
  <img src="{{ site.avatar | relative_url }}" alt="Shaoyan Liu" />
  <figcaption><a href="https://maps.app.goo.gl/J4aAKyqFRWxEpaaZ9" title="View location on Google Maps"><span aria-hidden="true">📍</span><span>Happy Valley · State College</span></a></figcaption>
</figure>

{% include scholar-stats.html %}

Greetings! I am Shaoyan Liu (劉 少言), a Ph.D. student in [Energy Mechanics and Sustainability Laboratory](https://junxu-emslab.github.io/) (EMSLab) and [Department of Mechanical Engineering](https://www.me.psu.edu/) at [Penn State University](https://www.psu.edu/), advised by [Prof. Jun Xu](https://www.me.psu.edu/department/directory-detail-g.aspx?q=jkx5175). Previously, I completed my M.S. at [Shanghai Jiao Tong University](https://en.sjtu.edu.cn/) and my B.S. at [Beijing Jiaotong University](http://en.bjtu.edu.cn/). My current research interests mainly lie in **battery safety**.

In my spare time, I enjoy doing sports (mostly running, cycling and working out at the gym), traveling, and going on hikes with friends (find my workout records on my [Strava page](https://www.strava.com/athletes/shaoyanliu)<style>
  .strava-badge- { display: inline-block; height: 16px; }
  .strava-badge- img { visibility: hidden; height: 16px; }
  .strava-badge-:hover { background-position: 0 -31px; }
  .strava-badge-follow { height: 16px; width: 16px; background: url(//badges.strava.com/echelon-sprite-16.png) no-repeat 0 0; }
</style>
<a href="https://www.strava.com/athletes/shaoyanliu" class="strava-badge- strava-badge-follow" target="_blank"><img src="//badges.strava.com/echelon-sprite-16.png" alt="Strava" /></a>). Also, I enjoy music, photography, and philosophy.

</div>

<div class="about-mentoring" style="border: 1px solid var(--site-border); padding: 11px; background-color: var(--site-surface); color: var(--site-card-text); border-radius: 5px;">
  <strong><span style="color:var(--site-callout-accent);">Pin1:</span> I dedicate one hour per week to mentor and offer suggestions to underrepresented students or anyone in need. You are welcome to fill in <a href="https://forms.gle/VpNYkEUKp5PXqFSv8">this form</a> if you are interested.</strong>
</div>


{% include_relative _includes/news.md %}

{% include publications.md selected_only=true %}
