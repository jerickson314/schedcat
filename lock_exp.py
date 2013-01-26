#!/usr/bin/env python
from __future__ import division

from schedcat.model.tasks import TaskSystem
from schedcat.model.serialize import write
from schedcat.generator.tasksets import make_standard_dists
from schedcat.util.time import ms2us

CACHE_SIZE_CLUSTERS = { 'L2' : 2, 'L3' : 6}

import os
import commands
import time

distributions = make_standard_dists()
#util_names = ["uni-light", "uni-heavy", "bimo-medium"]
#period_names = ["uni-short", "uni-moderate", "uni-long"]
cslengths = ["short", "medium", "long"]
nress = [6, 12]
paccs = [0.1, 0.25]

for period_name in distributions:
    by_util = distributions[period_name]
    for util_name in by_util:
        for cslength in cslengths:
            for nres in nress:
                for pacc in paccs:
                    cluster_size = 24
                    for cap in [cluster_size / 20 * i for i in range(1, 21)]:
                        while (int(commands.getoutput("ps -efww | grep gen_dat | wc -l")) >= 3):
                            time.sleep(5.0)
                        print "Spawning {0} {1} {2} {3} {4} {5}".format(util_name, period_name, str(cap), cslength, str(nres), str(pacc))
                        os.system("./gen_dat.py {0} {1} {2} {3} {4} {5} &".format(util_name, period_name, str(cap), cslength, str(nres), str(pacc)))
