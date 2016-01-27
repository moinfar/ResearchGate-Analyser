from django.core.management.base import BaseCommand, CommandError
from crawler.tasks import get_article_data


class Command(BaseCommand):
    help = 'Test!'

    def add_arguments(self, parser):
        parser.add_argument('url', nargs='+', type=str)

    def handle(self, *args, **options):
        print(get_article_data.delay(279633530))