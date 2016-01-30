"""website URL Configuration

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/1.8/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  url(r'^$', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  url(r'^$', Home.as_view(), name='home')
Including another URLconf
    1. Add an import:  from blog import urls as blog_urls
    2. Add a URL to urlpatterns:  url(r'^blog/', include(blog_urls))
"""
from django.conf.urls import include, url
from django.contrib import admin

urlpatterns = [
    # url(r'^admin/', include(admin.site.urls)),
    url(r'^$', 'search.views.home_page'),
    url(r'^crawl/$', 'crawler.views.crawl_page'),
    url(r'^crawl/authors/$', 'crawler.views.crawl_author_page'),
    url(r'^crawl/status/(?P<id>\d+)/$', 'crawler.views.crawl_status_page'),
    url(r'^indexing/$', 'search.views.indexing_page'),
    url(r'^indexing/authors/$', 'search.views.indexing_authors'),
    url(r'^indexing/status/(?P<id>\d+)/$', 'search.views.indexing_status_page'),
    url(r'^search/$', 'search.views.search_page'),
    url(r'^clustering/authors/result/$', 'clustering.views.author_clustering_result'),
    url(r'^calculate/pagerank/$', 'search.views.calculate_pagerank'),
]
