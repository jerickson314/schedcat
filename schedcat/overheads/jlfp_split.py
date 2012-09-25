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

    sched = 2 * (oheads.schedule(n) + oheads.ctx_switch(n)) \
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
        first_cost   = (split_cost + sched) / uscale + 2 * cpre
        other_cost   = first_cost
        # Account for the fact that first job can have IPI delay, though others
        # cannot.
        if dedicated_irq or num_cpus > 1:
            first_cost += oheads.ipi_latency(n)
        ti.cost      = first_cost + (ti.split - 1) * other_cost
        if ti.density() > 1:
            return False

    return taskset

def quantize_params(taskset):
    """After applying overheads, use this function to make
        task parameters integral again."""
        
    for t in taskset:
        t.cost     = int(ceil(t.cost))
        t.period   = int(floor(t.period))
        t.deadline = int(floor(t.deadline))
        if t.density() > 1:
            return False

    return taskset
