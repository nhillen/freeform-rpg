"""Simple terminal spinner for long-running operations."""

import sys
import threading
import time


class Spinner:
    """
    Context manager that shows a spinner animation while work runs.

    Usage:
        with Spinner("Thinking"):
            result = slow_function()
    """

    FRAMES = [".", "..", "...", "   "]
    INTERVAL = 0.4

    def __init__(self, message: str = "Thinking"):
        self.message = message
        self._stop = threading.Event()
        self._thread = None

    def _spin(self):
        idx = 0
        while not self._stop.is_set():
            frame = self.FRAMES[idx % len(self.FRAMES)]
            sys.stderr.write(f"\r  {self.message}{frame}   ")
            sys.stderr.flush()
            idx += 1
            self._stop.wait(self.INTERVAL)
        # Clear the spinner line
        sys.stderr.write(f"\r{' ' * (len(self.message) + 12)}\r")
        sys.stderr.flush()

    def __enter__(self):
        self._thread = threading.Thread(target=self._spin, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *args):
        self._stop.set()
        self._thread.join()

    def update(self, message: str):
        """Update the spinner message mid-operation."""
        self.message = message
