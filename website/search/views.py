import os
import json
import numpy

from search.models import JobInfo
from django.shortcuts import render
from django.http import HttpResponse
from crawler.models import CrawlInfo
from django.shortcuts import redirect
from elasticsearch import Elasticsearch
from search.tasks import index_fetched_publications, index_fetched_authors
from search.tasks import calculate_pagerank_and_insert_to_elasticsearch


def home_page(request):
    if CrawlInfo.objects.filter(type="publication").exists():
        last_crawl_id = CrawlInfo.objects.filter(type="publication").latest('id').id
    else:
        last_crawl_id = -1
    return render(request, 'home.html', {'last_crawl_id': last_crawl_id})


def search_page(request):
    result = None
    clusters = None
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
        if request.GET.get('cluster_label') is not None and request.GET.get('cluster_label') != 'all':
            search_query = {
                "query": {
                    "bool": {
                        "should": [
                            {
                                "match": {
                                    "cluster_label":    request.GET.get('cluster_label')
                                }
                            },
                            {
                                "multi_match": {
                                    "query":    q,
                                    "type":     "cross_fields",
                                    "fields":   ["title^%s" % w_title, "abstract^%s" % w_abstract, "authors.name^%s" % w_authors]
                                },
                            },
                        ]
                    }
                },
                "size": limit,
            }
        else:
            search_query = {
                'query': {
                    'function_score': {
                        'functions': [
                            {
                                'script_score': {
                                    'script': "%s * doc['PR'].value" % w_page_rank
                                }
                            }
                        ],
                        'query': {
                            'multi_match': {
                                'query':    q,
                                'type':     'cross_fields',
                                'fields':   ['title^%s' % w_title, 'abstract^%s' % w_abstract, 'authors.name^%s' % w_authors]
                            },
                        },
                        'filter': {
                            'exists': {
                                'field': 'PR'
                            }
                        },
                        'score_mode': 'sum',
                    }
                },
                "size": limit,
            }
            # search_query = {
            #     "query": {
            #         "custom_score": {
            #             "query": {
            #                 "multi_match": {
            #                     "query":    q,
            #                     "type":     "cross_fields",
            #                     "fields":   ["title^%s" % w_title, "abstract^%s" % w_abstract, "authors.name^%s" % w_authors]
            #                 },
            #             },
            #             "script": "_score * 2"
            #         }
            #     },
            #     "size": limit,
            # }

        res = es.search(index="global-index", body=search_query)
        result = res['hits']
        clusters = {}
        for r in res['hits']['hits']:
            if 'cluster_id' in r['_source']:
                clusters[r['_source']['cluster_id']] = r['_source']['cluster_label']

    return render(request, 'search.html', {'request': request, 'result': result, 'clusters': clusters})


def indexing_page(request):
    if request.GET.get('crawl_id') is not None and request.GET.get('crawl_id') != '':
        crawl_info = CrawlInfo.objects.get(id=request.GET.get('crawl_id'))
        index_fetched_publications.delay(crawl_info.id)
        return redirect("/indexing/status/%d/" % crawl_info.id)

    crawls_info = CrawlInfo.objects.filter(type="publication")
    return render(request, 'indexing.html', {'crawls_info': crawls_info})


def indexing_authors(request):
    if request.GET.get('crawl_id') is not None and request.GET.get('crawl_id') != '':
        crawl_info = CrawlInfo.objects.get(id=request.GET.get('crawl_id'))
        index_fetched_authors.delay(crawl_info.id)
        return redirect("/indexing/status/%d/" % crawl_info.id)

    crawls_info = CrawlInfo.objects.filter(type="author")
    return render(request, 'indexing.html', {'crawls_info': crawls_info})


def indexing_status_page(request, id):
    es = Elasticsearch()
    crawl_info = CrawlInfo.objects.get(id=id)
    try:
        es.indices.refresh(index="index-%d" % crawl_info.id)
        percentage = int(es.count("index-%d" % crawl_info.id, crawl_info.type).get('count') * 100 /
                         crawl_info.successful_crawls)
        percentage = max(1, percentage)
    except Exception as e:
        percentage = 0

    if request.GET.get('type', 'HTML') == 'JSON':
        result = json.dumps({'status': 'OK', 'percent': percentage},
                            ensure_ascii=False, encoding='utf8')
        return HttpResponse(result, content_type='application/json; charset=utf-8')

    return render(request, 'indexing_status.html', {'percent': percentage})


def calculate_pagerank(request):
    es = Elasticsearch()

    if request.GET.get('index_id') is not None and request.GET.get('index_id') != '':
        index_id = request.GET.get('index_id')
        alpha = float(request.GET.get('alpha'))

        job_info = JobInfo(title='calculating PageRank for %s with alpha = %d' % (index_id, alpha),
                           info=json.dumps({'message': 'Starting ...', 'percentage': 3}))
        job_info.save()

        calculate_pagerank_and_insert_to_elasticsearch.delay(index_id, alpha, job_info.id)

        return redirect('/pagerank/status/%d/' % job_info.id)

    indexes = es.indices.get_mapping()
    return render(request, 'calculate_pagerank.html', {'indexes': indexes})


def pagerank_status_page(request, id):

    job_info = JobInfo.objects.get(id=id)
    info = json.loads(job_info.info)

    percentage = info['percentage']
    action = info['message']

    if request.GET.get('type', 'HTML') == 'JSON':
        result = json.dumps({'status': 'OK', 'percent': percentage, 'message': action},
                            ensure_ascii=False, encoding='utf8')
        return HttpResponse(result, content_type='application/json; charset=utf-8')

    return render(request, 'PR_status.html', {'percent': percentage, 'message': action})
