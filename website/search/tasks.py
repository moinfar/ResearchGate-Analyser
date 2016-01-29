from __future__ import absolute_import

import os
import json

from celery import shared_task
from elasticsearch import Elasticsearch
from crawler.models import CrawlInfo


@shared_task
def index_fetched_publication(index, path):
    es = Elasticsearch()
    with open(path, 'r') as infile:
        page_info = json.load(infile)
        es.index(index=index, doc_type='publication', id=page_info.get('id'), body=page_info)
        es.index(index="global-index", doc_type='publication', id=page_info.get('id'), body=page_info)

    # es.indices.refresh(index=index)


@shared_task
def index_fetched_publications(crawl_info_id):
    crawl_info = CrawlInfo.objects.get(id=crawl_info_id)
    pages = os.listdir('crawl_result/%d' % crawl_info.id)

    for page in pages:
        index_fetched_publication("index-%s" % crawl_info.id,
                                  'crawl_result/%d/%s' % (crawl_info.id, page))
