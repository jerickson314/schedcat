#!/usr/bin/env python

from schedcat.overheads.model import Overheads, CacheDelay
from schedcat.overheads.jlfp import charge_scheduling_overheads, quantize_params

from schedcat.model.ms2us import ms2us
from schedcat.model.serialize import load
from schedcat.model.tasks import SporadicTask, TaskSystem

from schedcat.sched.edf.gel_pl import bound_gfl_response_times
import sys

main_overheads_file = sys.argv[1]
cpmd_overheads_file = sys.argv[2]
task_system_file = sys.argv[3]
num_cpus = int(sys.argv[4])
dedicated_irq = False
if sys.argv[5] == 'd':
    dedicated_irq = True

oh = Overheads.from_file(main_overheads_file)
oh.initial_cache_loss = CacheDelay.from_file(cpmd_overheads_file)
oh.cache_affinity_loss = CacheDelay.from_file(cpmd_overheads_file)

task_system = ms2us(load(task_system_file))

charge_scheduling_overheads(oh, num_cpus, dedicated_irq, task_system)
quantize_params(task_system)
success = bound_gfl_response_times(num_cpus, task_system, 15)

if success:
    print [task.response_time - task.deadline for task in task_system]
else:
    print "Unbounded tardiness for task system with utilization", \
          task_system.utilization()
    print "Maximum single utilization", \
          max([task.utilization() for task in task_system])
