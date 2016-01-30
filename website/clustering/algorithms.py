import os
import json
import numpy
import heapq
import random
from math import sqrt

from pprint import pprint


class Mapper:
    def __init__(self):
        self.uid_to_sid = {}
        self.sid_to_uid = {}
        self.last_index = -1

    def create_sid(self, uid):
        uid = int(uid)
        self.last_index += 1
        self.uid_to_sid[uid] = self.last_index
        self.sid_to_uid[self.last_index] = uid

    def get_sid(self, uid):
        uid = int(uid)
        return self.uid_to_sid[uid]

    def get_uid(self, sid):
        sid = int(sid)
        return self.sid_to_uid[sid]

    def knows_uid(self, uid):
        uid = int(uid)
        return self.uid_to_sid.has_key(uid)

    def size(self):
        return self.last_index + 1


class AverageLinkClustering:
    def __init__(self, distance_matrix):
        self.N = distance_matrix.shape[0]
        self.base_distances = distance_matrix

    def av_link_set_and_sum(self, sets_info, a, b):
        (_, _, sum_link_a, set_a) = sets_info[a]
        (_, _, sum_link_b, set_b) = sets_info[b]

        new_sum = sum_link_a + sum_link_b + sum([self.base_distances[ax][bx] for ax in set_a for bx in set_b])
        return set_a.union(set_b), new_sum

    def cluster(self, max_cluster_size):
        sets_info = []
        set_distances = []

        for i in range(self.N):
            for j in range(self.N):
                if i < j:
                    distance_info = (self.base_distances[i][j], (i, j))
                    heapq.heappush(set_distances, distance_info)

            sets_info.insert(i, [0, 0, 0, set([i])])  # [valid_until, average, sum [link inside set], set]

        max_gap, step_of_max_gap = 0, 0
        previous_average = 0
        step = 0

        while set_distances:
            (min_distance, (a, b)) = heapq.heappop(set_distances)

            if sets_info[a][0] > 0:
                continue
            if sets_info[b][0] > 0:
                continue

            step += 1

            (_, _, sum_link_a, set_a), sets_info[a][0] = sets_info[a], step
            (_, _, sum_link_b, set_b), sets_info[b][0] = sets_info[b], step

            new_index = self.N + step - 1
            new_set, new_sum = self.av_link_set_and_sum(sets_info, a, b)
            new_average = 2 * new_sum / (len(new_set) * (len(new_set) - 1))
            sets_info.insert(new_index, [0, new_average, new_sum, new_set])

            # print(step, max_gap, new_average - previous_average, new_average, set_a, set_b, max_cluster_size)

            if max_gap < new_average - previous_average and (self.N - step) < max_cluster_size:
                max_gap = new_average - previous_average
                step_of_max_gap = step

            previous_average = new_average

            for c in range(len(sets_info) - 1):
                if sets_info[c][0] > 0 and c != new_index:
                    continue

                (_, _, sum_link_c, set_c) = sets_info[c]
                set_with_c, sum_with_c = self.av_link_set_and_sum(sets_info, c, new_index)
                average_with_c = 2 * sum_with_c / (len(set_with_c) * (len(set_with_c) - 1))
                distance_info = (average_with_c, (c, new_index))
                # print(distance_info)
                heapq.heappush(set_distances, distance_info)

        cluster_mapper = Mapper()
        cluster_map = {}
        clusters = []
        for i in range(self.N + step_of_max_gap - 1):
            if sets_info[i][0] >= step_of_max_gap:
                cluster_mapper.create_sid(i)
                for doc_id in sets_info[i][3]:
                    cluster_map[doc_id] = cluster_mapper.get_sid(i)
                clusters.append(sets_info[i][3])

        return clusters, cluster_map


class KMeans:
    @staticmethod
    def inner_product(a, b):
        if len(a) > len(b):
            return KMeans.inner_product(b, a)

        r = 0
        for key in a:
            if key in b:
                r += a[key] * b[key]
        return r

    @staticmethod
    def dist(a, b):
        r = 0
        for key in a:
            if key in b:
                r += (a[key] - b[key]) * (a[key] - b[key])
            else:
                r += a[key] * a[key]
        for key in b:
            if key not in a:
                r += b[key] * b[key]
        return r

    @staticmethod
    def compute_means(dataset, k, dci, thrsh=1):        # dci is a DocumentClusteringInfo
        dci.k = k
        dci.iter = 0
        dci.save()

        # means = [{} for i in range(k)]
        # for data in dataset:
        #     for term in data.tf:
        #         for i in range(k):
        #             means[i][term] = random.randint(0, 4)
        means = [doc_inf.tf.copy() for doc_inf in random.sample(dataset, k)]
        old_means = [{} for i in range(k)]

        cost = float("inf")
        while True:
            dci.iter += 1
            dci.save()
            old_cost = cost
            cost = 0
            cluster_count = [0]*k

            print('^^^^^^^^^^^^^^^^^^^^^')
            print('iteration {}:'.format(dci.iter))

            for data in dataset:
                closest_dist = float("inf")
                data.cluster_id = -1
                for i in range(0, k):
                    d = KMeans.dist(means[i], data.tf)
                    if d < closest_dist:
                        closest_dist = d
                        data.cluster_id = i
                cluster_count[data.cluster_id] += 1
                cost += sqrt(closest_dist)
            dci.cost = cost
            dci.save()

            cluster_sum = [{} for i in range(k)]
            for data in dataset:
                for key in data.tf:
                    if key not in cluster_sum[data.cluster_id]:
                        cluster_sum[data.cluster_id][key] = data.tf[key]*1.0 / cluster_count[data.cluster_id]
                    else:
                        cluster_sum[data.cluster_id][key] += data.tf[key]*1.0 / cluster_count[data.cluster_id]

            if old_cost - cost < thrsh:
                break

            for i in range(k):
                print("Cluster {}:\t{}".format(i, cluster_count[i]))
                old_means[i] = means[i].copy()
                means[i] = cluster_sum[i]
            print(cost)

            for i in range(k):
                if cluster_count[i] < len(dataset) / 10.0 / k and dci.iter < 15:
                    means = [doc_inf.tf.copy() for doc_inf in random.sample(dataset, k)]
                    cost = float("inf")
                    break

        return old_means, old_cost
