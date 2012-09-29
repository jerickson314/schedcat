#!/usr/bin/env python
from __future__ import division

from schedcat.model.tasks import TaskSystem
from schedcat.model.serialize import write
from schedcat.generator.tasksets import make_standard_dists
from schedcat.util.time import ms2us

CACHE_SIZE_CLUSTERS = { 'L2' : 2, 'L3' : 6}

distributions = make_standard_dists()

for period_name in distributions:
    by_util = distributions[period_name]
    for util_name in by_util:
#        for cache_name in CACHE_SIZE_CLUSTERS:
#            cluster_size = CACHE_SIZE_CLUSTERS[cache_name]
            cluster_size = 24
            for cap in [cluster_size / 20 * i for i in range(1, 21)]:
                for i in range(1000):
#                    task_list = []
#                    for partition in range(int(24/cluster_size)): 
                    clust = by_util[util_name](max_util=cap,
                                                   time_conversion=ms2us)
#                        for task in clust:
#                            task.partition = partition
#                            task_list.append(task)
#                    ts = TaskSystem(task_list)
                    print "Generating {0} {1} {2} {3}".format(period_name,
                            util_name, cap, i)
                    filename = "/playpen/jerickso/tasksets/taskset_{0}_{1}_{2}_{3}".format(
                               period_name, util_name, cap, i)
                    write(clust, filename)
