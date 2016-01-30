import os
import json
import numpy
import heapq

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






