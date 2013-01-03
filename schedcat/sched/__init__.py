
# Python model to C++ model conversion code.


try:
    from .native import TaskSet

    using_native = True

    def get_native_taskset(tasks):
        ts = TaskSet()
        for t in tasks:
            pp = 0
            if hasattr(t, 'pp'):
                pp = t.pp
            if hasattr(t, 'request_span'):
                ts.add_task(t.cost, t.period, t.deadline, pp, t.request_span)
            else:
                ts.add_task(t.cost, t.period, t.deadline, t.pp)
        return ts

except ImportError:
    # Nope, C++ impl. not available. Use Python implementation.
    using_native = False
    def get_native_taskset(tasks):
        assert False # C++ implementation not available
