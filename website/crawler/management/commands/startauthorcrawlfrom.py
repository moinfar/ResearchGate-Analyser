import os

from django.core.management.base import BaseCommand, CommandError
from crawler.tasks import InformationDownloader
from crawler.tasks import crawl_author_pages
from crawler.models import CrawlInfo


class Command(BaseCommand):
    help = 'Fetch a page and crawl from `N` articles inside it.'

    def add_arguments(self, parser):
        parser.add_argument('url', nargs=1, type=str)
        parser.add_argument('branch_factor', nargs=1, type=int)
        parser.add_argument('--limit', default=1000, help='crawling will finish after limit exceeds')

    def handle(self, *args, **options):
        crawl_info = CrawlInfo(init_url=options['url'][0], limit=options['limit'],
                               type="author", i_limit=0, o_limit=options['branch_factor'][0])
        crawl_info.save()

        if not os.path.exists("managed_data/crawled_authors/%d" % crawl_info.id):
            os.makedirs("managed_data/crawled_authors/%d" % crawl_info.id)

        author_id = InformationDownloader.get_researcher_id_from_url(crawl_info.init_url)
        crawl_author_pages.delay(crawl_info.id, author_id)
