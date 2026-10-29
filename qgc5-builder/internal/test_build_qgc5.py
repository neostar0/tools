#!/usr/bin/env python3
"""Unit tests for build_qgc5.py (run directly or with unittest discover)."""

from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

import build_qgc5 as tool


def make_qgc5(root: Path) -> Path:
    (root / "CMakeLists.txt").write_text(
        "project(QGroundControl)\n", encoding="utf-8"
    )
    docker_dir = root / "deploy/docker"
    docker_dir.mkdir(parents=True)
    (docker_dir / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    (docker_dir / "variants.json").write_text(
        json.dumps(
            {
                "variants": [
                    {
                        "id": "ubuntu",
                        "target": "linux",
                        "image": "qgc-ubuntu-docker",
                        "fuse": True,
                        "build_args": {"BASE_REF": "example"},
                    },
                    {
                        "id": "aarch64",
                        "target": "linux-cross",
                        "image": "qgc-aarch64-docker",
                        "fuse": False,
                        "build_args": {},
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    return root


class RootDetection(unittest.TestCase):
    def test_finds_qgc5_from_subdirectory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_qgc5(Path(tmp))
            subdir = root / "src/Foo"
            subdir.mkdir(parents=True)
            self.assertEqual(tool.find_root(subdir), root.resolve())

    def test_rejects_qgc4_with_a_pointer_to_build_qgc(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "qgroundcontrol.pro").write_text("", encoding="utf-8")
            with self.assertRaises(tool.UsageError) as caught:
                tool.require_root(root)
            self.assertIn("build-qgc", str(caught.exception))

    def test_rejects_unrelated_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(tool.UsageError):
                tool.require_root(Path(tmp))


class Variants(unittest.TestCase):
    def test_loads_variants_by_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_qgc5(Path(tmp))
            variants = tool.load_variants(root)
            self.assertEqual(sorted(variants), ["aarch64", "ubuntu"])
            self.assertEqual(variants["ubuntu"]["target"], "linux")

    def test_rejects_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_qgc5(Path(tmp))
            (root / tool.VARIANTS_FILE).write_text("{", encoding="utf-8")
            with self.assertRaises(tool.UsageError):
                tool.load_variants(root)

    def test_rejects_variant_without_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_qgc5(Path(tmp))
            (root / tool.VARIANTS_FILE).write_text(
                json.dumps({"variants": [{"id": "x", "target": "linux"}]}),
                encoding="utf-8",
            )
            with self.assertRaises(tool.UsageError):
                tool.load_variants(root)


class Commands(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = make_qgc5(Path(self.tmp.name))
        self.variant = tool.load_variants(self.root)["ubuntu"]

    def test_image_command_uses_target_args_and_tag(self) -> None:
        command = tool.build_image_command(
            self.root, self.variant, "custom:tag", rebuild=True
        )
        self.assertIn("--target", command)
        self.assertEqual(command[command.index("--target") + 1], "linux")
        self.assertIn("BASE_REF=example", command)
        self.assertIn("--no-cache", command)
        self.assertEqual(command[-3:], ["-t", "custom:tag", str(self.root)])

    def test_run_command_maps_host_uid_jobs_and_fuse(self) -> None:
        build_dir = self.root / "build"
        command = tool.run_build_command(
            self.root,
            build_dir,
            self.variant,
            "qgc-ubuntu-docker",
            "Debug",
            8,
            clean=True,
        )
        if hasattr(os, "getuid"):
            self.assertIn(f"{os.getuid()}:{os.getgid()}", command)
        self.assertIn("JOBS=8", command)
        self.assertIn("CLEAN_BUILD=1", command)
        self.assertIn("apparmor:unconfined", command)
        self.assertIn(f"{self.root}:/project/source", command)
        self.assertIn(f"{build_dir}:/project/build", command)
        self.assertEqual(command[-2:], ["qgc-ubuntu-docker", "Debug"])

    def test_non_fuse_variant_omits_fuse_options(self) -> None:
        variant = tool.load_variants(self.root)["aarch64"]
        command = tool.run_build_command(
            self.root,
            self.root / "build-aarch64",
            variant,
            "qgc-aarch64-docker",
            "Release",
            4,
            clean=False,
        )
        self.assertNotIn("--device", command)
        self.assertNotIn("apparmor:unconfined", command)

    def test_aarch64_uses_its_own_default_build_dir(self) -> None:
        self.assertEqual(
            tool.default_build_dir(self.root, "aarch64"),
            self.root / "build-aarch64",
        )
        self.assertEqual(
            tool.default_build_dir(self.root, "ubuntu"), self.root / "build"
        )


class RunHints(unittest.TestCase):
    def test_reports_apprun_and_appimage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            build_dir = Path(tmp)
            (build_dir / "AppRun").write_text("", encoding="utf-8")
            (build_dir / "QGroundControl-x86_64.AppImage").write_text(
                "", encoding="utf-8"
            )
            hints = tool.run_hints(build_dir)
            self.assertTrue(any("AppImage:" in hint for hint in hints))
            self.assertTrue(any("run-qgc5" in hint for hint in hints))

    def test_empty_build_dir_has_no_hints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(tool.run_hints(Path(tmp)), [])


class Arguments(unittest.TestCase):
    def test_parses_common_options(self) -> None:
        args = tool.parse_args(
            ["/tmp/qgc", "-b", "Debug", "--variant", "debian", "-j", "2", "--clean"]
        )
        self.assertEqual(args.root, "/tmp/qgc")
        self.assertEqual(args.build_type, "Debug")
        self.assertEqual(args.variant, "debian")
        self.assertEqual(args.jobs, 2)
        self.assertTrue(args.clean)

    def test_rejects_bad_values(self) -> None:
        for argv in (
            ["--build-type", "Nope"],
            ["--jobs", "0"],
            ["--jobs", "-1"],
            ["a", "--root", "b"],
            ["--bogus"],
        ):
            with self.subTest(argv=argv), self.assertRaises(tool.UsageError):
                tool.parse_args(argv)


class EntryPoints(unittest.TestCase):
    def test_help_prints_usage(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(tool.main(["--help"]), 0)
        self.assertIn("Usage:", output.getvalue())

    def test_list_variants_needs_no_docker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_qgc5(Path(tmp))
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(tool.main([str(root), "--list-variants"]), 0)
            self.assertIn("ubuntu", output.getvalue())
            self.assertIn("aarch64", output.getvalue())

    def test_unknown_variant_is_a_usage_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = make_qgc5(Path(tmp))
            errors = io.StringIO()
            with contextlib.redirect_stderr(errors):
                self.assertEqual(tool.main([str(root), "--variant", "nope"]), 2)
            self.assertIn("unknown variant", errors.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
