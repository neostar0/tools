#!/usr/bin/env python3
"""Focused unit tests for the Android APK builder."""

import argparse
import importlib.util
import os
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
SPEC = importlib.util.spec_from_file_location(
    "build_android", os.path.join(HERE, "build_android.py"))
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

COMMON_PRI = '''        } else:equals(ANDROID_TARGET_ARCH, x86)  {
            CONFIG += Androidx86Build
            DEFINES += __androidx86__
            message("Android x86 build")
        } else {
            error("Unsupported Android architecture: $${ANDROID_TARGET_ARCH}")
        }
    }

    equals(ANDROID_TARGET_ARCH, arm64-v8a)  {
        ANDROID_TRUE_BITNESS = 64
        ANDROID_VERSION_BITNESS = 66
    } else {
        ANDROID_TRUE_BITNESS = 32
        ANDROID_VERSION_BITNESS = 34
    }
'''

HEADER = '#include "../VideoReceiver/GstVideoReceiver.h"\nclass JoystickManager {};\n'
SOURCE = '    gst_rec = dynamic_cast<GstVideoReceiver*>(v_rec);\n'


def fake_checkout(root):
    os.makedirs(os.path.join(root, "src", "Joystick"))
    open(os.path.join(root, "QGCCommon.pri"), "w").write(COMMON_PRI)
    open(os.path.join(root, "src", "Joystick", "JoystickManager.h"), "w").write(HEADER)
    open(os.path.join(root, "src", "Joystick", "JoystickManager.cc"), "w").write(SOURCE)


class Builder(unittest.TestCase):
    def test_replace_reports_missing_anchor(self):
        with self.assertRaises(RuntimeError):
            MODULE._replace("abc", "zzz", "x", "test")

    def test_x86_overlays_disable_gstreamer_dependency(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as out:
            fake_checkout(root)
            MODULE.write_x86_overlays(root, out)
            common = open(os.path.join(out, "QGCCommon.pri")).read()
            header = open(os.path.join(out, "JoystickManager.h")).read()
            source = open(os.path.join(out, "JoystickManager.cc")).read()
            stub = open(os.path.join(out, "gst_stub.cpp")).read()
        self.assertIn("x86_64 build", common)
        self.assertIn("arm64-v8a)|equals(ANDROID_TARGET_ARCH, x86_64)", common)
        self.assertIn("SOURCES += /project/build/.patches/gst_stub.cpp", common)
        self.assertIn("class GstVideoReceiver;", header)
        self.assertIn("reinterpret_cast<GstVideoReceiver*>", source)
        self.assertIn("gst_amc_jni_set_java_vm", stub)

    def test_build_dir_keeps_legacy_arm64_path(self):
        self.assertEqual(MODULE.build_dir_for("/qgc", "arm64-v8a"),
                         "/qgc/build_android")
        self.assertEqual(MODULE.build_dir_for("/qgc", "x86_64"),
                         "/qgc/build_android_x86_64")

    def test_keystore_password_prefers_environment(self):
        with tempfile.TemporaryDirectory() as root:
            open(os.path.join(root, "build-android.sh"), "w").write(
                "docker run -e ANDROID_KEYSTORE_PASSWORD=localpw image\n")
            with mock.patch.dict(os.environ, {"ANDROID_KEYSTORE_PASSWORD": "envpw"}):
                self.assertEqual(MODULE.keystore_password(root), "envpw")
            with mock.patch.dict(os.environ, {}, clear=True):
                self.assertEqual(MODULE.keystore_password(root), "localpw")

    def test_arm64_command_keeps_video(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as out:
            fake_checkout(root)
            apk = os.path.join(root, "build_android", MODULE.SIGNED_APK)
            os.makedirs(os.path.dirname(apk))
            open(apk, "wb").write(b"apk")
            args = argparse.Namespace(jobs=2, image="img", name="QGC", out=out,
                                      clean=False, x86_video=False)
            with mock.patch.object(MODULE.subprocess, "run",
                                   return_value=mock.Mock(returncode=0)) as run:
                MODULE.build_abi(root, "arm64-v8a", args, "pw")
                command = run.call_args.args[0]
                self.assertIn("ANDROID_ABIS=arm64-v8a", command[-1])
                self.assertNotIn("DISABLE_VIDEOSTREAMING", command[-1])
                self.assertTrue(os.path.isfile(os.path.join(out, "QGC-arm64-v8a.apk")))

    def test_x86_command_disables_video_and_mounts_overlays(self):
        with tempfile.TemporaryDirectory() as root, tempfile.TemporaryDirectory() as out:
            fake_checkout(root)
            apk = os.path.join(root, "build_android_x86_64", MODULE.SIGNED_APK)
            os.makedirs(os.path.dirname(apk))
            open(apk, "wb").write(b"apk")
            args = argparse.Namespace(jobs=2, image="img", name="QGC", out=out,
                                      clean=False, x86_video=False)
            with mock.patch.object(MODULE.subprocess, "run",
                                   return_value=mock.Mock(returncode=0)) as run:
                MODULE.build_abi(root, "x86_64", args, "pw")
                command = run.call_args.args[0]
                self.assertIn("DISABLE_VIDEOSTREAMING", command[-1])
                self.assertIn("ANDROID_ABIS=x86_64", command[-1])
                self.assertTrue(any(".patches/QGCCommon.pri" in item for item in command))
                self.assertTrue(os.path.isfile(os.path.join(out, "QGC-x86_64-novideo.apk")))


if __name__ == "__main__":
    unittest.main(verbosity=2)
