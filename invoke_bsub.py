#!/usr/bin/env python
from __future__ import division

from schedcat.model.tasks import TaskSystem
from schedcat.model.serialize import write
from schedcat.generator.tasksets import make_standard_dists
from schedcat.util.time import ms2us

CACHE_SIZE_CLUSTERS = { 'L2' : 2, 'L3' : 6}

import os

distributions = make_standard_dists()

for period_name in distributions:
    by_util = distributions[period_name]
    for util_name in by_util:
        cluster_size = 24
        for cap in [cluster_size / 20 * i for i in range(1, 21)]:
            os.system("bsub /netscr/jpericks/schedcat/gen_dat.py {0} {1} {2}".format(util_name, period_name, str(cap)))
