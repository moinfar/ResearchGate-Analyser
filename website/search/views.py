import os
import json

from django.shortcuts import render
from django.http import HttpResponse
from crawler.models import CrawlInfo
from django.shortcuts import redirect
from elasticsearch import Elasticsearch
from search.tasks import index_fetched_publications


def home_page(request):
    if CrawlInfo.objects.filter(type="publication").exists():
        last_crawl_id = CrawlInfo.objects.filter(type="publication").latest('id').id
    else:
        last_crawl_id = -1
    return render(request, 'home.html', {'last_crawl_id': last_crawl_id})


def search_page(request):
    result = None
    if request.GET.get('q') is not None and request.GET.get('q') != '':
        q = request.GET.get('q')
        w_title = request.GET.get('title_weight')
        w_abstract = request.GET.get('abstract_weight')
        w_authors = request.GET.get('author_weight')
        w_page_rank = request.GET.get('PR_weight')
        limit = request.GET.get('limit', 30)
        es = Elasticsearch()
        es.indices.refresh(index="global-index")
        # search_query = {
        #     "query": {
        #         "bool": {
        #             "should": [
        #                 {"match": {
        #                     "title": {
        #                         "query": "learn",
        #                         "boost": 3
        #                     }
        #                 }},
        #                 {"match": {
        #                     "abstract": {
        #                         "query": "learn",
        #                         "boost": 1
        #                     }
        #                 }}
        #             ]
        #         }
        #     }
        # }
        search_query = {
            "query": {
                "multi_match": {
                    "query":    q,
                    "type":     "cross_fields",
                    "fields":   ["title^%s" % w_title, "abstract^%s" % w_abstract, "authors.name^%s" % w_authors]
                }
            },
            "size": limit,
        }
        res = es.search(index="global-index", body=search_query)
        result = res['hits']

    return render(request, 'search.html', {'request': request, 'result': result})


def indexing_page(request):
    if request.GET.get('crawl_id') is not None and request.GET.get('crawl_id') != '':
        crawl_info = CrawlInfo.objects.get(id=request.GET.get('crawl_id'))
        index_fetched_publications.delay(crawl_info.id)
        return redirect("/indexing/status/%d/" % crawl_info.id)

    crawls_info = CrawlInfo.objects.filter(type="publication")
    return render(request, 'indexing.html', {'crawls_info': crawls_info})


def indexing_status_page(request, id):
    es = Elasticsearch()
    crawl_info = CrawlInfo.objects.get(id=id)
    try:
        es.indices.refresh(index="index-%d" % crawl_info.id)
        percentage = int(es.count("index-%d" % crawl_info.id, "publication").get('count') * 100 /
                         crawl_info.successful_crawls)
        percentage = max(1, percentage)
    except:
        percentage = 0

    if request.GET.get('type', 'HTML') == 'JSON':
        result = json.dumps({'status': 'OK', 'percent': percentage},
                            ensure_ascii=False, encoding='utf8')
        return HttpResponse(result, content_type='application/json; charset=utf-8')

    return render(request, 'indexing_status.html', {'percent': percentage})
