from django.shortcuts import redirect, render, HttpResponse
from clustering_pubs.models import DocClusteringInfo
from crawler.models import CrawlInfo
import clustering_pubs.tasks
import json
from elasticsearch import Elasticsearch


def clustering_pubs_page(request):
    if request.GET.get('index_name') is not None and request.GET.get('index_name') != '':
        dci = DocClusteringInfo()
        dci.doc_type = "publication"
        dci.cost = -1
        dci.iter = -1
        dci.k = -1
        dci.index_name = request.GET.get('index_name')
        dci.save()
        if request.GET.get('k') is not None:
            clustering_pubs.tasks.cluster_index.delay(dci.index_name, k=int(request.GET.get('k')))
        else:
            clustering_pubs.tasks.cluster_index.delay(dci.index_name)
        return redirect("/clustering_pubs/status/%s/" % dci.index_name)

    es = Elasticsearch()
    indexes = es.indices.get_mapping()
    return render(request, 'clustering_pubs.html', {'indexes': indexes})


def clustering_pubs_status_page(request, index_name):
    dci = DocClusteringInfo.objects.get(index_name=index_name)
    if request.GET.get('type', 'HTML') == 'JSON':
        result = json.dumps({'status': dci.status, 'k': dci.k, 'iter': dci.iter, 'cost': dci.cost}, ensure_ascii=False)
        return HttpResponse(result, content_type='application/json; charset=utf-8')

    return render(request, 'clustering_pubs_status.html')
