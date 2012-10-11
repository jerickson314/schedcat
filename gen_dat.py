#!/usr/bin/env python

from __future__ import division

from schedcat.overheads.model import Overheads, CacheDelay

from schedcat.model.serialize import load
from schedcat.model.tasks import SporadicTask, TaskSystem

from schedcat.sched.split_heuristic import compute_splits

from schedcat.mapping.rollback import Bin, MaxSpareCapacity, WorstFit

from gen_ts import generate_tasksets

import sys
import os
import re

ohead_root = "/playpen/jerickso/bbbdiss/ohead-data/diss/"

class Scheduler:
    def __init__(self, name, cluster_size, num_clusters, dedicated_irq,
                 cache_level):
        self.name = name
        self.oh_file = ohead_root + "oh_host=ludwig_scheduler={0}_stat=avg.new.csv".format(name)
        self.pmo_file = ohead_root + "pmo_host=ludwig_background=load_stat=avg.csv"
        self.cluster_size = cluster_size
        self.num_clusters = num_clusters
        self.dedicated_irq = dedicated_irq
        self.cache_level = cache_level

class TestTaskSystem:
    def __init__(self, file_name):
        self.file_name = file_name
        items = file_name.split('_')
        self.util_dist = items[1]
        self.period_dist = items[2]
        self.util_cap = float(items[3])
        self.test_num = int(items[4])

    def get_task_system(self):
        return load(self.file_name)

class DataCollector:
    def __init__(self):
        self.improvement_numerators = {}
        self.improvement_denominators = {}
        self.raw_nonsplit_numerators = {}
        self.raw_split_numerators = {}

    def get_sub_hash(self, parent_hash, set_name):
        if set_name not in parent_hash:
            parent_hash[set_name] = {}
        return parent_hash[set_name]

    def add_to_entry(self, parent_hash, set_name, wss, value):
        wss_map = self.get_sub_hash(parent_hash, set_name)
        if wss not in wss_map:
            wss_map[wss] = 0.0
        wss_map[wss] += value

    def report_data_point(self, scheduler, task_system, wss, nonsplit_maxtard,
                          split_maxtard):
        sched_name = scheduler.name + "_" + task_system.util_dist + "_" \
                     + task_system.period_dist + "_" + str(task_system.util_cap)
        # Ignore any situation where there was already no tardiness.
        if (nonsplit_maxtard > 0.0):
            self.add_to_entry(self.raw_nonsplit_numerators, sched_name, wss,
                              nonsplit_maxtard)
            self.add_to_entry(self.raw_split_numerators, sched_name, wss,
                              split_maxtard)
            improvement = (nonsplit_maxtard - split_maxtard) / nonsplit_maxtard
            # known_schedulers is a set, so each will appear only once.
            self.add_to_entry(self.improvement_numerators, sched_name, wss,
                              improvement)
            self.add_to_entry(self.improvement_denominators,
                                          sched_name, wss, 1.0)

    def get_graph_points(self, set_name):
        points = []
        for wss in self.get_sub_hash(self.improvement_numerators, set_name):
            denominator = self.get_sub_hash(self.improvement_denominators,
                                            set_name)[wss]
            improvement_num = self.get_sub_hash(self.improvement_numerators,
                                               set_name)[wss]
            raw_nonsplit_num = self.get_sub_hash(self.raw_nonsplit_numerators,
                                                 set_name)[wss]
            raw_split_num = self.get_sub_hash(self.raw_split_numerators,
                                              set_name)[wss]
            points.append((wss, improvement_num / denominator,
                           raw_nonsplit_num / denominator,
                           raw_split_num / denominator,
                           denominator))
        return sorted(points, key=lambda t: t[0])

    def get_all_graph_points(self):
        to_ret = {}
        for set_name in self.improvement_numerators:
            to_ret[set_name] = self.get_graph_points(set_name)
        return to_ret

def get_ludwig_schedulers():
    return [Scheduler("C-EDF-L2", 2, 12, False, "L2"),
            Scheduler("C-EDF-L2-RM", 2, 12, True, "L2"),
            Scheduler("C-EDF-L3", 6, 4, False, "L3"),
            Scheduler("C-EDF-L3-RM", 6, 4, True, "L3")]

def get_wss_list():
    return [4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 3072, 4096, 8192, 12288]

def get_task_systems(util_dist, period_dist, util_cap):
    file_names = generate_tasksets(util_dist, period_dist, util_cap)
    return [TestTaskSystem(file_name)
            for file_name in file_names]

# Taken from Bjoern's dissertation
def partition_tasks(heur_func, cluster_size, clusters, dedicated_irq, taskset):
    first_cap = cluster_size - 1 if dedicated_irq else cluster_size
    first_bin = Bin(size=SporadicTask.utilization, capacity=first_cap)
    other_bins = [Bin(size=SporadicTask.utilization, capacity=first_cap) for _ in xrange(1, clusters)]
    
    heuristic = heur_func(initial_bins=[first_bin] + other_bins)

    taskset.sort(key=SporadicTask.utilization, reverse=True)

    heuristic.binpack(taskset)
    
    if not (heuristic.misfits):
        parts = [TaskSystem(b.items) for b in heuristic.bins]
        for i, p in enumerate(parts):
            if i == 0 and dedicated_irq:
                p.cpus = cluster_size - 1
            else:
                p.cpus = cluster_size
        return [p for p in parts if len(p) > 0]
    else:
        return False

def process_task_systems(task_system_list, scheduler_list):
    wss_list = get_wss_list()

    for scheduler in scheduler_list:
        reporter = DataCollector()
        oh = Overheads.from_file(scheduler.oh_file)
        oh.initial_cache_loss = CacheDelay.from_file(scheduler.pmo_file).__dict__[scheduler.cache_level]
        oh.cache_affinity_loss = CacheDelay.from_file(scheduler.pmo_file).__dict__[scheduler.cache_level]
        for task_system_obj in task_system_list:
            print task_system_obj.file_name
            task_system = task_system_obj.get_task_system()
            for wss in wss_list:
                for task in task_system:
                    task.wss = wss
                #partitions = partition_tasks(MaxSpareCapacity,
                partitions = partition_tasks(WorstFit,
                                             scheduler.cluster_size,
                                             scheduler.num_clusters,
                                             scheduler.dedicated_irq,
                                             task_system)
                if partitions:
                    max_base_tardiness = float("-inf")
                    max_split_tardiness = float("-inf")
                    for cluster_tasks in partitions:
                        results = compute_splits(oh, scheduler.cluster_size,
                                                 cluster_tasks,
                                                 scheduler.dedicated_irq)
                        if results is not None:
                            max_base_tardiness = max(max_base_tardiness,
                                                     results.base_lateness)
                            max_split_tardiness = max(max_split_tardiness,
                                                      results.best_lateness)
                        else:
                            max_base_tardiness = float("inf")
                            max_split_tardiness = float("inf")
                    # Only report systems that are schedulable in the first place
                    if (max_base_tardiness < float("inf")):
                        reporter.report_data_point(scheduler, task_system_obj, wss,
                                                   max_base_tardiness,
                                                   max_split_tardiness)


        data = reporter.get_all_graph_points()
        for sched_name in data:
            print "Doing " + sched_name
            outfile = open('results/' + sched_name, 'w')
            for point in data[sched_name]:
                outfile.write("{0}\t{1}\t{2}\t{3}\t{4}\n".format(point[0], point[1], point[2], point[3], point[4]))
            outfile.close()

task_systems = get_task_systems(sys.argv[1], sys.argv[2], float(sys.argv[3]))
#scheduler_list = [get_ludwig_schedulers()[int(sys.argv[4])]]
scheduler_list = get_ludwig_schedulers()
process_task_systems(task_systems, scheduler_list)
