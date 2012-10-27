from __future__ import division

from math import ceil, floor

def charge_initial_load(oheads, taskset):
    """Increase WCET to reflect the cost of establishing a warm cache.
    Note: assumes that .wss (working set size) has been populated in each task.
    """
    if oheads:
        for ti in taskset:
            load = oheads.initial_cache_load(ti.wss)
            assert load >= 0 # negative overheads make no sense    
            ti.cost += load
            if ti.density() > 1:
                # infeasible
                return False
    return taskset

def preemption_centric_irq_costs(oheads, dedicated_irq, taskset):
    n      = len(taskset)
    qlen   = oheads.quantum_length
    tck    = oheads.tick(n)
    ev_lat = oheads.release_latency(n)

    # tick interrupt
    utick = tck / qlen
    
    urel  = 0.0
    if not dedicated_irq:
        rel   = oheads.release(n)
        for ti in taskset:
            urel += (rel / ti.period)

    # cost of preemption
    cpre = tck + ev_lat * utick
    if not dedicated_irq:
        cpre += n * rel + ev_lat * urel

    return (1.0 - utick - urel, cpre)

def charge_scheduling_overheads(oheads, num_cpus, dedicated_irq, taskset):
    if not oheads:
        return taskset

    uscale, cpre = preemption_centric_irq_costs(oheads, dedicated_irq, taskset)

    if uscale <= 0:
        # interrupt overload
        return False

    n   = len(taskset)
    wss = taskset.max_wss()

#    has_splits = (len([task for task in taskset if task.split > 1]) > 0)
#    if len([task for task in taskset if task.split > 1]) > 0:
#        sched_oh = oheads.schedule(n) + oheads.release(n)
#    else:
    sched_oh = oheads.schedule(n)

    sched_first = 2 * (sched_oh + oheads.ctx_switch(n)) \
            + oheads.cache_affinity_loss(wss)

    sched_other = sched_oh + oheads.ctx_switch(n) \
                  + oheads.cache_affinity_loss(wss)

    irq_latency = oheads.release_latency(n)

    if dedicated_irq or num_cpus > 1:
        unscaled = 2 * cpre + oheads.ipi_latency(n)
    else:
        unscaled = 2 * cpre

    for ti in taskset:
        ti.period   -= irq_latency
        ti.deadline -= irq_latency
        # Initially, we will work with the fiction that jobs are scheduled
        # without accounting for overheads - the first subjob will then have
        # IPI latency, but other jobs cannot.  Actual scheduler should start
        # the budget with a provided IPI latency, so that all jobs have the
        # same length accounting for overheads.
        split_cost   = ti.cost / ti.split
        # Initially set up all jobs to have the basic overheads, but no IPI
        # delay.
        first_cost   = (split_cost + sched_first) / uscale + 2 * cpre
        # Technically release latency cost applies only to non-final subjobs
        # rather than non-initial, but other_cost will be counted s_i - 1 times.
        other_cost   = (split_cost + sched_other) / uscale \
                        + cpre
        if split_cost < ((ti.split - 1) / ti.split * \
                         (uscale * oheads.ipi_latency(n) + \
                          uscale * cpre + \
                          sched_first - sched_other)):
            return False
        # Account for the fact that first job can have IPI delay, though others
        # cannot.
        if dedicated_irq or num_cpus > 1:
            first_cost += oheads.ipi_latency(n)
        ti.cost      = first_cost + (ti.split - 1) * other_cost
        if hasattr(ti, 'request_span'):
            if ti.split > 1:
                ti.request_span = ti.request_span / uscale
            else:
                ti.request_span = 0
        if ti.utilization() > 1:
            return False

    return taskset

def quantize_params(taskset):
    """After applying overheads, use this function to make
        task parameters integral again."""
        
    for t in taskset:
        t.cost     = int(ceil(t.cost))
        t.period   = int(floor(t.period))
        t.deadline = int(floor(t.deadline))
        if hasattr(t, 'request_span'):
            t.request_span = int(ceil(t.request_span))
        if t.density() > 1:
            return False

    return taskset
