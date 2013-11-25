#!/usr/bin/env python

from __future__ import division

from schedcat.overheads.model import Overheads, CacheDelay

from schedcat.model.serialize import load
from schedcat.model.tasks import SporadicTask, TaskSystem

from schedcat.sched.split_heuristic import compute_splits_nolock, \
                                           compute_splits_lock

from schedcat.mapping.rollback import Bin, MaxSpareCapacity, WorstFit

from gen_ts import generate_tasksets, generate_lock_tasksets

import sys
import os
import re

ohead_root = "/home/jerickso/ohead-data/"

class Scheduler:
    def __init__(self, name, cluster_size, num_clusters, dedicated_irq,
                 cache_level, lock_type):
        self.name = name
        self.oh_file = ohead_root + "oh_host=ludwig_scheduler={0}_stat=avg.new.csv".format(name)
        self.unsplit_oh_file = ohead_root + "unsplit/oh_host=ludwig_scheduler={0}_stat=avg.new.csv".format(name)
        self.pmo_file = ohead_root + "pmo_host=ludwig_background=load_stat=avg.csv"
        self.cluster_size = cluster_size
        self.num_clusters = num_clusters
        self.dedicated_irq = dedicated_irq
        self.cache_level = cache_level
        self.lock_type = lock_type
        if self.lock_type is not None:
            self.lock_oh_file = ohead_root + "oh_host=ludwig_scheduler={0}_locks={1}_stat=avg.new.csv".format(name, lock_type)
            self.unsplit_lock_oh_file = ohead_root + "unsplit/oh_host=ludwig_scheduler={0}_locks={1}_stat=avg.new.csv".format(name, lock_type)
#            self.syscall_oh_file = ohead_root + "oh_host=ludwig_scheduler={0}_locks=OMLP_stat=avg.new.csv".format(name)
            if self.lock_type is "OMLP":
                self.spinlock = False
            else:
                self.spinlock = True

class TestTaskSystem:
    def __init__(self, file_name):
        self.file_name = file_name
        items = file_name.split('_')
        self.util_dist = items[1]
        self.period_dist = items[2]
        self.util_cap = float(items[3])
        if len(items) > 5:
            self.cslength = items[4]
            self.nres = int(items[5])
            self.pacc = float(items[6])
            self.test_num = int(items[7])
        else:
            self.test_num = int(items[4])

    def get_task_system(self):
        return load(self.file_name)

class DataCollector:
    def __init__(self):
        self.improvement_numerators = {}
        self.improvement_denominators = {}
        self.raw_nonsplit_numerators = {}
        self.raw_split_numerators = {}
        self.ave_splits_numerators = {}
        self.max_splits_numerators = {}

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
                          split_maxtard, ave_splits, max_splits):
        sched_name = scheduler.name + "_" + task_system.util_dist + "_" \
                     + task_system.period_dist + "_" + str(task_system.util_cap)
        if scheduler.lock_type is not None:
            sched_name += "_" + scheduler.lock_type + "_" + \
                          task_system.cslength + "_" + str(task_system.nres) + \
                          "_" + str(task_system.pacc)
        # Ignore any situation where there was already no tardiness.
        if (nonsplit_maxtard > 0.0):
            nonsplit_maxtard = max(0.0, nonsplit_maxtard)
            split_maxtard = max(0.0, split_maxtard)
            self.add_to_entry(self.raw_nonsplit_numerators, sched_name, wss,
                              nonsplit_maxtard)
            self.add_to_entry(self.raw_split_numerators, sched_name, wss,
                              split_maxtard)
            self.add_to_entry(self.ave_splits_numerators, sched_name, wss,
                              ave_splits)
            self.add_to_entry(self.max_splits_numerators, sched_name, wss,
                              max_splits)
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
            ave_splits_num = self.get_sub_hash(self.ave_splits_numerators,
                                               set_name)[wss]
            max_splits_num = self.get_sub_hash(self.max_splits_numerators,
                                               set_name)[wss]
            points.append((wss, improvement_num / denominator,
                           raw_nonsplit_num / denominator,
                           raw_split_num / denominator,
                           denominator,
                           ave_splits_num / denominator,
                           max_splits_num / denominator))
        return sorted(points, key=lambda t: t[0])

    def get_all_graph_points(self):
        to_ret = {}
        for set_name in self.improvement_numerators:
            to_ret[set_name] = self.get_graph_points(set_name)
        return to_ret

def get_ludwig_schedulers():
    return [Scheduler("C-FL-split-L2", 2, 12, False, "L2", None),
            Scheduler("C-FL-split-L2-RM", 2, 12, True, "L2", None),
            Scheduler("C-FL-split-L3", 6, 4, False, "L3", None),
            Scheduler("C-FL-split-L3-RM", 6, 4, True, "L3", None)]

def get_ludwig_lock_schedulers():
    return [Scheduler("C-FL-split-L2-RM", 2, 12, True, "L2", "MX-Q"),
            Scheduler("C-FL-split-L3-RM", 6, 4, True, "L3", "MX-Q")]
#    return [Scheduler("C-FL-split-L2-RM", 2, 12, True, "L2", "OMLP"),
#            Scheduler("C-FL-split-L2-RM", 2, 12, True, "L2", "MX-Q"),
#            Scheduler("C-FL-split-L3-RM", 6, 4, True, "L3", "OMLP"),
#            Scheduler("C-FL-split-L3-RM", 6, 4, True, "L3", "MX-Q")]

def get_wss_list():
#    return [4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048, 3072, 4096, 8192, 12288]
    return [4, 8, 16, 32, 64, 128, 256, 512, 1024, 2048]

def get_lock_wss_list():
    return get_wss_list()
#    return [4, 128]
#%    return [128]

def get_task_systems(util_dist, period_dist, util_cap):
    file_names = generate_tasksets(util_dist, period_dist, util_cap)
    return [TestTaskSystem(file_name)
            for file_name in file_names]

def get_lock_task_systems(util_dist, period_dist, util_cap, cslength, nres,
                          pacc):
    file_names = generate_lock_tasksets(util_dist, period_dist, util_cap,
                                        cslength, nres, pacc)
    return [TestTaskSystem(file_name)
            for file_name in file_names]

# Taken from Bjoern's dissertation
def partition_tasks(heur_func, cluster_size, clusters, dedicated_irq, taskset):
    first_cap = cluster_size - 1 if dedicated_irq else cluster_size
    first_bin = Bin(size=SporadicTask.utilization, capacity=first_cap)
    other_bins = [Bin(size=SporadicTask.utilization, capacity=cluster_size) for _ in xrange(1, clusters)]
    
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
            for task in p:
                task.partition = i
        return [p for p in parts if len(p) > 0]
    else:
        return False

def copy_lock_overheads(oh, lock_oh):
    oh.lock = lock_oh.lock
    oh.unlock = lock_oh.unlock
    oh.read_lock = lock_oh.read_lock
    oh.read_unlock = lock_oh.read_unlock
    oh.syscall_in = lock_oh.syscall_in
    oh.syscall_out = lock_oh.syscall_out

def process_task_systems(task_system_list, scheduler_list):

    for scheduler in scheduler_list:
        reporter = DataCollector()
        oh = Overheads.from_file(scheduler.oh_file)
        oh.initial_cache_loss = CacheDelay.from_file(scheduler.pmo_file).__dict__[scheduler.cache_level]
        oh.cache_affinity_loss = CacheDelay.from_file(scheduler.pmo_file).__dict__[scheduler.cache_level]
        unsplit_oh = Overheads.from_file(scheduler.unsplit_oh_file)
        unsplit_oh.initial_cache_loss = CacheDelay.from_file(scheduler.pmo_file).__dict__[scheduler.cache_level]
        unsplit_oh.cache_affinity_loss = CacheDelay.from_file(scheduler.pmo_file).__dict__[scheduler.cache_level]
        if scheduler.lock_type is not None:
            lock_oh = Overheads.from_file(scheduler.lock_oh_file)
            copy_lock_overheads(oh, lock_oh)
            unsplit_lock_oh = Overheads.from_file(scheduler.unsplit_lock_oh_file)
            copy_lock_overheads(unsplit_oh, unsplit_lock_oh)
            #syscall_oh = Overheads.from_file(scheduler.syscall_oh_file)
            #oh.syscall_in = syscall_oh.syscall_in
            #oh.syscall_out = syscall_oh.syscall_out
            wss_list = get_lock_wss_list()
        else:
            wss_list = get_wss_list()
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
                    if scheduler.lock_type is not None:
                        results = compute_splits_lock(unsplit_oh, oh,
                                                      scheduler.cluster_size,
                                                      scheduler.spinlock,
                                                      task_system, partitions)
                    else:
                        results = compute_splits_nolock(unsplit_oh, oh,
                                                        scheduler.dedicated_irq,
                                                        task_system, partitions)
                                                    
                    if results is not None:
                        reporter.report_data_point(scheduler, task_system_obj,
                                                   wss,
                                                   results.base_lateness,
                                                   results.best_lateness,
                                                   results.ave_splits,
                                                   results.max_splits)

        data = reporter.get_all_graph_points()
        for sched_name in data:
            print "Doing " + sched_name
            outfile = open('results/' + sched_name, 'w')
            for point in data[sched_name]:
                outfile.write("{0}\t{1}\t{2}\t{3}\t{4}\t{5}\t{6}\n".format(point[0], point[1], point[2], point[3], point[4], point[5], point[6]))
            outfile.close()

if len(sys.argv) > 4:
    task_systems = get_lock_task_systems(sys.argv[1], sys.argv[2],
                                         float(sys.argv[3]),
                                         sys.argv[4], int(sys.argv[5]),
                                         float(sys.argv[6]))
    scheduler_list = get_ludwig_lock_schedulers()
else:
    task_systems = get_task_systems(sys.argv[1], sys.argv[2], float(sys.argv[3]))
    scheduler_list = get_ludwig_schedulers()
process_task_systems(task_systems, scheduler_list)
