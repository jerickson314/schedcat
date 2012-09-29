#!/usr/bin/env python

from schedcat.overheads.model import Overheads, CacheDelay

from schedcat.model.serialize import load
from schedcat.model.tasks import SporadicTask, TaskSystem

from schedcat.sched.split_heuristic import compute_splits

from schedcat.mapping.rollback import Bin, MaxSpareCapacity

import sys

# Taken from Bjoern's dissertation
def partition_tasks(cluster_size, clusters, dedicated_irq, taskset):
    first_cap = cluster_size - 1 if dedicated_irq else cluster_size
    first_bin = Bin(size=SporadicTask.utilization, capacity=first_cap)
    other_bins = [Bin(size=SporadicTask.utilization, capacity=first_cap) for _ in xrange(1, clusters)]
    
    heuristic = MaxSpareCapacity(initial_bins=[first_bin] + other_bins)

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

if len(sys.argv) < 8:
    print "main_overheads_file cpmd_overheads_file task_system_file num_cpus_per_cluster num_clusters wss dedicated_irq"
    sys.exit()

main_overheads_file = sys.argv[1]
cpmd_overheads_file = sys.argv[2]
task_system_file = sys.argv[3]
num_cpus_per_cluster = int(sys.argv[4])
num_clusters = int(sys.argv[5])
wss = int(sys.argv[6])
dedicated_irq = False
if sys.argv[7] == 'd':
    dedicated_irq = True

oh = Overheads.from_file(main_overheads_file)
oh.initial_cache_loss = CacheDelay.from_file(cpmd_overheads_file)
oh.cache_affinity_loss = CacheDelay.from_file(cpmd_overheads_file)

task_system = load(task_system_file)

for task in task_system:
    task.wss = wss

partitions = partition_tasks(num_cpus_per_cluster, num_clusters, dedicated_irq,
                             task_system)

if partitions:
    #for part in range(num_clusters):
    for cluster_tasks in partitions:
    #    cluster_tasks = TaskSystem([task for task in task_system
    #                                if task.partition == part])
        results = compute_splits(oh, num_cpus_per_cluster, cluster_tasks,
                                 dedicated_irq)

        if results is not None:
            print "Original bound", results.base_lateness
            print "Improved bound", results.best_lateness
            print "Splits", [task.split for task in cluster_tasks]
        else:
            print "Unbounded tardiness for task system with utilization", \
                  cluster_tasks.utilization()
            print "Maximum single utilization", \
                  max([task.utilization() for task in cluster_tasks])
else:
    print "Partitioning failed!"
