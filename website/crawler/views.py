import os
import json

from django.shortcuts import render
from django.http import HttpResponse
from django.shortcuts import redirect
from crawler.models import CrawlInfo
from crawler.tasks import InformationDownloader, start_crawl, crawl_publication_page, crawl_author_pages


def crawl_page(request):
    if request.GET.get('urls') is not None:
        urls = request.GET.get('urls').split("\n")
        crawl_info = CrawlInfo(init_url=request.GET.get('urls'), limit=request.GET.get('limit'),
                               i_limit=request.GET.get('in_degree_limit'), o_limit=request.GET.get('out_degree_limit'))
        crawl_info.save()

        if not os.path.exists("managed_data/crawled_publications/%d" % crawl_info.id):
            os.makedirs("managed_data/crawled_publications/%d" % crawl_info.id)

        for url in urls:
            if "/publication/" in url:
                crawl_publication_page.delay(crawl_info.id, InformationDownloader.get_publication_id_from_url(url))
            else:
                start_crawl.delay(crawl_info.id, int(request.GET.get('out_degree_limit')))

        return redirect("/crawl/status/%d/" % crawl_info.id)

    return render(request, 'crawl.html')


def crawl_status_page(request, id):
    crawl_info = CrawlInfo.objects.get(id=id)
    crawled_pages_num = crawl_info.successful_crawls

    if request.GET.get('type', 'HTML') == 'JSON':
        result = json.dumps({'status': 'OK', 'percent': max(1, int(100*crawled_pages_num/crawl_info.limit))},
                            ensure_ascii=False)
        return HttpResponse(result, content_type='application/json; charset=utf-8')

    return render(request, 'crawl_status.html', {'percent': max(1, int(100*crawled_pages_num/crawl_info.limit))})


def crawl_author_page(request):
    if request.GET.get('urls') is not None:
        urls = request.GET.get('urls').split("\n")
        crawl_info = CrawlInfo(init_url=request.GET.get('urls'), limit=request.GET.get('limit'),
                               i_limit=0, o_limit=request.GET.get('branch_factor'), type='author')
        crawl_info.save()

        if not os.path.exists("managed_data/crawled_authors/%d" % crawl_info.id):
            os.makedirs("managed_data/crawled_authors/%d" % crawl_info.id)

        for url in urls:
            author_id = InformationDownloader.get_researcher_id_from_url(url)
            crawl_author_pages.delay(crawl_info.id, author_id)

        return redirect("/crawl/status/%d/" % crawl_info.id)

    return render(request, 'crawl_authors.html')