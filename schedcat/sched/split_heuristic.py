
from schedcat.overheads.model import Overheads, CacheDelay
from schedcat.overheads.jlfp_split import charge_scheduling_overheads, \
                                          quantize_params

from schedcat.model.split_tasks import apply_splits

from schedcat.sched.edf.gel_pl import compute_gfl_response_details, \
                                      has_bounded_tardiness

import heapq

class SplitResult:
    def __init__(self, base_lateness, best_lateness):
        self.base_lateness = base_lateness
        self.best_lateness = best_lateness

def compute_splits(overheads, num_cpus, task_system, dedicated_irq):
    # Initial setup
    for task in task_system:
        task.split = 1
        task.split_saturated = False
    # Compute tardiness bounds for initial task system.
    with_oh = task_system.copy()
    charge_scheduling_overheads(overheads, num_cpus, dedicated_irq, with_oh)
    quantize_params(with_oh)
    if not has_bounded_tardiness(num_cpus, with_oh):
        return None
    next_details = compute_gfl_response_details(num_cpus, with_oh, 15)
    # G-FL results in all tasks having same lateness bound, so just look at
    # the first
    best_lateness = next_details.bounds[0] - with_oh[0].deadline
    base_lateness = best_lateness

    keep_splitting = True
    while keep_splitting:
        keep_splitting = False
        # Compute splitting candidates, in order
        sorted_comps = heapq.nlargest(num_cpus - 1,
                                       enumerate(next_details.G_i),
                                       key=lambda g: g[1])
        sorted_S = sorted(enumerate(next_details.S_i),
                          key=lambda g: g[1], reverse=True)
        candidates = [c[0] for c in sorted_comps]
        new_candidates = [c[0] for c in sorted_S 
                             if c[0] not in candidates]
        candidates.extend(new_candidates)
        for c in candidates:
            if not task_system[c].split_saturated:
                task_system[c].split += 1
                with_oh = task_system.copy()
                charge_scheduling_overheads(overheads, num_cpus, dedicated_irq,
                                            with_oh)
                apply_splits(with_oh)
                if has_bounded_tardiness(num_cpus, with_oh):
                    next_details = compute_gfl_response_details(num_cpus,
                                                                with_oh, 15)
                    next_lateness = next_details.bounds[0] - with_oh[0].deadline
                    if next_lateness < best_lateness:
                        best_lateness = next_lateness
                        #Good
                        keep_splitting = True
                        break
                    else:
                        #Undo
                        task_system[c].split -= 1
                else:
                    #Undo this one.
                    task_system[c].split -= 1
                    task_system[c].split_saturated = True

    return SplitResult(base_lateness, best_lateness)

