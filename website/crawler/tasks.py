from __future__ import absolute_import

import os
import json
import random
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
    cookies = None
    referer = Statics.base_address

    @staticmethod
    def get_researcher_id_from_url(url):
        right_hand_side = url.split("researcher/")[-1]
        return int(right_hand_side.split("_")[0])

    @staticmethod
    def get_publication_id_from_url(url):
        right_hand_side = url.split("publication/")[-1]
        return int(right_hand_side.split("_")[0])

    @staticmethod
    def get_html_content(url, return_response_url=False):

        # print("<<<  " + url)

        headers = {
            'authority': 'www.researchgate.net',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'accept-language': 'en-US,en;q=0.8',
            'accept-encoding': 'gzip, deflate, sdch',
            'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
                          '(KHTML, like Gecko) Chrome/47.0.2526.111 Safari/537.36',
            'referer': InformationDownloader.referer,
        }

        if random.random() < 0.02:
            InformationDownloader.request_session = requests.session()

        # print(InformationDownloader.cookies)
        r = InformationDownloader.request_session.get(url, headers=headers, cookies=InformationDownloader.cookies)
        if requests.utils.dict_from_cookiejar(r.cookies):
            InformationDownloader.cookies = requests.utils.dict_from_cookiejar(r.cookies)
        InformationDownloader.referer = url
        if return_response_url:
            return r.text, r.url
        return r.text

    @staticmethod
    def get_ajax_content(url):
        headers = {
            'authority': 'www.researchgate.net',
            'accept': 'application/json',
            'accept-language': 'en-US,en;q=0.8',
            'accept-encoding': 'gzip, deflate, sdch',
            'x-requested-with': 'XMLHttpRequest',
            'user-agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
                          '(KHTML, like Gecko) Chrome/47.0.2526.111 Safari/537.36',
            'referer': InformationDownloader.referer,
        }
        # print(InformationDownloader.cookies)
        r = InformationDownloader.request_session.get(url, headers=headers, cookies=InformationDownloader.cookies)
        if requests.utils.dict_from_cookiejar(r.cookies):
            InformationDownloader.cookies = requests.utils.dict_from_cookiejar(r.cookies)
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
    def get_author_info(author_id, forced_url=None):
        publication_ids = set()
        co_author_ids = []
        name = None
        page = 1
        while True:
            if not forced_url:
                url = "https://www.researchgate.net/researcher/%d/publications/%d" % (author_id, page)
            else:
                url = "%s/publications/%d" % (forced_url, page)
            content, new_url = InformationDownloader.get_html_content(url, True)
            # print(new_url, "<<>>", forced_url)
            if forced_url is None and "/publications" not in new_url:
                return InformationParser.get_author_info(author_id, new_url)
            soup = BeautifulSoup(content, 'html.parser')

            previous_publication_ids = set(publication_ids)

            if len(soup.select(".ga-profile-header-name")) > 0:
                name = name or soup.select(".ga-profile-header-name")[0].string

                publication_links = soup.select(".js-publication-title-link")
                if len(publication_links) == 0:
                    break

                for link in publication_links:
                    publication_ids.add(InformationDownloader.get_publication_id_from_url(link.get('href')))
            else:
                name = name or soup.select(".profile-header-name span")[0].string

                link_descs = soup.find_all(class_='publication-type')
                if len(link_descs) == 0:
                    break

                for link_desc in link_descs:
                    publication_ids.add(InformationDownloader.
                                        get_publication_id_from_url(link_desc.find_next_sibling().get('href')))

            co_authors = soup.select('a[href^="researcher/"]')
            for co_author in co_authors:
                co_author_ids.append(InformationDownloader.get_researcher_id_from_url(co_author.get('href')))

            if len(previous_publication_ids) == len(publication_ids):
                break

            page += 1

        co_author_ids = set(co_author_ids)
        if author_id in co_author_ids:
            co_author_ids.remove(author_id)
        co_author_ids = list(co_author_ids)

        return {'id': author_id, 'name': name, 'publications': list(publication_ids), 'co_authors': co_author_ids}



# SCHEDULER AND PIPELINE

@shared_task
def crawl_publication_page(crawl_info_id, publication_id):

    crawl_info = CrawlInfo.objects.get(id=crawl_info_id)
    if crawl_info.successful_crawls >= crawl_info.limit:
        return

    if os.path.isfile('managed_data/crawled_publications/%d/%d.json' % (crawl_info.id, publication_id)):
        crawl_info.queue_size -= 1
        crawl_info.save()
        pprint("SKIP: publication with id `%d` has been fetched before." % publication_id)
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

    if os.path.isfile('managed_data/crawled_publications/%d/%d.json' % (crawl_info.id, publication_id)):
        crawl_info.queue_size -= 1
        crawl_info.save()
        pprint("SKIP: publication with id `%d` has been fetched before." % publication_id)
        return

    with open('managed_data/crawled_publications/%d/%d.json' % (crawl_info.id, publication_id), 'w') as outfile:
        json.dump(publication_data, outfile)
    crawl_info.successful_crawls = len(os.listdir("managed_data/crawled_publications/%d" % crawl_info.id))
    crawl_info.save()

    pprint("%d: publication with id `%d` successfully fetched." % (crawl_info.successful_crawls, publication_id))

    crawl_info = CrawlInfo.objects.get(id=crawl_info_id)
    if crawl_info.queue_size > crawl_info.limit * 5:
        return

    crawl_info.queue_size += len(publication_data.get('references')[:crawl_info.i_limit])
    crawl_info.queue_size += len(publication_data.get('citations')[:crawl_info.o_limit])
    crawl_info.save()

    for reference in publication_data.get('references')[:crawl_info.i_limit]:
        crawl_publication_page.delay(crawl_info_id, reference)
    for citation in publication_data.get('citations')[:crawl_info.o_limit]:
        crawl_publication_page.delay(crawl_info_id, citation)


@shared_task
def start_crawl(crawl_info_id, max_publication_link):

    crawl_info = CrawlInfo.objects.get(id=crawl_info_id)

    publication_ids = InformationParser.extract_publication_ids_in_a_page(crawl_info.init_url)
    print(crawl_info.init_url)
    publication_ids = publication_ids[:max_publication_link]
    for publication_id in publication_ids:
        crawl_publication_page.delay(crawl_info_id, publication_id)


@shared_task
def crawl_author_pages(crawl_info_id, author_id):

    crawl_info = CrawlInfo.objects.get(id=crawl_info_id)
    if crawl_info.successful_crawls >= crawl_info.limit:
        return

    if os.path.isfile('managed_data/crawled_authors/%d/%d.json' % (crawl_info.id, author_id)):
        crawl_info.queue_size -= 1
        crawl_info.save()
        pprint("SKIP: author with id `%d` has been fetched before." % author_id)
        return

    try:
        author_data = InformationParser.get_author_info(author_id)
    except Exception as e:
        print(e)
        print("Author id = `%d`" % author_id)
        crawl_info = CrawlInfo.objects.get(id=crawl_info_id)
        crawl_info.queue_size -= 1
        crawl_info.save()
        return

    crawl_info = CrawlInfo.objects.get(id=crawl_info_id)
    if crawl_info.successful_crawls >= crawl_info.limit:
        return

    if os.path.isfile('managed_data/crawled_authors/%d/%d.json' % (crawl_info.id, author_id)):
        crawl_info.queue_size -= 1
        crawl_info.save()
        pprint("SKIP: author with id `%d` has been fetched before." % author_id)
        return

    with open('managed_data/crawled_authors/%d/%d.json' % (crawl_info.id, author_id), 'w') as outfile:
        json.dump(author_data, outfile)
    crawl_info.successful_crawls = len(os.listdir("managed_data/crawled_authors/%d" % crawl_info.id))
    crawl_info.save()

    pprint("%d: author with id `%d` successfully fetched." % (crawl_info.successful_crawls, author_id))

    crawl_info = CrawlInfo.objects.get(id=crawl_info_id)
    if crawl_info.queue_size > crawl_info.limit * 5:
        return

    crawl_info.queue_size += len(author_data.get('co_authors')[:crawl_info.o_limit])
    crawl_info.save()

    for co_author_id in author_data.get('co_authors')[:crawl_info.o_limit]:
        crawl_author_pages.delay(crawl_info.id, co_author_id)


print("New HTTP Connection Created :D")
InformationDownloader.request_session = requests.session()
