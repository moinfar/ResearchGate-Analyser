from django.core.management.base import BaseCommand, CommandError
from crawler.tasks import start_crawl
from crawler.models import CrawlInfo


class Command(BaseCommand):
    help = 'Fetch a page and crawl from `N` articles inside it.'

    def add_arguments(self, parser):
        parser.add_argument('url', nargs=1, type=str)
        parser.add_argument('N', nargs=1, type=int)
        parser.add_argument('--limit', default=1000, help='crawling will finish after limit exceeds')

    def handle(self, *args, **options):
        crawl_info = CrawlInfo(init_url=options['url'][0], limit=options['limit'])
        crawl_info.save()
        start_crawl.delay(crawl_info.id, options['N'][0])
