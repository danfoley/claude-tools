import time
import unittest

from storage.timeout import run_with_timeout


class RunWithTimeoutTest(unittest.TestCase):
    def test_a_call_that_takes_too_long_raises_a_timeout(self):
        with self.assertRaises(TimeoutError):
            run_with_timeout(1, lambda: time.sleep(5))

    def test_a_quick_call_returns_normally_and_clears_the_alarm(self):
        calls = []
        run_with_timeout(1, lambda: calls.append("done"))
        time.sleep(1.2)
        self.assertEqual(calls, ["done"])


if __name__ == "__main__":
    unittest.main()
