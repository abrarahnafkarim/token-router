"""Global deadline manager. remaining() is processing time (reserve held back
for final writeout); hard_remaining() is wall-clock to the configured limit."""
import time


class Deadline:
    def __init__(self, limit=575, reserve=30):
        self.t0 = time.monotonic()
        self.limit = limit
        self.reserve = reserve

    def elapsed(self):
        return time.monotonic() - self.t0

    def hard_remaining(self):
        return self.limit - self.elapsed()

    def remaining(self):
        return self.hard_remaining() - self.reserve

    def should_flush(self):
        return self.remaining() <= 0

    def affordable(self, est_seconds, tasks_left=1):
        """Can we afford est_seconds of local compute given remaining tasks?"""
        rem = self.remaining()
        if rem <= 2:
            return False
        budget = max(2.0, rem / max(1, tasks_left))
        return est_seconds <= budget * 1.8 and est_seconds < rem - 2
