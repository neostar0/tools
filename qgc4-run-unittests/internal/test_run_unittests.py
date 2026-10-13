#!/usr/bin/env python3
"""Unit tests for qgc4-run-unittests' output parsing (the pure-function core).

Run: python3 internal/test_run_unittests.py
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import run_unittests as rt

# Real output shapes, captured from QGC debug builds on 2026-10-12.
PASSING_RUN = """\
********* Start testing of SignalSpyTest *********
Config: Using QtTest library 5.15.2, Qt 5.15.2 (x86_64 debug build; by MSVC 2019), windows 10
PASS   : SignalSpyTest::initTestCase()
PASS   : SignalSpyTest::_signalSpyTest()
PASS   : SignalSpyTest::cleanupTestCase()
Totals: 3 passed, 0 failed, 0 skipped, 0 blacklisted, 15ms
********* Finished testing of SignalSpyTest *********
2026-10-12 09:54:41.310 30388 default: ALL TESTS PASSED
"""

FAILING_RUN = """\
********* Start testing of ComponentInformationCacheTest *********
PASS   : ComponentInformationCacheTest::initTestCase()
PASS   : ComponentInformationCacheTest::_basic_test()
FAIL!  : ComponentInformationCacheTest::_lru_test() 'cache.access(_tmpFiles[0].cacheTag) == _tmpFiles[0].cachedPath' returned FALSE. ()
D:\\src\\qgcunittest\\ComponentInformationCacheTest.cc(86) : failure location
FAIL!  : ComponentInformationCacheTest::_multi_test() returned FALSE. ()
Totals: 3 passed, 2 failed, 0 skipped, 0 blacklisted, 81ms
********* Finished testing of ComponentInformationCacheTest *********
2026-10-12 09:50:45.000 12168 default: 2 TESTS FAILED!
"""

CRASHED_RUN = """\
********* Start testing of SendMavCommandWithSignallingTest *********
QFATAL : SendMavCommandWithSignailingTest::_performTestCases() ASSERT: "!_mockLink"
Totals: 1 passed, 2 failed, 0 skipped, 0 blacklisted, 60ms
"""


class ParseOutput(unittest.TestCase):

    def test_passing_run(self):
        parsed = rt.parse_output(PASSING_RUN)
        self.assertEqual(parsed["verdict"], "passed")
        self.assertEqual(parsed["suites_passed"], 1)
        self.assertEqual(parsed["suites_failed"], 0)
        self.assertEqual(parsed["failures"], [])

    def test_failing_run(self):
        parsed = rt.parse_output(FAILING_RUN)
        self.assertEqual(parsed["verdict"], "failed")
        self.assertEqual(parsed["suites_passed"], 0)
        self.assertEqual(parsed["suites_failed"], 1)
        self.assertEqual(len(parsed["failures"]), 2)
        self.assertIn("ComponentInformationCacheTest::_lru_test()", parsed["failures"][0])

    def test_crash_without_marker_is_no_verdict(self):
        parsed = rt.parse_output(CRASHED_RUN)
        self.assertEqual(parsed["verdict"], "no-verdict")
        self.assertEqual(parsed["suites_failed"], 1)

    def test_multiple_suites_are_counted(self):
        text = PASSING_RUN + FAILING_RUN
        parsed = rt.parse_output(text)
        self.assertEqual(parsed["suites_passed"], 1)
        self.assertEqual(parsed["suites_failed"], 1)
        # "TESTS FAILED!" takes priority even though "ALL TESTS PASSED" also
        # appears (stress runs can contain both markers).
        self.assertEqual(parsed["verdict"], "failed")


class LiveLines(unittest.TestCase):

    def test_progress_lines_are_live(self):
        for line in ("********* Start testing of X *********",
                     "Totals: 3 passed, 0 failed, 0 skipped, 0 blacklisted, 15ms",
                     "FAIL!  : X::_t() returned FALSE. ()",
                     "QFATAL : X::_t() ASSERT",
                     "2026-10-12 09:54:41 default: ALL TESTS PASSED",
                     "2026-10-12 09:54:41 default: 2 TESTS FAILED!"):
            self.assertTrue(rt.is_live_line(line), line)

    def test_noise_is_not_live(self):
        for line in ("PASS   : X::_t()",
                     "QDEBUG : X::_t() some debug text",
                     "Config: Using QtTest library 5.15.2",
                     "2026-10-12 09:54:41 default: Map Cache in: ..."):
            self.assertFalse(rt.is_live_line(line), line)


class LogPath(unittest.TestCase):

    def test_unique_within_same_second(self):
        with tempfile.TemporaryDirectory() as d:
            first = rt.available_log_path(Path(d), "2026_10_12_000000")
            first.write_text("x", encoding="utf-8")
            second = rt.available_log_path(Path(d), "2026_10_12_000000")
            self.assertNotEqual(first, second)
            self.assertEqual(second.name, "qgc_unittest_2026_10_12_000000_1.log")


class Baseline(unittest.TestCase):

    def test_failure_ids_are_deduped_and_message_free(self):
        ids = rt.failure_ids(FAILING_RUN)
        self.assertEqual(ids, ["ComponentInformationCacheTest::_lru_test",
                               "ComponentInformationCacheTest::_multi_test"])

    def test_failure_ids_empty_without_fail_lines(self):
        self.assertEqual(rt.failure_ids(PASSING_RUN), [])

    def test_classify_splits_new_from_known(self):
        failures = rt.parse_output(FAILING_RUN)["failures"]
        baseline = {"ComponentInformationCacheTest::_lru_test"}
        new, known = rt.classify_failures(failures, baseline)
        self.assertEqual(len(new), 1)
        self.assertIn("_multi_test", new[0])
        self.assertEqual(len(known), 1)
        self.assertIn("_lru_test", known[0])

    def test_empty_baseline_means_everything_is_new(self):
        failures = rt.parse_output(FAILING_RUN)["failures"]
        new, known = rt.classify_failures(failures, set())
        self.assertEqual(len(new), 2)
        self.assertEqual(known, [])

    def test_historical_baseline_unions_logs(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "qgc_unittest_1.log").write_text(FAILING_RUN, encoding="utf-8")
            (root / "qgc_unittest_2.log").write_text(CRASHED_RUN, encoding="utf-8")
            (root / "unrelated.log").write_text(FAILING_RUN, encoding="utf-8")
            baseline = rt.historical_baseline(root)
            self.assertIn("ComponentInformationCacheTest::_lru_test", baseline)
            self.assertIn("ComponentInformationCacheTest::_multi_test", baseline)
            # QFATAL lines are not FAIL! lines: a crash contributes no id.
            self.assertEqual(len(baseline), 2)

    def test_baseline_file_ignores_comments_and_blanks(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "known.txt"
            f.write_text("# comment\n\nFooTest::_bar\n", encoding="utf-8")
            self.assertEqual(rt.load_baseline_file(f), {"FooTest::_bar"})

    def test_baseline_file_missing_raises(self):
        with self.assertRaises(OSError):
            rt.load_baseline_file(Path("/nonexistent/known.txt"))

    def test_known_only_run_counts_as_regression_free(self):
        """Verdict helper: all failures known -> no NEW failures to report."""
        failures = rt.parse_output(FAILING_RUN)["failures"]
        new, _known = rt.classify_failures(
            failures, {"ComponentInformationCacheTest::_lru_test",
                       "ComponentInformationCacheTest::_multi_test"})
        self.assertEqual(new, [])


class Invariants(unittest.TestCase):

    def test_parsing_is_stable(self):
        """Parsing the same output twice yields identical results."""
        once = rt.parse_output(FAILING_RUN)
        self.assertEqual(rt.parse_output(FAILING_RUN), once)

    def test_exit_markers_never_depend_on_exit_code(self):
        """The verdict is text-only: no exit code appears in parse_output's input."""
        # Simulates QGC's shutdown abort: marker says passed, "exit code" was 3.
        parsed = rt.parse_output(PASSING_RUN)
        self.assertEqual(parsed["verdict"], "passed")


if __name__ == "__main__":
    unittest.main(verbosity=2)
