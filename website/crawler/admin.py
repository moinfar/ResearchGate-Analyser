from django.contrib import admin
from crawler.models import CrawlInfo, DocInfo

admin.site.register(CrawlInfo)
admin.site.register(DocInfo)
