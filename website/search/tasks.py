from __future__ import absolute_import

import os
import json

from celery import shared_task
from elasticsearch import Elasticsearch
from crawler.models import CrawlInfo


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
