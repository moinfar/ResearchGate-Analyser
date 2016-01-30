from django.db import models


class CrawlInfo(models.Model):
    start = models.DateTimeField(verbose_name='timestamp', auto_now=True)
    init_url = models.CharField(max_length=1024, verbose_name='initial url')
    limit = models.IntegerField(verbose_name='limit')
    i_limit = models.IntegerField(verbose_name='input degree limit')
    o_limit = models.IntegerField(verbose_name='output degree limit')
    successful_crawls = models.IntegerField(verbose_name='successful crawls', default=0)
    queue_size = models.IntegerField(verbose_name='queue size', default=0)
    type = models.CharField(max_length=64, default='publication')

    class Meta:
        verbose_name = 'crawl info'
        verbose_name_plural = 'crawl info'


class DocInfo(models.Model):
    current_crawl_info = models.ForeignKey(CrawlInfo, null=False, verbose_name='current crawl info')
    doc_id = models.IntegerField(verbose_name='document ID')
    json_info = models.TextField(verbose_name='JSON ID')

    class Meta:
        verbose_name = 'document info'
        verbose_name_plural = 'document info'

