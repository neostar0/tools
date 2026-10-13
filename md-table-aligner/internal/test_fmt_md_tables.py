#!/usr/bin/env python3
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Regression tests for fmt_md_tables.

Run with:
    python3 test_fmt_md_tables.py
    python3 -m unittest discover . -v
"""

import io
import os
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fmt_md_tables as fmt  # noqa: E402


def rows_of(text):
    """Return the table lines of `text`."""
    return [line for line in text.splitlines() if line.strip().startswith("|")]


def table_rows(text):
    """Return only the rows the formatter treated as tables.

    `rows_of` also picks up pipes inside fenced code blocks, which the
    formatter deliberately leaves alone.
    """
    return [line
            for kind, payload in fmt.iter_blocks(text.splitlines())
            if kind == fmt.TABLE
            for line in payload]


class TableDetectionTestCase(unittest.TestCase):

    def test_basic_table_is_aligned(self):
        out = fmt.process("| a | bb | ccc |\n| --- | --- | --- |\n| 1 | 2 | 3 |\n")
        self.assertEqual(out, "| a | bb | ccc |\n| - | -- | --- |\n| 1 | 2  | 3   |\n")

    def test_block_without_separator_is_untouched(self):
        text = "| a | b |\n| 1 | 2 |\n"
        self.assertEqual(fmt.process(text), text)

    def test_stray_pipe_line_is_untouched(self):
        text = "prose\n| a | b |\nmore prose\n"
        self.assertEqual(fmt.process(text), text)

    def test_code_fence_is_skipped(self):
        text = "```\n| a | b |\n| --- | --- |\n| 1 | 2 |\n```\n"
        self.assertEqual(fmt.process(text), text)

    def test_tilde_fence_is_skipped(self):
        text = "~~~\n| a | b |\n| --- | --- |\n| 1 | 2 |\n~~~\n"
        self.assertEqual(fmt.process(text), text)

    def test_table_after_fence_is_processed(self):
        out = fmt.process("```\nnot | a table\n```\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n")
        self.assertIn("```\nnot | a table\n```\n", out)
        self.assertEqual(len({fmt.rendered_width(l) for l in rows_of(out)}), 1)

    def test_exotic_line_mark_is_not_a_newline(self):
        text = "line1\x0bline2\n"
        self.assertEqual(fmt.process(text), text)


class WidthTestCase(unittest.TestCase):

    def test_cjk_width_is_double(self):
        self.assertEqual(fmt.display_width("中文"), 4)
        self.assertEqual(fmt.display_width("ab"), 2)

    def test_combining_marks_are_zero_width(self):
        self.assertEqual(fmt.display_width("é"), 1)

    def test_cjk_table_is_aligned(self):
        out = fmt.process("| 中文欄位 | 值 |\n| --- | --- |\n| 測試 | 1 |\n")
        self.assertEqual(out, "| 中文欄位 | 值 |\n| -------- | -- |\n| 測試     | 1  |\n")

    def test_escaped_pipe_is_one_column(self):
        out = fmt.process("| a | b |\n| --- | --- |\n| x \\| y | 2 |\n")
        self.assertEqual(out, "| a     | b |\n| ----- | - |\n| x \\| y | 2 |\n")
        self.assertEqual(fmt.rendered_width("x \\| y"), 5)

    def test_empty_cells_are_kept(self):
        out = fmt.process("| a | b |\n| --- | --- |\n| 1 |  |\n|  | 2 |\n")
        self.assertEqual(rows_of(out)[2], "| 1 |   |")
        self.assertEqual(rows_of(out)[3], "|   | 2 |")


class AlignmentMarkerTestCase(unittest.TestCase):

    def test_markers_are_preserved(self):
        out = fmt.process("| a | bb | ccc |\n| :--- | :---: | ---: |\n| 1 | 2 | 3 |\n")
        self.assertEqual(out, "| a  | bb   | ccc  |\n| :- | :--: | ---: |\n| 1  | 2    | 3    |\n")

    def test_marker_width_is_accounted_for(self):
        out = fmt.process("| a | bb |\n| :--- | ---: |\n| 1 | 2 |\n")
        self.assertEqual(len({fmt.rendered_width(l) for l in rows_of(out)}), 1)


class RaggedTableTestCase(unittest.TestCase):

    def test_rows_are_zero_filled(self):
        out = fmt.process("| a | b |\n| --- | --- |\n| 1 | 2 | 3 | 4 |\n| longer | x |\n")
        widths = {fmt.rendered_width(line) for line in rows_of(out)}
        self.assertEqual(len(widths), 1)

    def test_no_trailing_pipe(self):
        out = fmt.process("| a | b\n| --- | ---\n| 1 | 2\n")
        self.assertEqual(len({fmt.rendered_width(l) for l in rows_of(out)}), 1)


class ProcessInvariantTestCase(unittest.TestCase):
    """Invariants that must hold for every sample used in this file."""

    SAMPLES = [
        "| a | bb | ccc |\n| --- | --- | --- |\n| 1 | 2 | 3 |\n",
        "| 中文欄位 | 值 |\n| --- | --- |\n| 測試 | 1 |\n",
        "| a | bb | ccc |\n| :--- | :---: | ---: |\n| 1 | 2 | 3 |\n",
        "| 中文 | bb |\n|:---:|:---:|\n| 測試 | 2 |\n",
        "| a | b |\n| --- | --- |\n| 1 | 2 | 3 | 4 |\n| longer cell here | x |\n",
        "| a | b |\n| --- | --- |\n| x \\| y | 2 |\n",
        "| a | b |\n| --- | --- |\n| 1 |  |\n|  | 2 |\n",
        "| a |  |\n| --- | --- |\n| b |  |\n",
        "```\n| a | b |\n| --- | --- |\n| 1 | 2 |\n```\n",
        "| a | b\n| --- | ---\n| 1 | 2\n",
    ]

    def test_idempotent_is_required(self):
        for sample in self.SAMPLES:
            with self.subTest(sample=sample.splitlines()[0]):
                once = fmt.process(sample)
                self.assertEqual(fmt.process(once), once)

    def test_aligned_width_is_uniform(self):
        for sample in self.SAMPLES:
            with self.subTest(sample=sample.splitlines()[0]):
                widths = {fmt.rendered_width(line) for line in table_rows(fmt.process(sample))}
                self.assertLessEqual(len(widths), 1)

    def test_check_accepts_every_output(self):
        # Whatever we write must pass our own --check run afterwards.
        for sample in self.SAMPLES:
            with self.subTest(sample=sample.splitlines()[0]):
                self.assertTrue(fmt.check("sample", fmt.process(sample)))


class FileHandlingTestCase(unittest.TestCase):

    def make(self, text, newline=""):
        handle = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False,
                                             encoding="utf-8", newline="")
        handle.write(text)
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        return handle.name

    def test_crlf_is_preserved(self):
        source = self.make("| a | b |\n| --- | --- |\n| 1 | 2 |\n")
        with open(source, "w", encoding="utf-8", newline="\r\n") as handle:
            handle.write("| a | b |\n| --- | --- |\n| 1 | 2 |\n")
        original = fmt.read(source)
        self.assertIn("\r\n", original)

        target = fmt.stamped_path(source, "_t", None)
        self.addCleanup(os.unlink, target)
        fmt.write(target, fmt.process(original), original)

        with io.open(target, encoding="utf-8", newline="") as handle:
            result = handle.read()
        self.assertIn("\r\n", result)
        self.assertNotIn("\n", result.replace("\r\n", ""))

    def test_stamped_path_format(self):
        # A relative input is resolved, so the copy lands next to the source.
        expected = os.path.join(os.getcwd(), "report_2026-1002-1058.md")
        self.assertEqual(fmt.stamped_path("report.md", "_2026-1002-1058", None), expected)

    def test_stamped_path_adds_md_when_missing(self):
        self.assertTrue(fmt.stamped_path("report", "_x", None).endswith("report_x.md"))

    def test_stamped_path_honours_output_dir(self):
        self.assertEqual(fmt.stamped_path("/a/report.md", "_x", "/out"),
                         os.path.join("/out", "report_x.md"))


class CommandLineTestCase(unittest.TestCase):

    SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fmt_md_tables.py")

    def run_cli(self, *args):
        return subprocess.run([sys.executable, self.SCRIPT] + list(args),
                              capture_output=True, text=True)

    def test_default_writes_a_copy_and_keeps_the_source(self):
        handle = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8")
        handle.write("| a | b |\n| --- | --- |\n| 1 | 2 |\n")
        handle.close()
        self.addCleanup(os.unlink, handle.name)
        with io.open(handle.name, encoding="utf-8", newline="") as reader:
            before = reader.read()

        result = self.run_cli(handle.name)
        self.assertEqual(result.returncode, 0, result.stderr)

        produced = fmt.stamped_path(handle.name, fmt.DEFAULT_SUFFIX, None)
        self.addCleanup(os.unlink, produced)
        self.assertTrue(os.path.exists(produced))
        with io.open(handle.name, encoding="utf-8", newline="") as reader:
            self.assertEqual(reader.read(), before)

    def test_check_reports_misaligned_tables(self):
        handle = tempfile.NamedTemporaryFile("w", suffix=".md", delete=False, encoding="utf-8")
        handle.write("| a | b |\n| --- | --- |\n| 1 | 2 |\n")
        handle.close()
        self.addCleanup(os.unlink, handle.name)

        result = self.run_cli("--check", handle.name)
        self.assertEqual(result.returncode, 1)
        self.assertIn(":1:", result.stdout)  # line numbers are 1-based

        self.run_cli("--in-place", handle.name)
        self.assertEqual(self.run_cli("--check", handle.name).returncode, 0)

    def test_missing_file_reports_one_line_not_a_traceback(self):
        result = self.run_cli(os.path.join(tempfile.gettempdir(), "no-such-file.md"))
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("cannot read", result.stderr)

    def test_non_utf8_file_reports_one_line_not_a_traceback(self):
        handle = tempfile.NamedTemporaryFile("wb", suffix=".md", delete=False)
        handle.write(b"\xff\xfe not utf-8\n")
        handle.close()
        self.addCleanup(os.unlink, handle.name)

        result = self.run_cli(handle.name)
        self.assertEqual(result.returncode, 1)
        self.assertNotIn("Traceback", result.stderr)
        self.assertIn("cannot read", result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
