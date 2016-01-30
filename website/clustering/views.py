import numpy

from django.shortcuts import render
from elasticsearch import Elasticsearch
from clustering.algorithms import Mapper, AverageLinkClustering


def author_clustering_result(request):
    es = Elasticsearch()

    if request.GET.get('index_id') is not None and request.GET.get('index_id') != '':
        index_id = request.GET.get('index_id')

        authors = es.search(index_id, 'author', body={"size": 10000, "query": {"match_all": {}}})['hits']['hits']
        authors = {int(author.get('_id')): author.get('_source') for author in authors}

        mapper = Mapper()
        for author in authors:
            mapper.create_sid(author)

        N = mapper.size()
        distance = numpy.zeros(shape=(N, N))

        nodes = []
        edges = []

        for author_sid_1 in range(N):
            author_uid_1 = mapper.get_uid(author_sid_1)
            nodes.append(author_uid_1)
            for author_sid_2 in range(N):
                author_uid_2 = mapper.get_uid(author_sid_2)
                co_authored_publications = set(authors[author_uid_1].get('publications')). \
                    intersection(set(authors[author_uid_2].get('publications')))
                if author_sid_1 < author_sid_2:
                    for i in range(len(co_authored_publications)):
                        edges.append({'from': author_uid_1, 'to': author_uid_2})
                distance[author_sid_1][author_sid_2] = 1.0 / (1 + 5 * len(co_authored_publications))

        avc = AverageLinkClustering(distance)
        clusters, cluster_map = avc.cluster(N**0.6*2)

        uid_clusters = []
        uid_cluster_map = {}
        for cluster in clusters:
            uid_clusters.append(set([mapper.get_uid(x) for x in cluster]))
        for sid in cluster_map:
            uid_cluster_map[mapper.get_uid(sid)] = cluster_map[sid]

        # print(uid_clusters, uid_cluster_map)
        # print(nodes, edges)

        return render(request, 'author_clustering_result.html',
                      {'graph': {'nodes': nodes, 'edges': edges},
                       'cluster_map': uid_cluster_map, 'clusters': uid_clusters})

    indexes = es.indices.get_mapping()
    return render(request, 'author_clustering_result.html', {'indexes': indexes})
