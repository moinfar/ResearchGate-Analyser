from django.shortcuts import redirect, render, HttpResponse
from clustering_pubs.models import DocClusteringInfo
from crawler.models import CrawlInfo
import clustering_pubs.tasks
import json


def clustering_pubs_page(request):
    if request.GET.get('crawl_id') is not None and request.GET.get('crawl_id') != '':
        crawl_info = CrawlInfo.objects.get(id=request.GET.get('crawl_id'))
        dci = DocClusteringInfo()
        dci.doc_type = "publication"
        dci.cost = -1
        dci.iter = -1
        dci.k = -1
        dci.index_name = crawl_info.index_name
        dci.save()
        clustering_pubs.tasks.cluster_index.delay(dci.index_name)
        return redirect("/clustering_pubs/status/%s/" % dci.index_name)

    crawls_info = CrawlInfo.objects.filter(type="publication").exclude(index_name="")
    return render(request, 'clustering_pubs.html', {'crawls_info': crawls_info})


def clustering_pubs_status_page(request, index_name):
    dci = DocClusteringInfo.objects.get(index_name=index_name)
    if request.GET.get('type', 'HTML') == 'JSON':
        result = json.dumps({'status': dci.status, 'k': dci.k, 'iter': dci.iter, 'cost': dci.cost}, ensure_ascii=False)
        return HttpResponse(result, content_type='application/json; charset=utf-8')

    return render(request, 'clustering_pubs_status.html')
