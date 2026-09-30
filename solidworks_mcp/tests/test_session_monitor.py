import unittest

from solidworks_mcp.session_monitor import SessionMonitor


class Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


class App:
    def __init__(self):
        self.count = 1

    def GetDocumentCount(self):
        return self.count


class Automation:
    def __init__(self):
        self.app = App()
        self.is_connected = True


class Gpu:
    def __init__(self, value=100.0):
        self.value = value
        self.reads = 0

    def __call__(self, sw):
        self.reads += 1
        return self.value


def monitor(gpu=None):
    clock = Clock()
    return SessionMonitor(clock=clock, gpu_reader=gpu or Gpu()), clock


class CountingTests(unittest.TestCase):
    def test_document_count_changes_are_counted(self):
        watcher, _ = monitor()
        sw = Automation()
        watcher.observe(sw, "connect_solidworks", True)   # baseline 1
        sw.app.count = 3
        watcher.observe(sw, "open_document", True)
        sw.app.count = 2
        watcher.observe(sw, "close_document", True)
        snapshot = watcher.snapshot()
        self.assertEqual(2, snapshot["documents_opened"])
        self.assertEqual(1, snapshot["documents_closed"])

    def test_disconnected_session_is_not_observed(self):
        watcher, _ = monitor()
        sw = Automation()
        sw.is_connected = False
        self.assertEqual((), watcher.observe(sw, "open_document", True))
        self.assertEqual(0, watcher.snapshot()["documents_opened"])

    def test_successful_restart_resets_counters(self):
        watcher, _ = monitor()
        sw = Automation()
        watcher.observe(sw, "connect_solidworks", True)
        sw.app.count = 0
        watcher.observe(sw, "close_document", True)
        watcher.observe(sw, "restart_solidworks", True)
        self.assertEqual(0, watcher.snapshot()["documents_closed"])

    def test_failed_restart_keeps_counters(self):
        watcher, _ = monitor()
        sw = Automation()
        watcher.observe(sw, "connect_solidworks", True)
        sw.app.count = 0
        watcher.observe(sw, "close_document", True)
        watcher.observe(sw, "restart_solidworks", False)
        self.assertEqual(1, watcher.snapshot()["documents_closed"])


class GpuSamplingTests(unittest.TestCase):
    def test_gpu_is_sampled_on_lifecycle_tools_and_every_minute(self):
        gpu = Gpu()
        watcher, clock = monitor(gpu)
        sw = Automation()
        watcher.observe(sw, "draw_line", True)          # first observation samples
        clock.now = 10
        watcher.observe(sw, "draw_line", True)          # too soon
        clock.now = 20
        watcher.observe(sw, "open_document", True)      # lifecycle
        clock.now = 81
        watcher.observe(sw, "draw_line", True)          # 61 s after the last sample
        self.assertEqual(3, gpu.reads)
        self.assertEqual(100.0, watcher.snapshot()["gpu_dedicated_mb"])


class WarningTests(unittest.TestCase):
    def test_high_gpu_memory_warns_once_per_interval(self):
        watcher, clock = monitor(Gpu(5000.0))
        sw = Automation()
        first = watcher.observe(sw, "open_document", True)
        clock.now = 100
        second = watcher.observe(sw, "open_document", True)
        clock.now = 1000
        third = watcher.observe(sw, "open_document", True)
        self.assertEqual(1, len(first))
        self.assertIn("GPU memory 5000 MB", first[0])
        self.assertIn("ask the user before calling restart_solidworks", first[0])
        self.assertEqual((), second)
        self.assertEqual(1, len(third))

    def test_many_closed_documents_warn(self):
        watcher, _ = monitor()
        sw = Automation()
        sw.app.count = 200
        watcher.observe(sw, "connect_solidworks", True)
        sw.app.count = 0
        warnings = watcher.observe(sw, "close_document", True)
        self.assertIn("200 documents closed", warnings[0])

    def test_unknown_gpu_memory_does_not_warn(self):
        watcher, _ = monitor(Gpu(None))
        self.assertEqual((), watcher.observe(Automation(), "open_document", True))


if __name__ == "__main__":
    unittest.main()
