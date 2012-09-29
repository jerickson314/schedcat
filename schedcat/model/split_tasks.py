from __future__ import division

from math import floor, ceil

from schedcat.model.tasks import SporadicTask, TaskSystem

def apply_splits(ts):
    """This function accepts a task system with "split" parameters, and
       applies the given splits
    """
    for task in ts:
        task.cost = int(ceil(task.cost / task.split))
        task.period = int(floor(task.period / task.split))
        task.deadline = int(floor(task.deadline / task.split))
