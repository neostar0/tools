#!/usr/bin/env python3
"""Repo-wide verification: run every package's tests and audit every package.

Direct:   python3 test_repo.py
Discover: python3 -m unittest discover -p "test_*.py"    (from the repo root)

Scans the whole directory: each package's unit suite (subprocess), the
markdown table check on every .md, README/SKILL contract audits, .cmd/.bat
CRLF, and a usage smoke (each entry's documented trigger) of the .sh
entries that print usage.
"""
import glob
import os
import re
import shutil
import subprocess
import sys
import unittest

ROOT = os.path.dirname(os.path.abspath(__file__))
FMT = os.path.join(ROOT, "md-table-aligner", "internal", "fmt_md_tables.py")
USAGE_TRIGGERS = {  # .sh basename -> (argv, expected exit code) for its usage screen
    "launch-qgc.sh": (["--help"], 0),
    "stop-process.sh": ([], 2),
}


def rel(path):
    return os.path.relpath(path, ROOT)


def read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=120)


def packages():
    return sorted(
        d for d in glob.glob(os.path.join(ROOT, "*"))
        if os.path.isdir(d)
        and not os.path.basename(d).startswith(".")
        and os.path.basename(d) != "__pycache__"
    )


def skill_files():
    return sorted(glob.glob(os.path.join(ROOT, "*", "SKILL.md")))


def md_files():
    out = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        dirnames[:] = [d for d in dirnames if d not in (".git", "__pycache__")]
        out += [os.path.join(dirpath, f) for f in filenames if f.endswith(".md")]
    return sorted(out)


class PackageSuites(unittest.TestCase):

    def test_all_package_tests_pass(self):
        tests = sorted(glob.glob(os.path.join(ROOT, "*", "internal", "test_*.py")))
        self.assertTrue(tests, "no package unit tests found")
        for t in tests:
            with self.subTest(suite=rel(t)):
                r = run([sys.executable, t])
                self.assertEqual(r.returncode, 0, rel(t) + "\n" + r.stdout + r.stderr)


class MarkdownDocs(unittest.TestCase):

    def test_every_md_passes_table_check(self):
        self.assertTrue(os.path.exists(FMT), "fmt_md_tables.py missing")
        for md in md_files():
            with self.subTest(md=rel(md)):
                r = run([sys.executable, FMT, "--check", md])
                self.assertEqual(r.returncode, 0, rel(md) + "\n" + r.stdout + r.stderr)


class Readmes(unittest.TestCase):

    def test_every_tool_has_a_readme(self):
        for pkg in packages():
            with self.subTest(tool=os.path.basename(pkg)):
                self.assertTrue(os.path.exists(os.path.join(pkg, "README.md")),
                                os.path.basename(pkg) + " has no README.md at the tool root")

    def test_readme_documents_exit_codes(self):
        for readme in sorted(glob.glob(os.path.join(ROOT, "*", "README.md"))):
            with self.subTest(readme=rel(readme)):
                self.assertRegex(read(readme), r"(?i)exit code")

    def test_readme_never_links_skill_md(self):
        for readme in sorted(glob.glob(os.path.join(ROOT, "*", "README.md"))):
            with self.subTest(readme=rel(readme)):
                text = read(readme)
                self.assertNotIn("SKILL.md", text)


class Skills(unittest.TestCase):
    # SKILL.md is optional (spec section 3): audits apply only when present.

    def test_skill_line_budget(self):
        for skill in skill_files():
            with self.subTest(skill=rel(skill)):
                n = len(read(skill).splitlines())
                self.assertLess(n, 60, "%s has %d lines" % (rel(skill), n))

    def test_skill_documents_exit_codes_and_commands(self):
        for skill in skill_files():
            text = read(skill)
            with self.subTest(skill=rel(skill)):
                self.assertIn("## Commands", text)
                self.assertRegex(text, r"(?i)exit code")

    def test_skill_notes_pointer_resolves(self):
        for skill in skill_files():
            text = read(skill)
            with self.subTest(skill=rel(skill)):
                if "internal/NOTES.md" in text:
                    notes = os.path.join(os.path.dirname(skill), "internal", "NOTES.md")
                    self.assertTrue(os.path.exists(notes),
                                    rel(skill) + " points at a missing NOTES.md")

    def test_skill_entry_references_exist(self):
        known = set()
        for pkg in packages():
            for dirpath, _, files in os.walk(pkg):
                known.update(f for f in files if f.endswith((".cmd", ".bat", ".sh")))
        for skill in skill_files():
            text = read(skill)
            for ref in re.findall(r"`([\w.-]+\.(?:cmd|bat|sh))`", text):
                with self.subTest(skill=rel(skill), ref=ref):
                    self.assertIn(ref, known,
                                  rel(skill) + " references missing entry " + ref)


class Entries(unittest.TestCase):

    def sh_entries(self):
        return sorted(glob.glob(os.path.join(ROOT, "*", "*.sh")))

    def win_entries(self):
        return sorted(
            glob.glob(os.path.join(ROOT, "*", "*.cmd"))
            + glob.glob(os.path.join(ROOT, "*", "*.bat"))
        )

    def usage_printers(self):
        return sorted(p for p in self.sh_entries() + self.win_entries()
                      if "usage.md" in read(p))

    def test_every_package_has_a_windows_entry(self):
        for pkg in packages():
            with self.subTest(pkg=os.path.basename(pkg)):
                self.assertTrue(glob.glob(os.path.join(pkg, "*.cmd"))
                                or glob.glob(os.path.join(pkg, "*.bat")),
                                os.path.basename(pkg) + " has no .cmd/.bat entry at the package root")

    def test_windows_entries_are_crlf_only(self):
        for entry in self.win_entries():
            with self.subTest(entry=rel(entry)):
                with open(entry, "rb") as fh:
                    data = fh.read()
                self.assertNotIn(b"\n", data.replace(b"\r\n", b""),
                                 rel(entry) + " has LF-only lines")

    def test_bat_entries_take_no_arguments(self):
        for bat in sorted(glob.glob(os.path.join(ROOT, "*", "*.bat"))):
            text = read(bat)
            with self.subTest(bat=rel(bat)):
                self.assertNotIn("%~1", text,
                                 rel(bat) + " reads arguments (that is what .cmd is for)")
                self.assertNotIn("%*", text,
                                 rel(bat) + " reads arguments (that is what .cmd is for)")

    def test_usage_printers_have_a_usage_file(self):
        for entry in self.usage_printers():
            with self.subTest(entry=rel(entry)):
                usage = os.path.join(os.path.dirname(entry), "internal", "usage.md")
                self.assertTrue(os.path.exists(usage),
                                rel(entry) + " prints usage but internal/usage.md is missing")

    def test_sh_syntax(self):
        if not shutil.which("bash"):
            self.skipTest("bash not available")
        for sh in self.sh_entries():
            with self.subTest(sh=rel(sh)):
                r = run(["bash", "-n", sh])
                self.assertEqual(r.returncode, 0, r.stderr)

    def test_sh_usage_is_reachable(self):
        if not shutil.which("bash"):
            self.skipTest("bash not available")
        names = sorted(os.path.basename(p) for p in self.usage_printers()
                       if p.endswith(".sh"))
        self.assertEqual(names, sorted(USAGE_TRIGGERS),
                         "USAGE_TRIGGERS out of sync with the usage-printing .sh entries")
        for name, (argv, want) in sorted(USAGE_TRIGGERS.items()):
            matches = glob.glob(os.path.join(ROOT, "*", name))
            with self.subTest(sh=name):
                self.assertEqual(len(matches), 1, name)
                r = run(["bash", matches[0]] + argv)
                self.assertEqual(r.returncode, want, r.stdout + r.stderr)
                self.assertIn("Usage", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
