import threading

class ExecutionGuard:
    """
    Ensures a skill or task runs only once, even in case of timeouts.
    Prevents double-spending or redundant transactions in agent workflows.
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._executed = False

    def run_once(self, func, *args, **kwargs):
        with self._lock:
            if self._executed:
                print("Task already executed or in progress.")
                return None
            self._executed = True
        return func(*args, **kwargs)
