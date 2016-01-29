import os
import json

from django.core.management.base import BaseCommand, CommandError
from search.tasks import index_fetched_publication


class Command(BaseCommand):
    help = 'Index crawled pages in a given directory.'

    def add_arguments(self, parser):
        parser.add_argument('index', nargs=1, type=str)
        parser.add_argument('path', nargs=1, type=str)

    def handle(self, *args, **options):
        pages = os.listdir(options['path'][0])

        for page in pages:
            index_fetched_publication.delay("index-%s" % options['index'][0], "%s/%s" % (options['path'][0], page))
