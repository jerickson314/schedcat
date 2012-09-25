from __future__ import division

from schedcat.model.tasks import SporadicTask, TaskSystem

def ms2us(ts):
     new_ts = []
     for task in ts:
        new_task = SporadicTask(task.cost * 1000, task.period * 1000,
                                task.deadline * 1000, task.id)
        if hasattr(task, 'partition'):
            new_task.partition = task.partition
        if hasattr(task, 'wss'):
            new_task.wss = task.wss
        else:
            new_task.wss = 1024
        new_ts.append(new_task)
     return TaskSystem(new_ts)
