#!/usr/bin/env python3
"""Unit tests for qgc4-smoke's log analysis (the pure-function core).

Run: python3 internal/test_smoke_qgc.py
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import smoke_qgc as sq

# Real lines from qgc_2026_10_12_022222.log (QGC's launcher output format).
TYPE_ERROR = ("2026-10-12 02:22:29.354 20960 default: qrc:/qml/QGroundControl/"
              "AiseedQml/AiseedMissionInfoPanel.qml:296: TypeError: Cannot read property 'command' of null")
REFERENCE_ERROR = ("2026-10-12 02:22:33.954 20960 default: qrc:/qml/QGroundControl/"
                   "FlightDisplay/LeftButtonsGroup.qml:81: ReferenceError: _activeVehicle is not defined")
BINDING_LOOP = ("2026-10-12 02:22:30.000 20960 default: qrc:/qml/Window.qml:12:5: "
                "Binding loop detected for property \"width\"")
MODULE_MISSING = ("2026-10-12 02:22:30.000 20960 default: qrc:/qml/Main.qml:3:1: "
                  "module \"QtQuick.Controls\" is not installed")
SYNTAX_ERROR = ("2026-10-12 02:22:30.000 20960 default: qrc:/qml/Bad.qml:7:1: "
                "SyntaxError: Unexpected token")
INFO_LINE = "2026-10-12 02:22:29.100 20960 default: QGroundControl app started"
PARAM_WARNING = ("2026-10-12 02:22:29.200 20960 default: ParameterManagerLog: "
                 "No missing parameters for vehicle 1")
ENGINE_FAILURE = "2026-10-12 02:22:29.000 20960 default: QQmlApplicationEngine failed to load object"


class SignatureOf(unittest.TestCase):

    def test_type_error_is_captured(self):
        self.assertEqual(
            sq.signature_of(TYPE_ERROR),
            "qrc:/qml/QGroundControl/AiseedQml/AiseedMissionInfoPanel.qml: "
            "TypeError: Cannot read property 'command' of null")

    def test_reference_error_is_captured(self):
        self.assertIn("ReferenceError: _activeVehicle is not defined",
                      sq.signature_of(REFERENCE_ERROR))

    def test_binding_loop_is_captured(self):
        self.assertIn("Binding loop", sq.signature_of(BINDING_LOOP))

    def test_missing_module_is_captured(self):
        self.assertIn("is not installed", sq.signature_of(MODULE_MISSING))

    def test_syntax_error_is_captured(self):
        self.assertIn("SyntaxError", sq.signature_of(SYNTAX_ERROR))

    def test_line_numbers_are_dropped_from_signature(self):
        moved = TYPE_ERROR.replace("AiseedMissionInfoPanel.qml:296:",
                                   "AiseedMissionInfoPanel.qml:310:")
        self.assertEqual(sq.signature_of(TYPE_ERROR), sq.signature_of(moved))

    def test_column_numbers_are_dropped_from_message(self):
        sig = sq.signature_of(BINDING_LOOP)
        self.assertNotIn('"width" 12', sig)  # message must not keep 12:5:
        self.assertTrue(sig.endswith('Binding loop detected for property "width"'))

    def test_info_line_is_ignored(self):
        self.assertIsNone(sq.signature_of(INFO_LINE))

    def test_non_qml_warning_is_ignored(self):
        self.assertIsNone(sq.signature_of(PARAM_WARNING))

    def test_engine_failure_is_a_signature(self):
        self.assertEqual(sq.signature_of(ENGINE_FAILURE), ENGINE_FAILURE.split("default: ", 1)[1])

    def test_empty_line_is_ignored(self):
        self.assertIsNone(sq.signature_of("   "))


class ExtractSignatures(unittest.TestCase):

    def test_counts_duplicates(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "qgc_test.log"
            log.write_text(TYPE_ERROR + "\n" + TYPE_ERROR + "\n" + INFO_LINE + "\n",
                           encoding="utf-8")
            self.assertEqual(sq.extract_signatures(log), {sq.signature_of(TYPE_ERROR): 2})

    def test_corrupt_bytes_do_not_crash(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "qgc_test.log"
            log.write_bytes(b"\xff\xfe invalid \x00 bytes\n" + TYPE_ERROR.encode())
            self.assertEqual(len(sq.extract_signatures(log)), 1)


class Baseline(unittest.TestCase):

    def test_load_baseline_file_skips_comments_and_blanks(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "baseline.txt"
            f.write_text("# comment\n\nqrc:/a.qml: TypeError: x\n", encoding="utf-8")
            self.assertEqual(sq.load_baseline_file(f), {"qrc:/a.qml: TypeError: x"})

    def test_historical_baseline_unions_logs(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "qgc_2026_01_01_000000.log").write_text(TYPE_ERROR + "\n", encoding="utf-8")
            (root / "qgc_2026_01_02_000000.log").write_text(REFERENCE_ERROR + "\n", encoding="utf-8")
            (root / "notes.txt").write_text("not a log", encoding="utf-8")
            base = sq.historical_baseline(root)
            self.assertEqual(len(base), 2)


class FindNewLog(unittest.TestCase):

    def test_finds_log_created_after_launch(self):
        import os
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            old = root / "qgc_2026_01_01_000000.log"
            old.write_text("old", encoding="utf-8")
            new = root / "qgc_2026_01_02_000000.log"
            new.write_text("new", encoding="utf-8")
            started = os.path.getmtime(old) + 10
            os.utime(new, (started + 5, started + 5))
            found = sq.find_new_log(root, {old.name}, started)
            self.assertEqual(found, new)

    def test_no_new_log_returns_none(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.assertIsNone(sq.find_new_log(root, set(), 0))


class Invariants(unittest.TestCase):

    def test_signatures_are_stable(self):
        """Extracting twice from the same content yields the same dict."""
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "qgc_test.log"
            log.write_text("\n".join([TYPE_ERROR, REFERENCE_ERROR, INFO_LINE]),
                           encoding="utf-8")
            once = sq.extract_signatures(log)
            self.assertEqual(sq.extract_signatures(log), once)


if __name__ == "__main__":
    unittest.main(verbosity=2)
