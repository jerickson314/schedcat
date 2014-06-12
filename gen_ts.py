#!/usr/bin/env python
from __future__ import division

from schedcat.model.tasks import TaskSystem
from schedcat.model.serialize import write
from schedcat.generator.tasksets import mkgen, NAMED_UTILIZATIONS, NAMED_PERIODS
from schedcat.util.time import ms2us

import schedcat.model.resources as resources
#import schedcat.locking.bounds as bounds

import os
import random

taskset_root = "/home/jerickso/tasksets/"
locking_taskset_root = taskset_root + "locking/"
CACHE_SIZE_CLUSTERS = { 'L2' : 2, 'L3' : 6 }

CSLENGTH  = {
    'short'   : lambda: random.randint(1,   15),
    'medium'  : lambda: random.randint(1,  100),
    'long'    : lambda: random.randint(5, 1280),
}

def generate_tasksets(util_name, period_name, cap):
    print "Generating tasksets"
    generated_sets = []
    dirname = taskset_root + "{0}/{1}/{2}".format(util_name,
                                                              period_name,
                                                              cap)
    if os.path.exists(dirname):
        return [dirname + "/" + item for item in os.listdir(dirname)]
    else:
        os.makedirs(dirname)
    generator = mkgen(NAMED_UTILIZATIONS[util_name], NAMED_PERIODS[period_name])
    for i in range(100):
        print "Generating {0} {1} {2} {3}".format(period_name,
                util_name, cap, i)
        clust = generator(max_util=cap, time_conversion=ms2us)
        filename = dirname + "/taskset_{0}_{1}_{2}_{3}".format(util_name,
                                                               period_name,
                                                               cap, i)
        directory = os.path.dirname(filename)
        write(clust, filename)
        generated_sets.append(filename)
    return generated_sets

def generate_lock_tasksets(util_name, period_name, cap, cslength, nres,
                           pacc):
    print "Generating lock tasksets"
    generated_sets = []
    dirname = locking_taskset_root + "{0}/{1}/{2}/{3}/{4}/{5}".format(
            util_name, period_name, cap, cslength, nres, pacc)
    if os.path.exists(dirname):
        return (dirname + "/" + item for item in os.listdir(dirname))
    else:
        os.makedirs(dirname)
    generator = mkgen(NAMED_UTILIZATIONS[util_name], NAMED_PERIODS[period_name])
    for i in range(100):
        print "Generating {0} {1} {2} {3} {4} {5} {6}".format(util_name,
                                                              period_name,
                                                              cap, cslength,
                                                              nres, pacc, i)
        taskset = generator(max_util=cap, time_conversion=ms2us)
        resources.initialize_resource_model(taskset)
        has_requests = False
        while not has_requests:
            for task in taskset:
                for res_id in range(nres):
                    if random.random() <= pacc:
                        nreqs = random.randint(1, 5)
                        length = CSLENGTH[cslength]
                        has_requests = True
                        for j in range(nreqs):
                            task.resmodel[res_id].add_request(length())
        filename = dirname + "/taskset_{0}_{1}_{2}_{3}_{4}_{5}_{6}".format(
                util_name, period_name, cap, cslength, nres, pacc, i)
        directory = os.path.dirname(filename)
        write(taskset, filename)
        generated_sets.append(filename)
    return generated_sets
