from __future__ import absolute_import

import os
import json
import numpy

from celery import shared_task
from search.models import JobInfo
from elasticsearch import Elasticsearch
from crawler.models import CrawlInfo
from clustering.algorithms import Mapper


def index_fetched_publication(es, index, path):
    with open(path, 'r') as infile:
        page_info = json.load(infile)
        es.index(index=index, doc_type='publication', id=page_info.get('id'), body=page_info)
        es.index(index="global-index", doc_type='publication', id=page_info.get('id'), body=page_info)

    # es.indices.refresh(index=index)


@shared_task
def index_fetched_publications(crawl_info_id):
    es = Elasticsearch()
    crawl_info = CrawlInfo.objects.get(id=crawl_info_id)
    pages = os.listdir('managed_data/crawled_publications/%d' % crawl_info.id)

    for page in pages:
        index_fetched_publication(es, "index-%s" % crawl_info.id,
                                  'managed_data/crawled_publications/%d/%s' % (crawl_info.id, page))


def index_fetched_author(es, index, path):
    with open(path, 'r') as infile:
        author_info = json.load(infile)
        es.index(index=index, doc_type='author', id=author_info.get('id'), body=author_info)
        es.index(index="global-authors-index", doc_type='author', id=author_info.get('id'), body=author_info)

    # es.indices.refresh(index=index)


@shared_task
def index_fetched_authors(crawl_info_id):
    es = Elasticsearch()
    crawl_info = CrawlInfo.objects.get(id=crawl_info_id)
    pages = os.listdir('managed_data/crawled_authors/%d' % crawl_info.id)

    for page in pages:
        index_fetched_author(es, "index-%s" % crawl_info.id,
                             'managed_data/crawled_authors/%d/%s' % (crawl_info.id, page))


@shared_task
def calculate_pagerank_and_insert_to_elasticsearch(index_id, alpha, job_info_id):
    es = Elasticsearch()

    job_info = JobInfo.objects.get(id=job_info_id)
    job_info.save()

    job_info.info = json.dumps({'message': 'Fetching Publications From Elastic Joon ...', 'percentage': 7})
    job_info.save()

    publications = es.search(index_id, 'publication', body={"size": 10000, "query": {"match_all": {}}})['hits']['hits']
    publications = {int(publication.get('_id')): publication.get('_source') for publication in publications}

    mapper = Mapper()
    for publication in publications:
        mapper.create_sid(publication)

    N = mapper.size()
    links_graph = numpy.zeros(shape=(N, N))

    job_info.info = json.dumps({'message': 'Fetched Publications From Elastic Joon ...<br>'
                                           'Creating The Great Matrix ...', 'percentage': 35})
    job_info.save()

    initial_x = None
    for sid_1 in range(N):
        uid_1 = mapper.get_uid(sid_1)
        ones = 0
        for sid_2 in range(N):
            if sid_1 == sid_2:
                continue
            uid_2 = mapper.get_uid(sid_2)
            if uid_2 in publications[uid_1].get('references') or uid_1 in publications[uid_2].get('citations'):
                links_graph[sid_1][sid_2] = 1
                ones += 1
                if initial_x is None:
                    initial_x = sid_1
        if ones == 0:
            for sid_2 in range(N):
                links_graph[sid_1][sid_2] = 1. / N
        else:
            for sid_2 in range(N):
                links_graph[sid_1][sid_2] = links_graph[sid_1][sid_2] / ones * (1-alpha) + alpha / N
        # sum = 0
        # for sid_2 in range(N):
        #     sum += links_graph[sid_1][sid_2]
        # print(sum)

    job_info.info = json.dumps({'message': 'Multiplying ...', 'percentage': 60})
    job_info.save()

    links_graph = numpy.mat(links_graph)
    probability_vector = numpy.mat(numpy.zeros(shape=(1, N)) + 1. / N)
    # probability_vector[0, initial_x] = 1.

    # prev_prob_vec = probability_vector
    for i in range(365):
        probability_vector = probability_vector * links_graph
        # print("|x * links_graph|", numpy.sum(probability_vector))
        probability_vector = probability_vector / numpy.mat(numpy.sum(probability_vector))
        # print("|x * links_graph / |||", numpy.sum(probability_vector))
        # print(numpy.sum(prev_prob_vec - probability_vector))
        # prev_prob_vec = probability_vector

    # print(probability_vector)

    job_info.info = json.dumps({'message': 'Writing to ElasticSearch ...', 'percentage': 80})
    job_info.save()

    max_PR = numpy.matrix.max(probability_vector)

    for sid in range(N):
        uid = mapper.get_uid(sid)
        PR = probability_vector[0, sid] / max_PR
        es.update(index=index_id, doc_type='publication', id=str(uid), body={"doc": {'PR': PR}})
        es.update(index='global-index', doc_type='publication', id=str(uid), body={"doc": {'PR': PR}})

    job_info.info = json.dumps({'message': 'Fenitto ...', 'percentage': 100})
    job_info.save()
