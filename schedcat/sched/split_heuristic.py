
from schedcat.overheads.model import Overheads, CacheDelay
from schedcat.overheads.jlfp_split import charge_scheduling_overheads, \
                                          quantize_params
#import schedcat.overheads.jlfp_split as jlfp_split
#import schedcat.overheads.jlfp as jlfp
from schedcat.overheads.locking import charge_spinlock_overheads, \
                                       charge_semaphore_overheads

from schedcat.locking.bounds import assign_pp_locking_prios, \
                                    assign_edf_locking_prios, \
                                    apply_task_fair_mutex_bounds, \
                                    apply_clustered_omlp_bounds

from schedcat.model.split_tasks import apply_splits, unsplit

from schedcat.sched.edf.gel_pl import compute_gfl_response_details, \
                                      compute_response_details, \
                                      has_bounded_tardiness

import heapq

from functools import partial

from copy import deepcopy

class SplitResult:
    def __init__(self, base_lateness, best_lateness, ave_splits, max_splits):
        self.base_lateness = base_lateness
        self.best_lateness = best_lateness
        self.ave_splits = ave_splits
        self.max_splits = max_splits

def compute_splits_nolock(overheads_unsplit, overheads_split, dedicated_irq,
                          taskset, parts):
    true_base_lateness = compute_init_nolock(overheads_unsplit, dedicated_irq,
                                             taskset, parts)
    if true_base_lateness is None:
        return None
    # Initial setup
    for task in taskset:
        task.split = 1
        task.split_saturated = False
    boundfunc = partial(bound_no_locks, dedicated_irq, overheads_split)
    details = [None]*len(parts)
    for i in range(len(parts)):
        details = boundfunc(i, taskset, parts, details)
        if details is None:
            return SplitResult(true_base_lateness, true_base_lateness, 1.0, 1.0)
    return compute_splits(details, taskset, parts, boundfunc,
                          true_base_lateness, True)

def compute_init_nolock(overheads_unsplit, dedicated_irq, taskset, parts):
    for task in taskset:
        task.split = 1
        task.split_saturated = False
    boundfunc = partial(bound_no_locks, dedicated_irq, overheads_unsplit)
    details = [None]*len(parts)
    for i in range(len(parts)):
        details = boundfunc(i, taskset, parts, details)
        if details is None:
            return None
    return max(generic_lateness_list(details))

def compute_splits_lock(oheads_unsplit, oheads_split, cluster_size, spinlock,
                        taskset, parts):
    true_base_lateness = compute_init_lock(oheads_unsplit, cluster_size,
                                           spinlock, taskset, parts)
    if true_base_lateness is None:
        return None
    # Initial setup
    for task in taskset:
        task.split = 1
        task.split_saturated = False
    boundfunc = partial(bound_with_locks, spinlock, cluster_size, oheads_split)

    details = boundfunc(0, taskset, parts, None)
    if details is None:
        return SplitResult(true_base_lateness, true_base_lateness, 1.0, 1.0)
    return compute_splits(details, taskset, parts, boundfunc,
                          true_base_lateness, False)

def compute_init_lock(oheads_unsplit, cluster_size, spinlock, taskset, parts):
    # Initial setup
    for task in taskset:
        task.split = 1
        task.split_saturated = False
    boundfunc = partial(bound_with_locks, spinlock, cluster_size, oheads_unsplit)

    details = boundfunc(0, taskset, parts, None)
    if details is None:
        return None
    return max(generic_lateness_list(details))

def compute_splits(initial_details, taskset, parts, boundfunc,
                   true_base_lateness, restore_part):
    # Compute tardiness bounds for initial task system.
    base_lateness = max(generic_lateness_list(initial_details))
    best_details = initial_details

    keep_splitting = True
    while keep_splitting:
        keep_splitting = False
        lateness_list = generic_lateness_list(best_details)
        indexed_partitions = sorted(enumerate(lateness_list),
                                    key=lambda x: x[1], reverse=True)
        for i, lateness in indexed_partitions:
            new_details = try_one_split(i, taskset, parts, best_details,
                                        boundfunc, max(lateness_list),
                                        restore_part)
            if new_details is not None:
                best_details = new_details
                keep_splitting = True
                break
    best_lateness = max(generic_lateness_list(best_details))
    if best_lateness < true_base_lateness:
        splits = [task.split for task in taskset]
        return SplitResult(true_base_lateness, best_lateness,
                           sum(splits) / len(splits), max(splits))
    else:
        return SplitResult(true_base_lateness, true_base_lateness, 1.0, 1.0)

def try_one_split(part_num, taskset, parts, old_details, boundfunc,
                  best_lateness, restore_part):
    part = parts[part_num]
    part_details = old_details[part_num]
    # Compute splitting candidates, in order
    sorted_comps = heapq.nlargest(part.cpus - 1,
                                  enumerate(part_details.G_i),
                                  key=lambda g: g[1])
    sorted_S = sorted(enumerate(part_details.S_i),
                      key=lambda g: g[1], reverse=True)
    candidates = [c[0] for c in sorted_comps]
    new_candidates = [c[0] for c in sorted_S 
                         if c[0] not in candidates]
    candidates.extend(new_candidates)
    needs_restore = True
    for c in candidates:
        if not part[c].split_saturated:
            part[c].split += 1
            new_details = boundfunc(part_num, taskset, parts, old_details)
            if new_details is not None:
                next_lateness = max(generic_lateness_list(new_details))
                if next_lateness < best_lateness:
                    #Good
                    return new_details
                else:
                    #Undo
                    part[c].split -= 1
            else:
                #Undo this one.
                part[c].split -= 1
                part[c].split_saturated = True
    # If we got here, we didn't find a beneficial split.  Restore the old part
    # if needed.
    if restore_part:
        old_details[part_num] = part_details
    return None

def generic_lateness_list(details):
    return [part_details.max_lateness() for part_details in details]

# This will change old_details!
def bound_no_locks(dedicated_irq, oheads, part_num, taskset, parts,
                   old_details):
    part = parts[part_num]
    with_oh = part.copy()
    success = charge_scheduling_overheads(oheads, part.cpus, dedicated_irq,
                                          with_oh)
    apply_splits(with_oh)
    if success and has_bounded_tardiness(part.cpus, with_oh):
        old_details[part_num] = compute_gfl_response_details(part.cpus,
                                                             with_oh, 15)
        return old_details
    else:
        return None

def bound_with_locks(spinlock, cluster_size, oheads, part_num, taskset, parts,
                     old_details):

    # Copy task system with splits already applied.
    base_ts = []
    base_parts = []
    for part in parts:
        new_part = part.copy()
        apply_splits(new_part)
        # Seems not to be getting copied for some reason
        new_part.cpus = part.cpus
        base_parts.append(new_part)
        base_ts += new_part

    # Apply basic overhead account.
    for part in base_parts:
        if spinlock:
            charge_spinlock_overheads(oheads, part)
        else:
            charge_semaphore_overheads(oheads, True, False, part)
        for task in part:
            # Initially assume completion by deadline and use G-FL PPs.
            task.response_time = task.deadline
            task.pp = task.deadline - (part.cpus - 1) / (part.cpus) * \
                      task.cost

    assign_pp_locking_prios(base_ts)

    # Initially assume completion by deadline
    for t in base_ts:
        t.response_time = t.deadline

    completion_ok = False

    count = 0

    details = [None]*len(base_parts)
    
    while not completion_ok:
        completion_ok = True

        new_ts = []
        new_parts = []
        for part in base_parts:
            new_part = part.copy()
            # Seems not to be getting copied for some reason
            new_part.cpus = part.cpus
            new_parts.append(new_part)
            new_ts += new_part
        
        count += 1
        if count > 100:
            return None

        #assign_pessimistic_locking_prios(new_ts)
        #assign_edf_locking_prios(new_ts)

        if spinlock:
            blocking_terms = apply_task_fair_mutex_bounds
        else:
            blocking_terms = apply_clustered_omlp_bounds

        # Apply blocking bounds
        blocking_terms(new_ts, cluster_size, 0)
        
        for part in new_parts:
            inflation = oheads.syscall_in(len(part))
            if not spinlock:
                inflation = oheads.schedule(len(part)) + \
                            oheads.ctx_switch(len(part))
            for t in part:
                if t.arrival_blocked:
                    t.cost += inflation
                    t.arrival_blocked += inflation

        for i, part in enumerate(new_parts):
            # Hack, since charge_scheduling_overheads expects an unsplit TS.
            unsplit(part)
            if not charge_scheduling_overheads(oheads, part.cpus,
                                               True, part):
                return None

            quantize_params(part)
            # Resplit
            apply_splits(part)
            if not has_bounded_tardiness(part.cpus, part):
                return None

            details[i] = compute_response_details(cluster_size, part, 15)

            # Response-time bounds applied to real version
            for j, t in enumerate(part):
                if details[i].bounds[j] > base_parts[i][j].response_time:
                    completion_ok = False
                base_parts[i][j].response_time = details[i].bounds[j]

    return details

