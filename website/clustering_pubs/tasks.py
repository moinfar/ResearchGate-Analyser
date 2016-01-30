from __future__ import absolute_import
from math import log
from celery import shared_task
from elasticsearch import Elasticsearch
from stemming.porter2 import stem
from clustering_pubs.models import DocClusteringInfo
from clustering.algorithms import KMeans


class DocumentInfo:
    def __init__(self, document_id):
        self.doc_id = document_id
        self.cluster_id = -1
        self.tf = {}


@shared_task
def cluster_index(index_name, k=-1):
    dci = DocClusteringInfo.objects.get(index_name=index_name)

    dci.status = 'Retrieving Documents'
    dataset = retrieve_dataset(index_name, dci.doc_type)
    dci.save()

    dci.status = 'Clustering Data'
    if k < 2:
        find_clusters(list(dataset.values()), dci)
    else:
        KMeans.compute_means(list(dataset.values()), k, dci)
    dci.save()

    dci.status = 'Labeling Clusters'
    labels = label_clusters(index_name, dci.doc_type, list(dataset.values()), k)
    dci.save()

    dci.status = 'Updating Index'
    update_index(index_name, dci.doc_type, dataset, labels)
    dci.save()

    dci.status = 'Idle'
    dci.save()


def retrieve_dataset(index_name, doc_type, weight={'title': 5, 'abstract': 1}):
    es = Elasticsearch()
    results = es.search(index=index_name, doc_type=doc_type, size=10000)['hits']['hits']
    dataset = {}
    for res in results:
        doc = DocumentInfo(res['_id'])
        term_vectors = es.termvectors(index=index_name, doc_type=doc_type, id=res['_id'], offsets=False,
                                      payloads=False, positions=False, fields='title,abstract',
                                      field_statistics=False)['term_vectors']
        for zone in {'abstract', 'title'}:
            term_vector = term_vectors[zone]['terms']
            for term in term_vector:
                stemmed = stem(term)
                if stemmed.isalpha():
                    if stemmed not in doc.tf:
                        doc.tf[stemmed] = term_vector[term]['term_freq'] * weight[zone]
                    else:
                        doc.tf[stemmed] += term_vector[term]['term_freq'] * weight[zone]
        dataset[res['_id']] = doc
    return dataset


def find_clusters(dataset, dci, C=100):  # dci is a DocumentClusteringInfo
    k = 3
    best_k = 3
    cost = float("inf")
    while True:
        k += 1
        old_cost = cost
        means, d = KMeans.compute_means(dataset, k, dci)
        cost = k*C + d
        print(old_cost)
        print(cost)
        print(k)
        print(dci.iter)
        print('$')
        if old_cost > cost:
            best_k = k
        if k - best_k > 2:
            break

    return KMeans.compute_means(dataset, best_k)


def label_clusters(index_name, doc_type, dataset, k, label_length=3):
    labels = ['']*k
    best_mi = [0]*k
    cluster_tf = [{} for i in range(k)]
    cluster_doc_count = [0]*k
    cluster_term_count = [0]*k
    total_term_count = 0
    total_tf = {}
    for data in dataset:
        cluster_doc_count[data.cluster_id] += 1
        for term in data.tf:
            total_term_count += data.tf[term]
            cluster_term_count[data.cluster_id] += data.tf[term]
            if term not in cluster_tf[data.cluster_id]:
                cluster_tf[data.cluster_id][term] = data.tf[term]
            else:
                cluster_tf[data.cluster_id][term] += data.tf[term]
            if term not in total_tf:
                total_tf[term] = data.tf[term]
            else:
                total_tf[term] += data.tf[term]

    mi = [{} for i in range(k)]
    for cid in range(k):     # cluster id
        for term in cluster_tf[cid]:
            if (total_tf[term] - cluster_tf[cid][term]) == 0:
                if total_tf[term] < 10:
                    mi[cid][term] = -1000
                else:
                    mi[cid][term] = 1000
            elif (cluster_term_count[cid] - cluster_tf[cid][term]) == 0:
                mi[cid][term] = 1001
            elif (total_term_count - cluster_term_count[cid] - total_tf[term] + cluster_tf[cid][term]) == 0:
                mi[cid][term] = -1001
            else:
                mi[cid][term] = log(cluster_tf[cid][term]*1.0
                                    / cluster_term_count[cid]
                                    / total_tf[term])\
                                + log((total_tf[term] - cluster_tf[cid][term])*1.0
                                      / (total_term_count - cluster_term_count[cid])
                                      / total_tf[term])\
                                + log((cluster_term_count[cid] - cluster_tf[cid][term])*1.0
                                      / cluster_term_count[cid]
                                      / (total_term_count - total_tf[term]))\
                                + log((total_term_count - cluster_term_count[cid] - total_tf[term] + cluster_tf[cid][term])*1.0
                                      / (total_term_count - cluster_term_count[cid])
                                      / (total_term_count - total_tf[term]))
                if total_tf[term] < 10:
                    mi[cid][term] -= 10
        best_mi[cid] = sorted(mi[cid].keys(), key=mi[cid].get, reverse=True)[:label_length]

    es = Elasticsearch()
    lbls = [['']*label_length for i in range(k)]
    for zone in {'title', 'abstract'}:
        for data in dataset:
            cid = data.cluster_id
            term_vectors = es.termvectors(index=index_name, doc_type=doc_type, id=data.doc_id, offsets=False,
                                          payloads=False, positions=False, fields=zone,
                                          field_statistics=False)['term_vectors']
            term_vector = term_vectors[zone]['terms']
            for term in term_vector:
                for i in range(label_length):
                    if lbls[cid][i] == '':
                        if stem(term) == best_mi[cid][i]:
                            lbls[cid][i] = term
    for cid in range(k):
        labels[cid] = ', '.join(lbls[cid])

    return labels


def update_index(index_name, doc_type, dataset, labels):
    es = Elasticsearch()
    for doc_id in dataset:
        data = dataset[doc_id]
        es.update(index_name, doc_type, doc_id, body={'doc': {'cluster_id': data.cluster_id,
                                                              'cluster_label': labels[data.cluster_id]}})
        es.update('global-index', doc_type, doc_id, body={'doc': {'cluster_id': data.cluster_id,
                                                                  'cluster_label': labels[data.cluster_id]}})
