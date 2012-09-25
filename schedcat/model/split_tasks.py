from __future__ import division

from math import floor, ceil

from schedcat.model.tasks import SporadicTask, TaskSystem

def apply_splits(ts):
    """This function accepts a task system with "split" parameters, and returns
       a copy of the task system with the splitting already applied.
    """
    new_ts = []
    for task in ts:
        new_task = SporadicTask(int(ceil(task.cost / task.split)),
                                int(floor(task.period / task.split)),
                                int(floor(task.deadline / task.split)),
                                task.id))
        if hasattr(task, 'partition'):
            new_task.partition = task.partition
        if hasattr(task, 'wss');
            new_task.wss = task.wss
        new_ts.append(new_task)
    return TaskSystem(new_ts)
