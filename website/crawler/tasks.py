from __future__ import absolute_import

import os
import json
import requests

from pprint import pprint
from bs4 import BeautifulSoup
from celery import shared_task
from .models import CrawlInfo


class Statics:
    allowed_publication_types = [
        "Article",
        "Conference Paper"
    ]
    base_address = "https://www.researchgate.net"
    reference_depth_limit = 10
    citation_depth_limit = 10


class InformationDownloader:
    request_session = None

    @staticmethod
    def get_researcher_id_from_url(url):
        right_hand_side = url.split("researcher/")[-1]
        return int(right_hand_side.split("_")[0])

    @staticmethod
    def get_publication_id_from_url(url):
        right_hand_side = url.split("publication/")[-1]
        return int(right_hand_side.split("_")[0])

    @staticmethod
    def get_html_content(url):
        headers = {
            'authority': 'www.researchgate.net',
            'accept': 'text/html,application/xhtml+xml,application/xml',
        }
        r = InformationDownloader.request_session.get(url, headers=headers)
        return r.text

    @staticmethod
    def get_ajax_content(url):
        headers = {
            'authority': 'www.researchgate.net',
            'accept': 'application/json',
            'x-requested-with': 'XMLHttpRequest',
        }
        r = InformationDownloader.request_session.get(url, headers=headers)
        return json.loads(r.text)


class InformationParser:
    @staticmethod
    def get_citations(publication_id):
        ajax_url = "https://www.researchgate.net/publicliterature.PublicationIncomingCitationsList.html?publicationUid=%d&showCitationsSorter=true&showAbstract=false&showType=false&showPublicationPreview=false&swapJournalAndAuthorPositions=false&limit=10000"%publication_id
        ajax_result = InformationDownloader.get_ajax_content(ajax_url)
        results = ajax_result.get('result').get('data').get('citationItems')
        citations = []
        for result in results:
            id = result.get('data').get('publicationUid')
            type = result.get('data').get('publicationType')
            url = "%s/%s" % (Statics.base_address, result.get('data').get('publicationUrl'))
            if type in Statics.allowed_publication_types:
                # citations.append(dict(id=id, type=type, url=url))
                citations.append(id)
        return citations

    @staticmethod
    def get_references(publication_id):
        ajax_url = "https://www.researchgate.net/publicliterature.PublicationCitationsList.html?publicationUid=%d&showCitationsSorter=true&showAbstract=false&showType=false&showPublicationPreview=false&swapJournalAndAuthorPositions=false&limit=10000"%publication_id
        ajax_result = InformationDownloader.get_ajax_content(ajax_url)
        results = ajax_result.get('result').get('data').get('citationItems')
        references = []
        for result in results:
            id = result.get('data').get('publicationUid')
            type = result.get('data').get('publicationType')
            url = "%s/%s" % (Statics.base_address, result.get('data').get('publicationUrl'))
            if type in Statics.allowed_publication_types:
                # references.append(dict(id=id, type=type, url=url))
                references.append(id)
        return references

    @staticmethod
    def get_authors(publication_id):
        ajax_url = "https://www.researchgate.net/publicliterature.PublicationAuthorList.loadMore.html?publicationUid=%d&offset=0&count=100&limit=10000"%publication_id
        ajax_result = InformationDownloader.get_ajax_content(ajax_url)
        results = ajax_result.get('result').get('loadedItems')
        authors = []
        for author in results:
            authors.append(dict(
                    id=author.get('authorUid'),
                    name=author.get('nameOnPublication'),
                    # url="%s/%s" % (Statics.base_address, author.get('authorURL'))
            ))
            # authors.append(author.get('authorUid'))
        return authors

    @staticmethod
    def get_publication_data(publication_id):
        url = "https://www.researchgate.net/publication/%d" % publication_id
        content = InformationDownloader.get_html_content(url)
        soup = BeautifulSoup(content, 'html.parser')
        if len(soup.select('.publication-abstract-text')) > 0:
            try:
                title = soup.select('.publication-title')[0].getText()
            except Exception:
                raise Exception('No Title Found')
            try:
                abstract = soup.select('.publication-abstract-text')[0].getText()
            except Exception:
                raise Exception('No Abstract Found')
        else:
            try:
                title = soup.select('.pub-title')[0].getText()
            except Exception:
                raise Exception('No Title Found')
            try:
                abstract = soup.select('.pub-abstract [itemprop="description"] div')[0].getText()
            except Exception:
                raise Exception('No Abstract Found')
        return dict(id=publication_id, title=title, abstract=abstract,
                    authors=InformationParser.get_authors(publication_id),
                    citations=InformationParser.get_citations(publication_id),
                    references=InformationParser.get_references(publication_id))

    @staticmethod
    def extract_publication_ids_in_a_page(url):
        content = InformationDownloader.get_html_content(url)
        soup = BeautifulSoup(content, 'html.parser')
        link_descriptions = soup.find_all(class_='publication-type',
                                          string=["%s:" % pub_type for pub_type in Statics.allowed_publication_types])
        ids = []
        for link_desc in link_descriptions:
            ids.append(InformationDownloader.get_publication_id_from_url(link_desc.find_next_sibling().get('href')))
        return ids

    @staticmethod
    def get_publications_of_author(author_id):
        publication_ids = []
        page = 1
        while True:
            url = "https://www.researchgate.net/researcher/%d/publications/%d" % (author_id, page)
            content = InformationDownloader.get_html_content(url)
            soup = BeautifulSoup(content, 'html.parser')
            link_descs = soup.find_all(class_='publication-type',
                                       string=["%s:" % pub_type for pub_type in Statics.allowed_publication_types])
            if len(link_descs) == 0:
                break
            for link_desc in link_descs:
                publication_ids.append(InformationDownloader.
                                       get_publication_id_from_url(link_desc.find_next_sibling().get('href')))
            page += 1
        return publication_ids


# SCHEDULER AND PIPELINE

@shared_task
def crawl_publication_page(crawl_info_id, publication_id):

    crawl_info = CrawlInfo.objects.get(id=crawl_info_id)
    if crawl_info.successful_crawls >= crawl_info.limit:
        return

    try:
        publication_data = InformationParser.get_publication_data(publication_id)
    except Exception as e:
        print(e)
        print("Publication id = `%d`" % publication_id)
        crawl_info = CrawlInfo.objects.get(id=crawl_info_id)
        crawl_info.queue_size -= 1
        crawl_info.save()
        return

    crawl_info = CrawlInfo.objects.get(id=crawl_info_id)
    if crawl_info.successful_crawls >= crawl_info.limit:
        return

    if os.path.isfile('crawl_result/%d/%d.json' % (crawl_info.id, publication_id)):
        crawl_info.queue_size -= 1
        crawl_info.save()
        pprint("SKIP: publication with id `%d` has been fetched before." % publication_id)
        return

    pprint("%d: publication with id `%d` successfully fetched." % (crawl_info.successful_crawls, publication_id))

    with open('crawl_result/%d/%d.json' % (crawl_info.id, publication_id), 'w') as outfile:
        json.dump(publication_data, outfile)
    crawl_info.successful_crawls = len(os.listdir("crawl_result/%d" % crawl_info.id))
    crawl_info.save()

    crawl_info = CrawlInfo.objects.get(id=crawl_info_id)
    if crawl_info.queue_size > crawl_info.limit * 5:
        return

    crawl_info.queue_size += len(publication_data.get('references')[:crawl_info.i_limit])
    crawl_info.queue_size += len(publication_data.get('citations')[:crawl_info.o_limit])
    crawl_info.save()

    for reference in publication_data.get('references')[:Statics.reference_depth_limit]:
        crawl_publication_page.delay(crawl_info_id, reference)
    for citation in publication_data.get('citations')[:Statics.citation_depth_limit]:
        crawl_publication_page.delay(crawl_info_id, citation)


@shared_task
def start_crawl(crawl_info_id, max_publication_link):
    crawl_info = CrawlInfo.objects.get(id=crawl_info_id)

    publication_ids = InformationParser.extract_publication_ids_in_a_page(crawl_info.init_url)
    publication_ids = publication_ids[:max_publication_link]
    for publication_id in publication_ids:
        crawl_publication_page.delay(crawl_info_id, publication_id)


print("New HTTP Connection Created :D")
InformationDownloader.request_session = requests.session()