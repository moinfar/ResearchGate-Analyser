from django.core.management.base import BaseCommand, CommandError
from celery.task.control import discard_all


class Command(BaseCommand):
    help = 'Discards all crawl jobs.'

    def add_arguments(self, parser):
        pass

    def handle(self, *args, **options):
        discard_all()
