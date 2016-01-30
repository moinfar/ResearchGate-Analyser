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



mapper = Mapper()
authors = {}

base_dir = '../managed_data/crawled_authors/2'
author_files = os.listdir(base_dir)
for author_file in author_files:
    mapper.create_sid(int(author_file.split(".")[0]))
    with open("%s/%s" % (base_dir, author_file), 'r') as infile:
        author = json.load(infile)
        authors[author.get('id')] = author

N = mapper.size()
sets_info = []
distance = numpy.zeros(shape=(N, N))
set_distances = []

for author_sid_1 in range(N):
    author_uid_1 = mapper.get_uid(author_sid_1)
    for author_sid_2 in range(N):
        author_uid_2 = mapper.get_uid(author_sid_2)
        co_authored_publications = set(authors[author_uid_1].get('publications')). \
            intersection(set(authors[author_uid_2].get('publications')))
        distance[author_sid_1][author_sid_2] = 1.0 / (1 + 5 * len(co_authored_publications))
        if author_sid_1 < author_sid_2:
            distance_info = (distance[author_sid_1][author_sid_2], (author_sid_1, author_sid_2))
            heapq.heappush(set_distances, distance_info)

    sets_info.insert(author_sid_1, [0, 0, 0, set([author_sid_1])])  # (valid_until, average, sum [link inside set], set)

max_gap = 0
step_of_max_gap = 0
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

    new_index = N + step - 1
    new_set = set_a.union(set_b)
    new_sum = sum_link_a + sum_link_b + sum([distance[ax][bx] for ax in set_a for bx in set_b])
    new_average = 2 * new_sum / (len(new_set) * (len(new_set) - 1))

    if max_gap < new_average - previous_average and (N - step) < N**0.5*3:
        max_gap = new_average - previous_average
        step_of_max_gap = step

    print(max_gap, new_average - previous_average, new_average, set_a, set_b, N-step, N**0.5*3)
    previous_average = new_average

    for c in range(len(sets_info)):
        if sets_info[c][0] > 0:
            continue
        (_, _, sum_link_c, set_c) = sets_info[c]
        sum_with_c = sum_link_c + new_sum + sum([distance[x][cx] for x in new_set for cx in set_c])
        size_with_c = len(new_set) + len(set_c)
        average_with_c = 2 * sum_with_c / (size_with_c * (size_with_c - 1))
        distance_info = (average_with_c, (c, new_index))
        heapq.heappush(set_distances, distance_info)

    sets_info.insert(new_index, [0, new_average, new_sum, new_set])

for i in range(N + step_of_max_gap - 1):
    if sets_info[i][0] >= step_of_max_gap:
        print(i, ">>>", sets_info[i])
        # current_set = set([mapper.get_uid(x) for x in sets_info[i][3]])
        # print(current_set)

# print(sets_info[len(sets_info)-1])

