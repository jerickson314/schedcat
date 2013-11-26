#Necessary includes and stuff

from schedcat.example.generator import generate_taskset_files, \
                                       generate_lock_taskset_files
from schedcat.example.mapping import partition_tasks
from schedcat.example.overheads import get_oh_object, \
                                       bound_cfl_with_oh
from schedcat.example.locking import bound_cfl_with_locks

from schedcat.model.serialize import load

def example_overheads():
    return get_oh_object(
        "schedcat/example/oh_host=ludwig_scheduler=C-FL-L2-RM_stat=avg.csv",
        "schedcat/example/oh_host=ludwig_scheduler=C-FL-L2-RM_locks=MX-Q_stat=avg.csv",
        "schedcat/example/pmo_host=ludwig_background=load_stat=avg.csv",
        "L2")

def nolock_example():
    oheads = example_overheads()
    task_files = generate_taskset_files("uni-medium",
                                        "uni-moderate",
                                        9, 2)
    for file in task_files:
        ts = load(file)
        for task in ts:
            task.wss = 256
        clusts = partition_tasks(2, 12, True, ts)
        print "Processing {}".format(file)
        if clusts and bound_cfl_with_oh(oheads, True, clusts):
            for clust in clusts:
                for task in clust:
                    print task.response_time - task.deadline

def lock_example():
    oheads = example_overheads()
    task_files = generate_lock_taskset_files("uni-medium",
                                             "uni-moderate",
                                             6, "medium",
                                             6, 0.1, 2)
    for file in task_files:
        ts = load(file)
        for task in ts:
            task.wss = 256
        clusts = partition_tasks(2, 12, True, ts)
        print "Processing {}".format(file)
        if clusts:
            clusts2 = bound_cfl_with_locks(ts, clusts, oheads, 2)
            if clusts2:
                for clust in clusts2:
                    for task in clust:
                        print task.response_time - task.deadline

#Actually run examples when this script is executed
print "Running non-lock example"
nolock_example()
print "Running lock example"
lock_example()
