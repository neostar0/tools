#!/usr/bin/env python3
"""
QGC Nav Bar Tester
==================

A small Tkinter GUI MAVLink vehicle simulator for exercising the AiSeed/QGC
navigation bar and parameter plumbing.

It can:
  * connect to QGC over UDP, TCP (server) or a serial port
  * send heartbeat / battery / GPS / link RSSI / RC RSSI / status text
  * simulate armed state, landed state, flight mode and pre-arm health
  * answer QGC parameter requests and remember parameters set by QGC
  * persist remembered parameters and simulator values as JSON
  * send PARAM_VALUE messages for parameters added or edited in the GUI

Typical UDP usage:
  1. Start QGC with its normal UDP link listening on port 14550.
  2. Run:
       python3 tools/qgc_navbar_tester.py
  3. Keep transport = UDP, QGC port = 14550, bind port = 14555.
  4. Press "Connect". The tool sends a heartbeat to QGC and QGC should
     create a vehicle entry.

If your QGC UDP link uses another port, change "QGC port" to that value.
For a TCP link, use "TCP server" and connect QGC to this tool's bind port.
For serial, use "Serial" and select the port/baud.

Install dependencies:
    python3 -m pip install pymavlink pyserial

The Wi-Fi/2.4G item in the AiSeed nav bar is fed by the Microhard manager,
not by standard MAVLink, so this tool cannot drive that status. Everything
else in the nav bar (battery, GPS count, telemetry/RC RSSI, armed/mode text,
messages and parameters) is testable here.
"""

from __future__ import annotations

import argparse
import json
import os
import queue
import socket
import sys
import threading
import time
from collections import OrderedDict, deque
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Deque, Dict, List, Optional, Tuple

try:
    import tkinter as tk
    from tkinter import filedialog, messagebox, scrolledtext, ttk
except Exception as exc:  # pragma: no cover - depends on platform packages
    print("Tkinter is required: %s" % exc, file=sys.stderr)
    raise

try:
    from pymavlink.dialects.v20 import ardupilotmega as mavlink2
except ImportError as exc:  # pragma: no cover
    print(
        "pymavlink is required.\n"
        "Install it with: python3 -m pip install pymavlink pyserial\n"
        "Original error: %s" % exc,
        file=sys.stderr,
    )
    raise SystemExit(1)

try:
    import serial as pyserial
except ImportError:  # serial transport is optional
    pyserial = None


APP_NAME = "QGC Nav Bar Tester"
DEFAULT_STATE_PATH = Path.home() / ".qgc_navbar_tester" / "state.json"
DEFAULT_UDP_HOST = "127.0.0.1"
DEFAULT_UDP_PORT = 14550
DEFAULT_BIND_PORT = 14555
DEFAULT_SYSID = 42
DEFAULT_COMPID = 1
MAX_PARAM_NAME = 16
DEFAULT_PARAM_REPLY_DELAY = 3.0

# MAVLink parameter type names <-> enum values.
PARAM_TYPES: "OrderedDict[str, int]" = OrderedDict(
    [
        ("REAL32", 9),
        ("INT32", 6),
        ("UINT8", 1),
        ("INT8", 3),
        ("UINT16", 2),
        ("INT16", 4),
        ("UINT32", 5),
        ("REAL64", 10),
        ("UINT64", 8),
        ("INT64", 7),
    ]
)
PARAM_TYPE_NAMES = {value: name for name, value in PARAM_TYPES.items()}
PARAM_REAL_TYPES = {PARAM_TYPES["REAL32"], PARAM_TYPES["REAL64"]}

DEFAULT_PARAMS: List[Tuple[str, Any, str]] = [
    ("BAT_LOW_THR", 0.15, "REAL32"),
    ("BAT_CRIT_THR", 0.07, "REAL32"),
    ("RTL_ALT", 1500, "INT32"),
    ("RTL_SPEED", 0.0, "REAL32"),
    ("WPNAV_SPEED", 500.0, "REAL32"),
    ("CP_DIST", -1.0, "REAL32"),
    ("COM_OBS_AVOID", 0, "INT32"),
    ("MPC_XY_VEL_MAX", 5.0, "REAL32"),
    ("EKF2_GPS_CTRL", 7, "INT32"),
    ("SYSID_THISMAV", 1, "INT32"),
]

# Addresses used by the simulator. Positions around Taipei 101 by default.
DEFAULT_STATE: Dict[str, Any] = {
    "vehicle_type": int(getattr(mavlink2, "MAV_TYPE_QUADROTOR", 2)),
    "autopilot": int(getattr(mavlink2, "MAV_AUTOPILOT_PX4", 12)),
    "armed": False,
    "landed_state": int(getattr(mavlink2, "MAV_LANDED_STATE_ON_GROUND", 1)),
    "prearm_ok": True,
    "flight_mode_name": "Position",
    "custom_mode": 3 << 16,  # PX4 POSCTL
    "battery_percent": 100,
    "battery_voltage": 16.8,
    "battery_current": 5.0,
    "battery_charging": False,
    "gps_fix": int(getattr(mavlink2, "GPS_FIX_TYPE_3D_FIX", 3)),
    "gps_sats": 12,
    "lat": 25.033964,
    "lon": 121.564468,
    "alt": 30.0,
    "link_rssi": 80,
    "remote_rssi": 80,
    "rc_rssi": 80,
}

VEHICLE_TYPES = OrderedDict(
    [
        ("Quadrotor", int(getattr(mavlink2, "MAV_TYPE_QUADROTOR", 2))),
        ("Fixed wing", int(getattr(mavlink2, "MAV_TYPE_FIXED_WING", 1))),
        ("VTOL quadrotor", int(getattr(mavlink2, "MAV_TYPE_VTOL_QUADROTOR", 20))),
        ("VTOL tiltrotor", int(getattr(mavlink2, "MAV_TYPE_VTOL_TILTROTOR", 21))),
        ("Ground rover", int(getattr(mavlink2, "MAV_TYPE_GROUND_ROVER", 10))),
        ("Boat", int(getattr(mavlink2, "MAV_TYPE_SURFACE_BOAT", 11))),
    ]
)
VEHICLE_TYPE_NAMES = {value: name for name, value in VEHICLE_TYPES.items()}

AUTOPILOTS = OrderedDict(
    [
        ("PX4", int(getattr(mavlink2, "MAV_AUTOPILOT_PX4", 12))),
        ("ArduPilot", int(getattr(mavlink2, "MAV_AUTOPILOT_ARDUPILOTMEGA", 3))),
    ]
)
AUTOPILOT_NAMES = {value: name for name, value in AUTOPILOTS.items()}

# PX4 custom mode encoding: main mode in bits 16..23, sub mode in 24..31.
def _px4_mode(main: int, sub: int = 0) -> int:
    return ((sub & 0xFF) << 24) | ((main & 0xFF) << 16)


PX4_MODES = OrderedDict(
    [
        ("Position", _px4_mode(3)),
        ("Altitude", _px4_mode(2)),
        ("Manual", _px4_mode(1)),
        ("Stabilized", _px4_mode(7)),
        ("Acro", _px4_mode(5)),
        ("Offboard", _px4_mode(6)),
        ("Mission", _px4_mode(4, 4)),
        ("Hold", _px4_mode(4, 3)),
        ("Return", _px4_mode(4, 5)),
        ("Takeoff", _px4_mode(4, 2)),
        ("Land", _px4_mode(4, 6)),
        ("Follow", _px4_mode(4, 8)),
    ]
)

APM_MODES = OrderedDict(
    [
        ("Loiter", 5),
        ("Stabilize", 0),
        ("AltHold", 2),
        ("Auto", 3),
        ("Guided", 4),
        ("RTL", 6),
        ("Land", 9),
        ("PosHold", 16),
        ("Brake", 17),
        ("Smart RTL", 21),
    ]
)

LANDED_STATES = OrderedDict(
    [
        ("On ground", int(getattr(mavlink2, "MAV_LANDED_STATE_ON_GROUND", 1))),
        ("In air", int(getattr(mavlink2, "MAV_LANDED_STATE_IN_AIR", 2))),
        ("Landing", int(getattr(mavlink2, "MAV_LANDED_STATE_LANDING", 4))),
        ("Undefined", int(getattr(mavlink2, "MAV_LANDED_STATE_UNDEFINED", 0))),
    ]
)
LANDED_NAMES = {value: name for name, value in LANDED_STATES.items()}

GPS_FIXES = OrderedDict(
    [
        ("No GPS", int(getattr(mavlink2, "GPS_FIX_TYPE_NO_GPS", 0))),
        ("No fix", int(getattr(mavlink2, "GPS_FIX_TYPE_NO_FIX", 1))),
        ("2D fix", int(getattr(mavlink2, "GPS_FIX_TYPE_2D_FIX", 2))),
        ("3D fix", int(getattr(mavlink2, "GPS_FIX_TYPE_3D_FIX", 3))),
        ("DGPS", int(getattr(mavlink2, "GPS_FIX_TYPE_DGPS", 4))),
        ("RTK float", int(getattr(mavlink2, "GPS_FIX_TYPE_RTK_FLOAT", 5))),
        ("RTK fixed", int(getattr(mavlink2, "GPS_FIX_TYPE_RTK_FIXED", 6))),
    ]
)
GPS_FIX_NAMES = {value: name for name, value in GPS_FIXES.items()}

SEVERITIES = OrderedDict(
    [
        ("Info", int(getattr(mavlink2, "MAV_SEVERITY_INFO", 6))),
        ("Notice", int(getattr(mavlink2, "MAV_SEVERITY_NOTICE", 5))),
        ("Warning", int(getattr(mavlink2, "MAV_SEVERITY_WARNING", 4))),
        ("Critical", int(getattr(mavlink2, "MAV_SEVERITY_CRITICAL", 2))),
        ("Error", int(getattr(mavlink2, "MAV_SEVERITY_ERROR", 3))),
    ]
)
SEVERITY_NAMES = {value: name for name, value in SEVERITIES.items()}

COMMAND_NAMES = {
    int(getattr(mavlink2, "MAV_CMD_COMPONENT_ARM_DISARM", 400)): "COMPONENT_ARM_DISARM",
    int(getattr(mavlink2, "MAV_CMD_REQUEST_AUTOPILOT_CAPABILITIES", 520)): "REQUEST_AUTOPILOT_CAPABILITIES",
    int(getattr(mavlink2, "MAV_CMD_SET_MESSAGE_INTERVAL", 511)): "SET_MESSAGE_INTERVAL",
    int(getattr(mavlink2, "MAV_CMD_GET_HOME_POSITION", 410)): "GET_HOME_POSITION",
    int(getattr(mavlink2, "MAV_CMD_REQUEST_MESSAGE", 512)): "REQUEST_MESSAGE",
    int(getattr(mavlink2, "MAV_CMD_DO_SET_MODE", 176)): "DO_SET_MODE",
    int(getattr(mavlink2, "MAV_CMD_NAV_TAKEOFF", 22)): "NAV_TAKEOFF",
    int(getattr(mavlink2, "MAV_CMD_NAV_LAND", 21)): "NAV_LAND",
}

MESSAGE_NAMES = {
    0: "HEARTBEAT",
    1: "SYS_STATUS",
    2: "SYSTEM_TIME",
    4: "PING",
    24: "GPS_RAW_INT",
    30: "ATTITUDE",
    32: "LOCAL_POSITION_NED",
    33: "GLOBAL_POSITION_INT",
    65: "RC_CHANNELS",
    74: "VFR_HUD",
    109: "RADIO_STATUS",
    147: "BATTERY_STATUS",
    148: "AUTOPILOT_VERSION",
    245: "EXTENDED_SYS_STATE",
}


def _now_stamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _param_id(name: str) -> bytes:
    return name.encode("ascii", "ignore")[:MAX_PARAM_NAME]


def _param_name(raw: Any) -> str:
    if isinstance(raw, bytes):
        raw = raw.split(b"\x00", 1)[0].decode("ascii", "ignore")
    return str(raw).split("\x00", 1)[0].strip()


def _param_type_name(raw: int) -> str:
    return PARAM_TYPE_NAMES.get(int(raw), "TYPE_%s" % int(raw))


def _param_type_value(name: str) -> int:
    return PARAM_TYPES.get(name.upper(), PARAM_TYPES["REAL32"])


def _coerce_param_value(value: Any, param_type: int) -> Any:
    try:
        if param_type in PARAM_REAL_TYPES:
            return float(value)
        return int(float(value))
    except (TypeError, ValueError):
        return 0.0 if param_type in PARAM_REAL_TYPES else 0


def _format_param_value(value: Any) -> str:
    if isinstance(value, float):
        if value.is_integer():
            return str(int(value))
        return ("%.8g" % value)
    return str(value)


class MavlinkCodec:
    def __init__(self, sysid: int, compid: int):
        self.sysid = sysid
        self.compid = compid
        self.sender = mavlink2.MAVLink(None, srcSystem=sysid, srcComponent=compid)
        self.parser = mavlink2.MAVLink(None, srcSystem=sysid, srcComponent=compid)
        self.parser.robust_parsing = True

    def pack(self, msg: Any) -> bytes:
        return msg.pack(self.sender)

    def parse(self, data: bytes) -> List[Any]:
        try:
            msgs = self.parser.parse_buffer(data)
        except Exception:
            return []
        return msgs or []


class Endpoint:
    """UDP, TCP-server or serial MAVLink endpoint."""

    def __init__(
        self,
        transport: str,
        host: str,
        port: int,
        bind_host: str,
        bind_port: int,
        serial_port: str,
        baud: int,
        on_bytes: Callable[[bytes], None],
        on_log: Callable[[str, str], None],
    ):
        self.transport = transport.upper()
        self.host = host
        self.port = port
        self.bind_host = bind_host
        self.bind_port = bind_port
        self.serial_port = serial_port
        self.baud = baud
        self.on_bytes = on_bytes
        self.on_log = on_log

        self.sock: Optional[socket.socket] = None
        self.conn: Optional[socket.socket] = None
        self.serial = None
        self.running = False
        self._thread: Optional[threading.Thread] = None
        self._send_lock = threading.Lock()

    def open(self) -> None:
        self.close()
        self.running = True

        if self.transport == "UDP":
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind((self.bind_host, self.bind_port))
            self.sock.settimeout(0.15)
            self.on_log("info", "UDP bound on %s:%d -> QGC %s:%d" % (self.bind_host, self.bind_port, self.host, self.port))
        elif self.transport == "TCP SERVER":
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sock.bind((self.bind_host, self.bind_port))
            self.sock.listen(1)
            self.sock.settimeout(0.15)
            self.on_log("info", "TCP server listening on %s:%d" % (self.bind_host, self.bind_port))
        elif self.transport == "SERIAL":
            if pyserial is None:
                raise RuntimeError("pyserial is not installed (pip install pyserial)")
            self.serial = pyserial.Serial(self.serial_port, self.baud, timeout=0.1)
            self.on_log("info", "Serial opened: %s @ %d" % (self.serial_port, self.baud))
        else:
            raise ValueError("Unknown transport: %s" % self.transport)

        self._thread = threading.Thread(target=self._rx_loop, name="mavlink-rx", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self.running = False
        for obj_name in ("conn", "sock", "serial"):
            obj = getattr(self, obj_name, None)
            if obj is not None:
                try:
                    obj.close()
                except Exception:
                    pass
                setattr(self, obj_name, None)
        thread = self._thread
        if thread is not None and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=1.0)
        self._thread = None

    def send(self, data: bytes) -> None:
        with self._send_lock:
            if not self.running:
                raise RuntimeError("link is not connected")
            if self.transport == "UDP":
                if self.sock is None:
                    raise RuntimeError("UDP socket is not open")
                self.sock.sendto(data, (self.host, self.port))
            elif self.transport == "TCP SERVER":
                if self.conn is None:
                    raise RuntimeError("no TCP client connected")
                self.conn.sendall(data)
            elif self.transport == "SERIAL":
                if self.serial is None:
                    raise RuntimeError("serial port is not open")
                self.serial.write(data)

    def _rx_loop(self) -> None:
        while self.running:
            try:
                data = self._read_once()
                if data:
                    self.on_bytes(data)
            except socket.timeout:
                continue
            except (OSError, RuntimeError) as exc:
                if self.running:
                    self.on_log("error", "RX error: %s" % exc)
                break
            except Exception as exc:
                if self.running:
                    self.on_log("error", "RX parser error: %s" % exc)
                break

    def _read_once(self) -> bytes:
        if self.transport == "UDP":
            if self.sock is None:
                return b""
            try:
                data, _addr = self.sock.recvfrom(65535)
                return data
            except socket.timeout:
                return b""
        if self.transport == "TCP SERVER":
            if self.sock is None:
                return b""
            if self.conn is None:
                try:
                    self.conn, addr = self.sock.accept()
                    self.conn.settimeout(0.15)
                    self.on_log("info", "TCP client connected from %s:%d" % addr)
                except socket.timeout:
                    return b""
            try:
                data = self.conn.recv(65535)
            except socket.timeout:
                return b""
            if not data:
                self.on_log("info", "TCP client disconnected")
                try:
                    self.conn.close()
                except Exception:
                    pass
                self.conn = None
                return b""
            return data
        if self.transport == "SERIAL":
            if self.serial is None:
                return b""
            waiting = getattr(self.serial, "in_waiting", 0)
            return self.serial.read(max(1, waiting))
        return b""


class VehicleSimulator:
    def __init__(
        self,
        event_cb: Callable[[Tuple[Any, ...]], None],
        sysid: int = DEFAULT_SYSID,
        compid: int = DEFAULT_COMPID,
    ):
        self.event_cb = event_cb
        self.sysid = sysid
        self.compid = compid
        self.codec = MavlinkCodec(sysid, compid)
        self.lock = threading.RLock()
        self.params: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
        self.state = dict(DEFAULT_STATE)
        self.memory: Deque[Dict[str, Any]] = deque(maxlen=300)
        self.endpoint: Optional[Endpoint] = None
        self.running = False
        self.heartbeat_enabled = True
        self.auto_telemetry = True
        self.telemetry_interval = 1.0
        self.param_reply_delay = DEFAULT_PARAM_REPLY_DELAY
        self.verbose_rx = False
        self.rx_count = 0
        self.tx_count = 0
        self._loop_thread: Optional[threading.Thread] = None
        self._started_at = time.monotonic()
        self._last_heartbeat = 0.0
        self._last_telemetry = 0.0
        self._param_reply_lock = threading.Lock()
        self._pending_param_replies: Dict[str, threading.Timer] = {}

    def set_ids(self, sysid: int, compid: int) -> None:
        if self.running:
            raise RuntimeError("disconnect before changing MAVLink IDs")
        self.sysid = int(sysid)
        self.compid = int(compid)
        self.codec = MavlinkCodec(self.sysid, self.compid)

    # ------------------------------------------------------------------ state
    def export_state(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "params": [
                    {
                        "name": name,
                        "value": entry["value"],
                        "type": entry["type"],
                        "source": entry["source"],
                        "updated": entry["updated"],
                    }
                    for name, entry in self.params.items()
                ],
                "sim": dict(self.state),
                "memory": list(self.memory),
                "settings": {
                    "heartbeat_enabled": self.heartbeat_enabled,
                    "auto_telemetry": self.auto_telemetry,
                    "telemetry_interval": self.telemetry_interval,
                    "param_reply_delay": self.param_reply_delay,
                },
            }

    def import_state(self, data: Dict[str, Any]) -> None:
        with self.lock:
            sim = data.get("sim") or {}
            for key in DEFAULT_STATE:
                if key in sim:
                    self.state[key] = sim[key]

            self.params.clear()
            for row in data.get("params") or []:
                if not isinstance(row, dict):
                    continue
                name = _param_name(row.get("name", ""))
                if not name:
                    continue
                ptype = int(row.get("type", PARAM_TYPES["REAL32"]))
                value = _coerce_param_value(row.get("value", 0), ptype)
                self.params[name] = {
                    "value": value,
                    "type": ptype,
                    "source": str(row.get("source", "saved")),
                    "updated": str(row.get("updated", "")),
                }

            self.memory.clear()
            for row in data.get("memory") or []:
                if isinstance(row, dict):
                    self.memory.append(row)

            settings = data.get("settings") or {}
            self.heartbeat_enabled = bool(settings.get("heartbeat_enabled", True))
            self.auto_telemetry = bool(settings.get("auto_telemetry", True))
            try:
                self.telemetry_interval = max(0.2, min(10.0, float(settings.get("telemetry_interval", 1.0))))
            except Exception:
                self.telemetry_interval = 1.0
            try:
                self.param_reply_delay = max(
                    0.0,
                    min(60.0, float(settings.get("param_reply_delay", DEFAULT_PARAM_REPLY_DELAY))),
                )
            except Exception:
                self.param_reply_delay = DEFAULT_PARAM_REPLY_DELAY

    def state_snapshot(self) -> Dict[str, Any]:
        with self.lock:
            return dict(self.state)

    def update_state(self, **kwargs: Any) -> None:
        with self.lock:
            for key, value in kwargs.items():
                if key in self.state:
                    self.state[key] = value
        self.event_cb(("state", dict(kwargs)))

    # --------------------------------------------------------------- lifecycle
    def connect(self, endpoint: Endpoint) -> None:
        self.disconnect()
        self.endpoint = endpoint
        endpoint.open()
        self.running = True
        self._started_at = time.monotonic()
        self._last_heartbeat = 0.0
        self._last_telemetry = 0.0
        self._loop_thread = threading.Thread(target=self._send_loop, name="mavlink-tx", daemon=True)
        self._loop_thread.start()
        self.event_cb(("link", True, "Connected"))
        try:
            self.send_heartbeat()
            self.send_telemetry()
            self.send_autopilot_version()
        except Exception:
            # Never leave the send loop running after a partially failed
            # connection; the GUI would show "Disconnected" while packets
            # continue to be transmitted.
            self.disconnect()
            raise

    def disconnect(self) -> None:
        was_running = self.running
        self.running = False
        self._cancel_param_replies()
        if self._loop_thread is not None and self._loop_thread.is_alive() and self._loop_thread is not threading.current_thread():
            self._loop_thread.join(timeout=1.5)
        self._loop_thread = None
        endpoint = self.endpoint
        self.endpoint = None
        if endpoint is not None:
            endpoint.close()
        if was_running:
            self.event_cb(("link", False, "Disconnected"))

    def _send_loop(self) -> None:
        while self.running:
            now = time.monotonic()
            if self.heartbeat_enabled and now - self._last_heartbeat >= 1.0:
                self.send_heartbeat()
                self._last_heartbeat = now
            if self.auto_telemetry and now - self._last_telemetry >= self.telemetry_interval:
                self.send_telemetry()
                self._last_telemetry = now
            time.sleep(0.02)

    def _send(self, msg: Any) -> None:
        endpoint = self.endpoint
        if endpoint is None or not self.running:
            return
        try:
            endpoint.send(self.codec.pack(msg))
            self.tx_count += 1
        except Exception as exc:
            self.event_cb(("log", "error", "TX error: %s" % exc))

    def send_heartbeat(self) -> None:
        with self.lock:
            armed = bool(self.state["armed"])
            vehicle_type = int(self.state["vehicle_type"])
            autopilot = int(self.state["autopilot"])
            custom_mode = int(self.state["custom_mode"])
        base_mode = int(getattr(mavlink2, "MAV_MODE_FLAG_CUSTOM_MODE_ENABLED", 1))
        if armed:
            base_mode |= int(getattr(mavlink2, "MAV_MODE_FLAG_SAFETY_ARMED", 128))
        state_active = int(getattr(mavlink2, "MAV_STATE_ACTIVE", 4))
        self._send(self.codec.sender.heartbeat_encode(vehicle_type, autopilot, base_mode, custom_mode, state_active))
        # QGC also benefits from a current SYS_STATUS shortly after heartbeat.
        self.send_sys_status()

    def send_sys_status(self) -> None:
        with self.lock:
            prearm_ok = bool(self.state["prearm_ok"])
            voltage = float(self.state["battery_voltage"])
            current = float(self.state["battery_current"])
            percent = int(self.state["battery_percent"])
            gps_fix = int(self.state["gps_fix"])

        # Present + enabled sensors; health follows the pre-arm toggle.
        sensor_bits = 0
        for name in (
            "MAV_SYS_STATUS_SENSOR_3D_GYRO",
            "MAV_SYS_STATUS_SENSOR_3D_ACCEL",
            "MAV_SYS_STATUS_SENSOR_3D_MAG",
            "MAV_SYS_STATUS_SENSOR_ABSOLUTE_PRESSURE",
            "MAV_SYS_STATUS_SENSOR_DIFFERENTIAL_PRESSURE",
            "MAV_SYS_STATUS_SENSOR_GPS",
            "MAV_SYS_STATUS_SENSOR_RC_RECEIVER",
            "MAV_SYS_STATUS_SENSOR_MOTOR_OUTPUTS",
        ):
            sensor_bits |= int(getattr(mavlink2, name, 0))
        prearm_bit = int(getattr(mavlink2, "MAV_SYS_STATUS_PREARM_CHECK", 1 << 28))
        sensor_bits |= prearm_bit
        if not gps_fix:
            sensor_bits &= ~int(getattr(mavlink2, "MAV_SYS_STATUS_SENSOR_GPS", 0))
        health = sensor_bits if prearm_ok else (sensor_bits & ~prearm_bit)
        self._send(
            self.codec.sender.sys_status_encode(
                sensor_bits,  # present
                sensor_bits,  # enabled
                health,
                0,  # load
                int(round(voltage * 1000.0)),
                int(round(current * 100.0)),
                percent,
                0,
                0,
                0,
                0,
                0,
                0,
            )
        )

    def send_battery(self) -> None:
        with self.lock:
            percent = max(0, min(100, int(self.state["battery_percent"])))
            voltage = max(0.0, float(self.state["battery_voltage"]))
            current = max(0.0, float(self.state["battery_current"]))
            charging = bool(self.state["battery_charging"])
        if charging:
            charge_state = int(getattr(mavlink2, "MAV_BATTERY_CHARGE_STATE_CHARGING", 7))
        elif percent <= 10:
            charge_state = int(getattr(mavlink2, "MAV_BATTERY_CHARGE_STATE_CRITICAL", 3))
        elif percent <= 20:
            charge_state = int(getattr(mavlink2, "MAV_BATTERY_CHARGE_STATE_LOW", 2))
        else:
            charge_state = int(getattr(mavlink2, "MAV_BATTERY_CHARGE_STATE_OK", 1))
        cell_count = 4
        per_cell = int(round(voltage * 1000.0 / cell_count)) if voltage > 0 else 0
        voltages = [per_cell] * cell_count + [0xFFFF] * (10 - cell_count)
        self._send(
            self.codec.sender.battery_status_encode(
                0,
                int(getattr(mavlink2, "MAV_BATTERY_FUNCTION_ALL", 1)),
                int(getattr(mavlink2, "MAV_BATTERY_TYPE_LIPO", 1)),
                250,
                voltages,
                int(round(current * 100.0)),
                0,
                0,
                percent,
                0,
                charge_state,
            )
        )

    def send_gps(self) -> None:
        with self.lock:
            fix = int(self.state["gps_fix"])
            sats = int(self.state["gps_sats"])
            lat = float(self.state["lat"])
            lon = float(self.state["lon"])
            alt = float(self.state["alt"])
        self._send(
            self.codec.sender.gps_raw_int_encode(
                int(time.time() * 1e6),
                fix,
                int(round(lat * 1e7)),
                int(round(lon * 1e7)),
                int(round(alt * 1000.0)),
                100,
                200,
                0,
                0,
                sats,
            )
        )

    def send_global_position(self) -> None:
        with self.lock:
            lat = float(self.state["lat"])
            lon = float(self.state["lon"])
            alt = float(self.state["alt"])
        boot_ms = int((time.monotonic() - self._started_at) * 1000) & 0xFFFFFFFF
        self._send(
            self.codec.sender.global_position_int_encode(
                boot_ms,
                int(round(lat * 1e7)),
                int(round(lon * 1e7)),
                int(round(alt * 1000.0)),
                int(round(alt * 1000.0)),
                0,
                0,
                0,
                0,
            )
        )

    def send_attitude(self) -> None:
        boot_ms = int((time.monotonic() - self._started_at) * 1000) & 0xFFFFFFFF
        self._send(self.codec.sender.attitude_encode(boot_ms, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0))

    def send_vfr_hud(self) -> None:
        with self.lock:
            alt = float(self.state["alt"])
        self._send(self.codec.sender.vfr_hud_encode(0.0, 0.0, 0, 0, alt, 0.0))

    def send_extended_sys_state(self) -> None:
        with self.lock:
            landed = int(self.state["landed_state"])
            vehicle_type = int(self.state["vehicle_type"])
        vtol = int(getattr(mavlink2, "MAV_VTOL_STATE_UNDEFINED", 0))
        if vehicle_type in (int(getattr(mavlink2, "MAV_TYPE_VTOL_QUADROTOR", 20)), int(getattr(mavlink2, "MAV_TYPE_VTOL_TILTROTOR", 21))):
            vtol = int(getattr(mavlink2, "MAV_VTOL_STATE_MC", 1))
        self._send(self.codec.sender.extended_sys_state_encode(vtol, landed))

    def send_radio_status(self) -> None:
        with self.lock:
            rssi = max(0, min(255, int(self.state["link_rssi"])))
            remrssi = max(0, min(255, int(self.state["remote_rssi"])))
        self._send(self.codec.sender.radio_status_encode(rssi, remrssi, 100, 0, 0, 0, 0))

    def send_rc_channels(self) -> None:
        with self.lock:
            rssi = max(0, min(100, int(self.state["rc_rssi"])))
        boot_ms = int((time.monotonic() - self._started_at) * 1000) & 0xFFFFFFFF
        channels = [1500, 1500, 1000, 1500, 1000, 1000, 1000, 1000] + [65535] * 10
        self._send(self.codec.sender.rc_channels_encode(boot_ms, 8, *channels, rssi))

    def send_telemetry(self) -> None:
        self.send_sys_status()
        self.send_battery()
        self.send_gps()
        self.send_global_position()
        self.send_attitude()
        self.send_vfr_hud()
        self.send_extended_sys_state()
        self.send_radio_status()
        self.send_rc_channels()

    def send_statustext(self, severity: int, text: str) -> None:
        text = text.encode("utf-8", "replace")[:50]
        self._send(self.codec.sender.statustext_encode(int(severity), text))
        self.event_cb(("log", "tx", "STATUSTEXT: %s" % text.decode("utf-8", "replace")))

    def send_home_position(self) -> None:
        with self.lock:
            lat = float(self.state["lat"])
            lon = float(self.state["lon"])
            alt = float(self.state["alt"])
        self._send(
            self.codec.sender.home_position_encode(
                int(round(lat * 1e7)),
                int(round(lon * 1e7)),
                int(round(alt * 1000.0)),
                0.0,
                0.0,
                0.0,
                (1.0, 0.0, 0.0, 0.0),
                0.0,
                0.0,
                0.0,
            )
        )

    def send_autopilot_version(self) -> None:
        capabilities = 0
        for name in (
            "MAV_PROTOCOL_CAPABILITY_MAVLINK2",
            "MAV_PROTOCOL_CAPABILITY_PARAM_FLOAT",
            "MAV_PROTOCOL_CAPABILITY_MISSION_INT",
            "MAV_PROTOCOL_CAPABILITY_COMMAND_INT",
        ):
            capabilities |= int(getattr(mavlink2, name, 0))
        self._send(
            self.codec.sender.autopilot_version_encode(
                capabilities,
                (1 << 24) | (14 << 16),
                (1 << 24) | (0 << 16),
                (1 << 24) | (0 << 16),
                1,
                bytes([0] * 8),
                bytes([0] * 8),
                bytes([0] * 8),
                0,
                0,
                0x1234567890ABCDEF,
            )
        )

    def send_ping_reply(self, msg: Any) -> None:
        target_sys = msg.get_srcSystem()
        target_comp = msg.get_srcComponent()
        self._send(self.codec.sender.ping_encode(int(msg.time_usec), int(msg.seq), target_sys, target_comp))

    # --------------------------------------------------------------- parameter
    def add_or_update_param(
        self,
        name: str,
        value: Any,
        type_name: str = "REAL32",
        source: str = "local",
        send: bool = False,
    ) -> bool:
        name = _param_name(name)
        if not name:
            return False
        ptype = _param_type_value(type_name)
        value = _coerce_param_value(value, ptype)
        with self.lock:
            self.params[name] = {
                "value": value,
                "type": ptype,
                "source": source,
                "updated": _now_stamp(),
            }
            entry = dict(self.params[name])
        self.event_cb(("param", name, entry))
        if send:
            self.send_param_value(name)
        return True

    def delete_param(self, name: str) -> None:
        with self.lock:
            self.params.pop(name, None)
        self.event_cb(("param_deleted", name))

    def _sorted_params(self) -> List[Tuple[str, Dict[str, Any]]]:
        with self.lock:
            return sorted(self.params.items(), key=lambda item: item[0].lower())

    def send_param_value(self, name: str) -> None:
        name = _param_name(name)
        rows = self._sorted_params()
        count = len(rows)
        index = next((i for i, (n, _e) in enumerate(rows) if n == name), -1)
        entry = next((e for n, e in rows if n == name), None)
        if entry is None:
            return
        self._send(
            self.codec.sender.param_value_encode(
                _param_id(name),
                float(entry["value"]),
                int(entry["type"]),
                count,
                max(0, index),
            )
        )

    def send_all_params(self) -> None:
        rows = self._sorted_params()
        for idx, (name, entry) in enumerate(rows):
            self._send(
                self.codec.sender.param_value_encode(
                    _param_id(name),
                    float(entry["value"]),
                    int(entry["type"]),
                    len(rows),
                    idx,
                )
            )
        self.event_cb(("log", "tx", "PARAM_VALUE x%d" % len(rows)))

    # ------------------------------------------------- delayed param replies
    def _schedule_param_reply(self, key: str, action: Callable[[], None]) -> bool:
        """Run a parameter reply after ``param_reply_delay`` seconds.

        Returns False when an identical reply is already pending, so QGC
        retries do not schedule duplicate responses.
        """
        delay = max(0.0, float(self.param_reply_delay))
        with self._param_reply_lock:
            if key in self._pending_param_replies:
                return False
            if delay > 0:
                timer = threading.Timer(delay, self._run_param_reply, args=(key, action))
                timer.daemon = True
                self._pending_param_replies[key] = timer
                timer.start()
                return True
        self._run_param_reply(key, action)
        return True

    def _run_param_reply(self, key: str, action: Callable[[], None]) -> None:
        with self._param_reply_lock:
            self._pending_param_replies.pop(key, None)
        if not self.running:
            return
        try:
            action()
        except Exception as exc:
            self.event_cb(("log", "error", "Param reply error: %s" % exc))

    def _cancel_param_replies(self) -> None:
        with self._param_reply_lock:
            timers = list(self._pending_param_replies.values())
            self._pending_param_replies.clear()
        for timer in timers:
            timer.cancel()

    def _queue_param_list_reply(self) -> None:
        delay = max(0.0, float(self.param_reply_delay))
        if self._schedule_param_reply("list", self.send_all_params) and delay > 0:
            self.event_cb(("log", "info", "PARAM_REQUEST_LIST: replying in %.1fs" % delay))

    def _queue_param_read_reply(self, name: str) -> None:
        self._schedule_param_reply("read:%s" % name, lambda: self.send_param_value(name))

    # --------------------------------------------------------------- RX handling
    def feed_bytes(self, data: bytes) -> None:
        for msg in self.codec.parse(data):
            self._handle_message(msg)

    def _remember(self, mtype: str, name: str, value: Any) -> None:
        item = {
            "time": _now_stamp(),
            "type": mtype,
            "name": name,
            "value": str(value),
        }
        self.memory.append(item)
        self.event_cb(("memory", item))

    def _handle_message(self, msg: Any) -> None:
        self.rx_count += 1
        mtype = msg.get_type()
        if mtype == "BAD_DATA":
            return
        src_sys = msg.get_srcSystem()
        src_comp = msg.get_srcComponent()
        if mtype == "HEARTBEAT":
            if getattr(msg, "type", None) == int(getattr(mavlink2, "MAV_TYPE_GCS", 6)):
                return
        if self.verbose_rx:
            self.event_cb(("log", "rx", "RX %s sys=%s comp=%s" % (mtype, src_sys, src_comp)))

        if mtype == "PARAM_REQUEST_LIST":
            self._remember("PARAM_REQUEST_LIST", "*", "all")
            self._queue_param_list_reply()
        elif mtype == "PARAM_REQUEST_READ":
            name = _param_name(getattr(msg, "param_id", ""))
            if not name and int(getattr(msg, "param_index", -1)) >= 0:
                rows = self._sorted_params()
                idx = int(msg.param_index)
                if 0 <= idx < len(rows):
                    name = rows[idx][0]
            if name and name not in self.params:
                # QGC may remember parameters from a previous session. Remember
                # the request so its value can be provided afterwards.
                self.add_or_update_param(name, 0.0, "REAL32", source="QGC request")
            self._remember("PARAM_REQUEST_READ", name or "(index %s)" % getattr(msg, "param_index", "?"), "read")
            if name:
                self._queue_param_read_reply(name)
        elif mtype == "PARAM_SET":
            name = _param_name(getattr(msg, "param_id", ""))
            if name:
                ptype = int(getattr(msg, "param_type", PARAM_TYPES["REAL32"]))
                if ptype not in PARAM_TYPE_NAMES:
                    ptype = PARAM_TYPES["REAL32"]
                value = _coerce_param_value(getattr(msg, "param_value", 0), ptype)
                self.add_or_update_param(name, value, _param_type_name(ptype), source="QGC", send=True)
                self._remember("PARAM_SET", name, _format_param_value(value))
        elif mtype in ("COMMAND_LONG", "COMMAND_INT"):
            self._handle_command(msg, src_sys, src_comp)
        elif mtype == "SET_MODE":
            custom_mode = int(getattr(msg, "custom_mode", 0))
            base_mode = int(getattr(msg, "base_mode", 0))
            armed = bool(base_mode & int(getattr(mavlink2, "MAV_MODE_FLAG_SAFETY_ARMED", 128)))
            self.update_state(custom_mode=custom_mode, armed=armed)
            self._remember("SET_MODE", "custom_mode", custom_mode)
            self.send_heartbeat()
        elif mtype == "PING":
            self.send_ping_reply(msg)
        elif mtype == "MISSION_REQUEST_LIST":
            self._remember("MISSION_REQUEST_LIST", "*", "list")
            self._send(
                self.codec.sender.mission_count_encode(
                    src_sys,
                    src_comp,
                    0,
                    int(getattr(mavlink2, "MAV_MISSION_TYPE_MISSION", 0)),
                )
            )
        elif mtype in ("MISSION_REQUEST", "MISSION_REQUEST_INT"):
            self._remember(mtype, "seq", getattr(msg, "seq", "?"))
            self._send(
                self.codec.sender.mission_ack_encode(
                    src_sys,
                    src_comp,
                    int(getattr(mavlink2, "MAV_MISSION_ERROR", 1)),
                    int(getattr(mavlink2, "MAV_MISSION_TYPE_MISSION", 0)),
                )
            )
        elif mtype == "MISSION_ACK":
            self._remember("MISSION_ACK", "type", getattr(msg, "type", "?"))
        elif mtype == "STATUSTEXT":
            text = getattr(msg, "text", b"")
            if isinstance(text, bytes):
                text = text.decode("utf-8", "replace")
            self._remember("STATUSTEXT", "QGC", text)

    def _handle_command(self, msg: Any, src_sys: int, src_comp: int) -> None:
        command = int(getattr(msg, "command", 0))
        command_name = COMMAND_NAMES.get(command, "CMD_%d" % command)
        params = [getattr(msg, "param%d" % i, 0.0) for i in range(1, 8)]
        self._remember("COMMAND", command_name, " p1=%.4g p2=%.4g" % (params[0], params[1]))

        result = int(getattr(mavlink2, "MAV_RESULT_ACCEPTED", 0))
        handled = True

        if command == int(getattr(mavlink2, "MAV_CMD_COMPONENT_ARM_DISARM", 400)):
            self.update_state(armed=bool(params[0] >= 0.5))
            self.send_heartbeat()
            self.send_sys_status()
        elif command == int(getattr(mavlink2, "MAV_CMD_REQUEST_AUTOPILOT_CAPABILITIES", 520)):
            self.send_autopilot_version()
        elif command == int(getattr(mavlink2, "MAV_CMD_SET_MESSAGE_INTERVAL", 511)):
            pass
        elif command == int(getattr(mavlink2, "MAV_CMD_GET_HOME_POSITION", 410)):
            self.send_home_position()
        elif command == int(getattr(mavlink2, "MAV_CMD_REQUEST_MESSAGE", 512)):
            requested = int(params[0])
            self._send_requested_message(requested)
        elif command == int(getattr(mavlink2, "MAV_CMD_DO_SET_MODE", 176)):
            self.update_state(custom_mode=int(params[1]))
            self.send_heartbeat()
        else:
            handled = False
            result = int(getattr(mavlink2, "MAV_RESULT_UNSUPPORTED", 3))

        self._send(
            self.codec.sender.command_ack_encode(
                command,
                result,
                0,
                0,
                src_sys,
                src_comp,
            )
        )
        self.event_cb(("log", "rx", "COMMAND %s -> %s" % (command_name, "ACCEPTED" if handled else "UNSUPPORTED")))

    def _send_requested_message(self, message_id: int) -> None:
        if message_id == 0:
            self.send_heartbeat()
        elif message_id == 1:
            self.send_sys_status()
        elif message_id == 24:
            self.send_gps()
        elif message_id == 30:
            self.send_attitude()
        elif message_id == 33:
            self.send_global_position()
        elif message_id == 65:
            self.send_rc_channels()
        elif message_id == 74:
            self.send_vfr_hud()
        elif message_id == 109:
            self.send_radio_status()
        elif message_id == 147:
            self.send_battery()
        elif message_id == 148:
            self.send_autopilot_version()
        elif message_id == 245:
            self.send_extended_sys_state()


class StateStore:
    def __init__(self, path: Path):
        self.path = path

    def load(self) -> Dict[str, Any]:
        try:
            with self.path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def save(self, data: Dict[str, Any]) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
            tmp.replace(self.path)
        except Exception:
            pass


def acquire_instance_lock(path: Path):
    """Return an open lock file, or None if another tester owns it."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = path.open("a+")
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        fh.seek(0)
        fh.truncate()
        fh.write(str(os.getpid()))
        fh.flush()
        return fh
    except OSError:
        try:
            fh.close()
        except Exception:
            pass
        return None


class QGCNavBarTesterApp:
    def __init__(self, root: tk.Tk, args: argparse.Namespace):
        self.root = root
        self.args = args
        self.store = StateStore(Path(args.state_file).expanduser())
        self.saved_state = self.store.load()
        self.events: "queue.Queue[Tuple[Any, ...]]" = queue.Queue()
        self.sim = VehicleSimulator(self.events.put, sysid=args.sysid, compid=args.compid)
        self._loading_ui = True
        self._save_after_id = None
        self._link_connected = False
        self._build_style()
        self._build_ui()
        self._load_initial_state()
        self._loading_ui = False
        self._refresh_mode_values()
        self._sync_ui_from_sim()
        self.root.after(80, self._poll_events)
        if args.auto_connect:
            self.root.after(300, self._connect)

    # ------------------------------------------------------------------ style
    def _build_style(self) -> None:
        self.root.title(APP_NAME)
        self.root.geometry("1180x820")
        self.root.minsize(960, 640)
        bg = "#1b1d1f"
        panel = "#24272a"
        field = "#2f3337"
        fg = "#f0f0f0"
        muted = "#a7adb5"
        accent = "#00c8c0"
        self.root.configure(bg=bg)
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure(".", background=bg, foreground=fg, fieldbackground=field, bordercolor="#444a50")
        style.configure("TFrame", background=bg)
        style.configure("Panel.TFrame", background=panel)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("Panel.TLabel", background=panel, foreground=fg)
        style.configure("Muted.TLabel", background=bg, foreground=muted)
        style.configure("PanelMuted.TLabel", background=panel, foreground=muted)
        style.configure("TLabelframe", background=bg, foreground=fg)
        style.configure("TLabelframe.Label", background=bg, foreground=accent)
        style.configure("TButton", background=field, foreground=fg, padding=(8, 4))
        style.map("TButton", background=[("active", "#3b4046"), ("disabled", "#2a2d30")])
        style.configure("Accent.TButton", background="#007d78", foreground="#ffffff", padding=(10, 5))
        style.map("Accent.TButton", background=[("active", accent)])
        style.configure("TCheckbutton", background=bg, foreground=fg)
        style.configure("Panel.TCheckbutton", background=panel, foreground=fg)
        style.configure("TNotebook", background=bg, borderwidth=0)
        style.configure("TNotebook.Tab", background=field, foreground=fg, padding=(14, 6))
        style.map("TNotebook.Tab", background=[("selected", "#3a4046")])
        style.configure("TEntry", fieldbackground=field, foreground=fg, insertcolor=fg)
        style.configure("TCombobox", fieldbackground=field, background=field, foreground=fg, arrowcolor=fg)
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", field), ("disabled", field)],
            foreground=[("readonly", fg), ("disabled", muted)],
            selectbackground=[("readonly", field)],
            selectforeground=[("readonly", fg)],
        )
        self.root.option_add("*TCombobox*Listbox.background", field)
        self.root.option_add("*TCombobox*Listbox.foreground", fg)
        self.root.option_add("*TCombobox*Listbox.selectBackground", "#007d78")
        self.root.option_add("*TCombobox*Listbox.selectForeground", "#ffffff")
        style.configure("TSpinbox", fieldbackground=field, foreground=fg, arrowcolor=fg)
        style.configure("TScale", background=bg, troughcolor="#3a3f44")
        style.configure("Treeview", background=field, fieldbackground=field, foreground=fg, rowheight=24)
        style.configure("Treeview.Heading", background="#3a4046", foreground=fg)
        style.map("Treeview", background=[("selected", "#007d78")])
        self.colors = {"bg": bg, "panel": panel, "field": field, "fg": fg, "muted": muted, "accent": accent}

    # --------------------------------------------------------------------- UI
    def _build_ui(self) -> None:
        self._build_link_bar()
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=(0, 6))
        self.sim_tab = ttk.Frame(self.notebook)
        self.params_tab = ttk.Frame(self.notebook)
        self.memory_tab = ttk.Frame(self.notebook)
        self.log_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.sim_tab, text="Simulator")
        self.notebook.add(self.params_tab, text="Parameters")
        self.notebook.add(self.memory_tab, text="QGC Memory")
        self.notebook.add(self.log_tab, text="Log")
        self._build_sim_tab()
        self._build_params_tab()
        self._build_memory_tab()
        self._build_log_tab()
        self._build_status_bar()

    def _build_link_bar(self) -> None:
        outer = ttk.Frame(self.root, padding=(8, 8, 8, 4))
        outer.pack(fill="x")
        self.link_frame = ttk.LabelFrame(outer, text="MAVLink link", padding=8)
        self.link_frame.pack(fill="x")

        self.transport_var = tk.StringVar(value="UDP")
        self.host_var = tk.StringVar(value=DEFAULT_UDP_HOST)
        self.port_var = tk.StringVar(value=str(DEFAULT_UDP_PORT))
        self.bind_host_var = tk.StringVar(value="0.0.0.0")
        self.bind_port_var = tk.StringVar(value=str(DEFAULT_BIND_PORT))
        self.serial_port_var = tk.StringVar(value="/dev/ttyUSB0")
        self.baud_var = tk.StringVar(value="115200")
        self.sysid_var = tk.StringVar(value=str(DEFAULT_SYSID))
        self.compid_var = tk.StringVar(value=str(DEFAULT_COMPID))

        ttk.Label(self.link_frame, text="Transport").grid(row=0, column=0, sticky="w")
        self.transport_combo = ttk.Combobox(self.link_frame, textvariable=self.transport_var, values=["UDP", "TCP server", "Serial"], width=11, state="readonly")
        self.transport_combo.grid(row=0, column=1, padx=(4, 12), sticky="w")
        self.transport_combo.bind("<<ComboboxSelected>>", lambda *_: self._update_link_fields())

        self.host_label = ttk.Label(self.link_frame, text="QGC host")
        self.host_label.grid(row=0, column=2, sticky="w")
        self.host_entry = ttk.Entry(self.link_frame, textvariable=self.host_var, width=14)
        self.host_entry.grid(row=0, column=3, padx=(4, 12), sticky="w")

        self.port_label = ttk.Label(self.link_frame, text="QGC port")
        self.port_label.grid(row=0, column=4, sticky="w")
        self.port_spin = ttk.Spinbox(self.link_frame, from_=1, to=65535, textvariable=self.port_var, width=8)
        self.port_spin.grid(row=0, column=5, padx=(4, 12), sticky="w")

        self.bind_port_label = ttk.Label(self.link_frame, text="Bind port")
        self.bind_port_label.grid(row=0, column=6, sticky="w")
        self.bind_port_spin = ttk.Spinbox(self.link_frame, from_=1, to=65535, textvariable=self.bind_port_var, width=8)
        self.bind_port_spin.grid(row=0, column=7, padx=(4, 12), sticky="w")

        self.serial_port_label = ttk.Label(self.link_frame, text="Serial port")
        self.serial_port_label.grid(row=0, column=8, sticky="w")
        self.serial_port_entry = ttk.Entry(self.link_frame, textvariable=self.serial_port_var, width=16)
        self.serial_port_entry.grid(row=0, column=9, padx=(4, 12), sticky="w")

        self.baud_label = ttk.Label(self.link_frame, text="Baud")
        self.baud_label.grid(row=0, column=10, sticky="w")
        self.baud_combo = ttk.Combobox(self.link_frame, textvariable=self.baud_var, values=["57600", "115200", "230400", "460800", "921600"], width=9, state="readonly")
        self.baud_combo.grid(row=0, column=11, padx=(4, 12), sticky="w")

        ttk.Label(self.link_frame, text="System ID").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Spinbox(self.link_frame, from_=1, to=255, textvariable=self.sysid_var, width=6).grid(row=1, column=1, padx=(4, 12), pady=(6, 0), sticky="w")
        ttk.Label(self.link_frame, text="Component ID").grid(row=1, column=2, sticky="w", pady=(6, 0))
        ttk.Spinbox(self.link_frame, from_=1, to=255, textvariable=self.compid_var, width=6).grid(row=1, column=3, padx=(4, 12), pady=(6, 0), sticky="w")
        ttk.Label(
            self.link_frame,
            text="Use a System ID different from other simulators (PX4/ArduPilot SITL default is 1).",
            style="Muted.TLabel",
        ).grid(row=1, column=4, columnspan=10, sticky="w", pady=(6, 0))

        self.connect_button = ttk.Button(self.link_frame, text="Connect", style="Accent.TButton", command=self._toggle_connection)
        self.connect_button.grid(row=0, column=12, padx=(4, 8), sticky="e")
        self.link_state_label = ttk.Label(self.link_frame, text="Disconnected", foreground="#ff9f43")
        self.link_state_label.grid(row=0, column=13, sticky="w")
        self._update_link_fields()

    def _build_status_bar(self) -> None:
        bar = ttk.Frame(self.root, padding=(8, 2, 8, 6))
        bar.pack(fill="x", side="bottom")
        self.stats_var = tk.StringVar(value="RX 0 | TX 0")
        ttk.Label(bar, textvariable=self.stats_var, style="Muted.TLabel").pack(side="left")
        self.save_note_var = tk.StringVar(value=str(self.store.path))
        ttk.Label(bar, textvariable=self.save_note_var, style="Muted.TLabel").pack(side="right")

    def _build_sim_tab(self) -> None:
        actions = ttk.Frame(self.sim_tab, padding=(8, 6))
        actions.pack(fill="x", side="top")
        self.auto_heartbeat_var = tk.BooleanVar(value=True)
        self.auto_telemetry_var = tk.BooleanVar(value=True)
        self.telemetry_interval_var = tk.DoubleVar(value=1.0)
        ttk.Checkbutton(actions, text="Auto heartbeat", variable=self.auto_heartbeat_var, command=self._apply_settings).pack(side="left")
        ttk.Checkbutton(actions, text="Auto telemetry", variable=self.auto_telemetry_var, command=self._apply_settings).pack(side="left", padx=(12, 0))
        ttk.Label(actions, text="Interval (s)").pack(side="left", padx=(16, 4))
        ttk.Spinbox(actions, from_=0.2, to=10.0, increment=0.2, textvariable=self.telemetry_interval_var, width=6, command=self._apply_settings).pack(side="left")
        ttk.Button(actions, text="Send telemetry now", command=self._send_telemetry_now).pack(side="left", padx=(16, 0))
        ttk.Button(actions, text="Send heartbeat", command=self._send_heartbeat_now).pack(side="left", padx=(8, 0))

        canvas = tk.Canvas(self.sim_tab, background=self.colors["bg"], highlightthickness=0)
        scrollbar = ttk.Scrollbar(self.sim_tab, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        inner = ttk.Frame(canvas, padding=8)
        inner.columnconfigure(0, weight=1)
        window_id = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>", lambda _e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.bind("<Configure>", lambda e: canvas.itemconfigure(window_id, width=e.width))

        self.vehicle_type_var = tk.StringVar(value="Quadrotor")
        self.autopilot_var = tk.StringVar(value="PX4")
        self.flight_mode_var = tk.StringVar(value="Position")
        self.custom_mode_var = tk.StringVar(value=str(DEFAULT_STATE["custom_mode"]))
        self.armed_var = tk.BooleanVar(value=False)
        self.prearm_var = tk.BooleanVar(value=True)
        self.landed_var = tk.StringVar(value="On ground")

        status = ttk.LabelFrame(inner, text="Status / nav bar title", padding=8)
        status.grid(row=0, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))
        status.columnconfigure(1, weight=1)
        status.columnconfigure(3, weight=1)
        ttk.Label(status, text="Autopilot").grid(row=0, column=0, sticky="w")
        self.autopilot_combo = ttk.Combobox(status, textvariable=self.autopilot_var, values=list(AUTOPILOTS.keys()), width=12, state="readonly")
        self.autopilot_combo.grid(row=0, column=1, sticky="w", padx=4, pady=2)
        self.autopilot_combo.bind("<<ComboboxSelected>>", lambda *_: self._refresh_mode_values())
        ttk.Label(status, text="Vehicle type").grid(row=0, column=2, sticky="w")
        self.vehicle_type_combo = ttk.Combobox(status, textvariable=self.vehicle_type_var, values=list(VEHICLE_TYPES.keys()), width=16, state="readonly")
        self.vehicle_type_combo.grid(row=0, column=3, sticky="w", padx=4, pady=2)

        ttk.Label(status, text="Flight mode").grid(row=1, column=0, sticky="w")
        self.flight_mode_combo = ttk.Combobox(status, textvariable=self.flight_mode_var, width=18, state="readonly")
        self.flight_mode_combo.grid(row=1, column=1, sticky="w", padx=4, pady=2)
        self.flight_mode_combo.bind("<<ComboboxSelected>>", lambda *_: self._on_flight_mode_changed())
        ttk.Label(status, text="Custom mode").grid(row=1, column=2, sticky="w")
        self.custom_mode_spin = ttk.Spinbox(status, from_=0, to=4294967295, textvariable=self.custom_mode_var, width=18)
        self.custom_mode_spin.grid(row=1, column=3, sticky="w", padx=4, pady=2)

        ttk.Checkbutton(status, text="Armed", variable=self.armed_var).grid(row=2, column=0, sticky="w", pady=2)
        ttk.Checkbutton(status, text="Pre-arm checks OK", variable=self.prearm_var).grid(row=2, column=1, sticky="w", pady=2)
        ttk.Label(status, text="Landed state").grid(row=2, column=2, sticky="w")
        self.landed_combo = ttk.Combobox(status, textvariable=self.landed_var, values=list(LANDED_STATES.keys()), width=14, state="readonly")
        self.landed_combo.grid(row=2, column=3, sticky="w", padx=4, pady=2)

        battery = ttk.LabelFrame(inner, text="Battery", padding=8)
        battery.grid(row=1, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))
        battery.columnconfigure(1, weight=1)
        self.battery_percent_var = tk.DoubleVar(value=100)
        self.battery_voltage_var = tk.DoubleVar(value=16.8)
        self.battery_current_var = tk.DoubleVar(value=5.0)
        self.battery_charging_var = tk.BooleanVar(value=False)
        ttk.Label(battery, text="Remaining %").grid(row=0, column=0, sticky="w")
        self.battery_scale = ttk.Scale(battery, from_=0, to=100, variable=self.battery_percent_var, orient="horizontal")
        self.battery_scale.grid(row=0, column=1, sticky="ew", padx=4)
        self.battery_spin = ttk.Spinbox(battery, from_=0, to=100, textvariable=self.battery_percent_var, width=6)
        self.battery_spin.grid(row=0, column=2, padx=4)
        ttk.Label(battery, text="Voltage (V)").grid(row=1, column=0, sticky="w")
        ttk.Spinbox(battery, from_=0.0, to=100.0, increment=0.1, textvariable=self.battery_voltage_var, width=10).grid(row=1, column=1, sticky="w", padx=4, pady=2)
        ttk.Label(battery, text="Current (A)").grid(row=2, column=0, sticky="w")
        ttk.Spinbox(battery, from_=0.0, to=300.0, increment=0.5, textvariable=self.battery_current_var, width=10).grid(row=2, column=1, sticky="w", padx=4, pady=2)
        ttk.Checkbutton(battery, text="Charging", variable=self.battery_charging_var).grid(row=3, column=0, columnspan=2, sticky="w", pady=2)

        gps = ttk.LabelFrame(inner, text="GPS", padding=8)
        gps.grid(row=2, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))
        gps.columnconfigure(1, weight=1)
        self.gps_fix_var = tk.StringVar(value="3D fix")
        self.gps_sats_var = tk.IntVar(value=12)
        self.lat_var = tk.StringVar(value="25.033964")
        self.lon_var = tk.StringVar(value="121.564468")
        self.alt_var = tk.DoubleVar(value=30.0)
        ttk.Label(gps, text="Fix").grid(row=0, column=0, sticky="w")
        ttk.Combobox(gps, textvariable=self.gps_fix_var, values=list(GPS_FIXES.keys()), width=14, state="readonly").grid(row=0, column=1, sticky="w", padx=4, pady=2)
        ttk.Label(gps, text="Satellites").grid(row=0, column=2, sticky="w")
        ttk.Spinbox(gps, from_=0, to=50, textvariable=self.gps_sats_var, width=8).grid(row=0, column=3, sticky="w", padx=4, pady=2)
        ttk.Label(gps, text="Latitude").grid(row=1, column=0, sticky="w")
        ttk.Entry(gps, textvariable=self.lat_var, width=16).grid(row=1, column=1, sticky="w", padx=4, pady=2)
        ttk.Label(gps, text="Longitude").grid(row=1, column=2, sticky="w")
        ttk.Entry(gps, textvariable=self.lon_var, width=16).grid(row=1, column=3, sticky="w", padx=4, pady=2)
        ttk.Label(gps, text="Altitude (m)").grid(row=2, column=0, sticky="w")
        ttk.Spinbox(gps, from_=-1000.0, to=10000.0, increment=1.0, textvariable=self.alt_var, width=10).grid(row=2, column=1, sticky="w", padx=4, pady=2)
        ttk.Label(gps, text="Nav bar satellite count is the GPS satellite count.", style="Muted.TLabel").grid(row=3, column=0, columnspan=4, sticky="w", pady=(4, 0))

        link = ttk.LabelFrame(inner, text="Link / RC", padding=8)
        link.grid(row=3, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))
        link.columnconfigure(1, weight=1)
        self.link_rssi_var = tk.IntVar(value=80)
        self.remote_rssi_var = tk.IntVar(value=80)
        self.rc_rssi_var = tk.IntVar(value=80)
        ttk.Label(link, text="Telemetry RSSI").grid(row=0, column=0, sticky="w")
        ttk.Scale(link, from_=0, to=100, variable=self.link_rssi_var, orient="horizontal").grid(row=0, column=1, sticky="ew", padx=4)
        ttk.Spinbox(link, from_=0, to=100, textvariable=self.link_rssi_var, width=6).grid(row=0, column=2, padx=4)
        ttk.Label(link, text="Remote RSSI").grid(row=1, column=0, sticky="w")
        ttk.Scale(link, from_=0, to=100, variable=self.remote_rssi_var, orient="horizontal").grid(row=1, column=1, sticky="ew", padx=4)
        ttk.Spinbox(link, from_=0, to=100, textvariable=self.remote_rssi_var, width=6).grid(row=1, column=2, padx=4)
        ttk.Label(link, text="RC RSSI").grid(row=2, column=0, sticky="w")
        ttk.Scale(link, from_=0, to=100, variable=self.rc_rssi_var, orient="horizontal").grid(row=2, column=1, sticky="ew", padx=4)
        ttk.Spinbox(link, from_=0, to=100, textvariable=self.rc_rssi_var, width=6).grid(row=2, column=2, padx=4)
        ttk.Label(link, text="The 2.4G Wi-Fi item is driven by Microhard, not MAVLink.", style="Muted.TLabel").grid(row=3, column=0, columnspan=3, sticky="w", pady=(4, 0))

        message = ttk.LabelFrame(inner, text="Message", padding=8)
        message.grid(row=4, column=0, sticky="nsew", padx=(0, 8), pady=(0, 8))
        message.columnconfigure(1, weight=1)
        self.severity_var = tk.StringVar(value="Warning")
        self.message_var = tk.StringVar(value="Test message from nav bar tester")
        ttk.Label(message, text="Severity").grid(row=0, column=0, sticky="w")
        ttk.Combobox(message, textvariable=self.severity_var, values=list(SEVERITIES.keys()), width=12, state="readonly").grid(row=0, column=1, sticky="w", padx=4, pady=2)
        ttk.Label(message, text="Text").grid(row=1, column=0, sticky="w")
        ttk.Entry(message, textvariable=self.message_var).grid(row=1, column=1, sticky="ew", padx=4, pady=2)
        ttk.Button(message, text="Send STATUSTEXT", command=self._send_message).grid(row=1, column=2, padx=4)

        # Any control change updates the simulator state and is persisted.
        vars_to_watch = [
            self.vehicle_type_var, self.autopilot_var, self.flight_mode_var, self.custom_mode_var,
            self.armed_var, self.prearm_var, self.landed_var,
            self.battery_percent_var, self.battery_voltage_var, self.battery_current_var,
            self.battery_charging_var, self.gps_fix_var, self.gps_sats_var,
            self.lat_var, self.lon_var, self.alt_var,
            self.link_rssi_var, self.remote_rssi_var, self.rc_rssi_var,
            self.auto_heartbeat_var, self.auto_telemetry_var, self.telemetry_interval_var,
        ]
        for var in vars_to_watch:
            var.trace_add("write", self._on_control_changed)

    def _build_params_tab(self) -> None:
        frame = ttk.Frame(self.params_tab, padding=8)
        frame.pack(fill="both", expand=True)
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", pady=(0, 6))
        ttk.Button(toolbar, text="Send selected", style="Accent.TButton", command=self._send_selected_param).pack(side="left")
        ttk.Button(toolbar, text="Send all params", command=self._send_all_params).pack(side="left", padx=6)
        ttk.Button(toolbar, text="Load defaults", command=self._load_default_params).pack(side="left", padx=6)
        ttk.Button(toolbar, text="Import…", command=self._import_params).pack(side="left", padx=6)
        ttk.Button(toolbar, text="Export…", command=self._export_params).pack(side="left", padx=6)
        ttk.Label(toolbar, text="Request reply delay (s)").pack(side="left", padx=(16, 4))
        self.param_reply_delay_var = tk.DoubleVar(value=DEFAULT_PARAM_REPLY_DELAY)
        ttk.Spinbox(
            toolbar,
            from_=0.0,
            to=60.0,
            increment=0.5,
            textvariable=self.param_reply_delay_var,
            width=6,
            command=self._apply_settings,
        ).pack(side="left")
        self.param_reply_delay_var.trace_add("write", lambda *_: self._apply_settings())

        columns = ("value", "type", "source", "updated")
        self.param_tree = ttk.Treeview(frame, columns=columns, show="tree headings", height=16)
        self.param_tree.heading("#0", text="Parameter")
        self.param_tree.heading("value", text="Value")
        self.param_tree.heading("type", text="Type")
        self.param_tree.heading("source", text="Source")
        self.param_tree.heading("updated", text="Updated")
        self.param_tree.column("#0", width=260, stretch=True)
        self.param_tree.column("value", width=120, anchor="e")
        self.param_tree.column("type", width=90, anchor="center")
        self.param_tree.column("source", width=110, anchor="center")
        self.param_tree.column("updated", width=90, anchor="center")
        self.param_tree.pack(fill="both", expand=True)
        self.param_tree.bind("<<TreeviewSelect>>", self._on_param_selected)

        editor = ttk.LabelFrame(frame, text="Parameter editor / remembered QGC variables", padding=8)
        editor.pack(fill="x", pady=(8, 0))
        self.param_name_var = tk.StringVar()
        self.param_value_var = tk.StringVar()
        self.param_type_var = tk.StringVar(value="REAL32")
        self.param_source_var = tk.StringVar(value="")
        ttk.Label(editor, text="Name").grid(row=0, column=0, sticky="w")
        ttk.Entry(editor, textvariable=self.param_name_var, width=22).grid(row=0, column=1, sticky="w", padx=4, pady=2)
        ttk.Label(editor, text="Value").grid(row=0, column=2, sticky="w")
        ttk.Entry(editor, textvariable=self.param_value_var, width=16).grid(row=0, column=3, sticky="w", padx=4, pady=2)
        ttk.Label(editor, text="Type").grid(row=0, column=4, sticky="w")
        ttk.Combobox(editor, textvariable=self.param_type_var, values=list(PARAM_TYPES.keys()), width=10, state="readonly").grid(row=0, column=5, sticky="w", padx=4, pady=2)
        ttk.Label(editor, text="Source").grid(row=0, column=6, sticky="w")
        ttk.Label(editor, textvariable=self.param_source_var, style="Muted.TLabel").grid(row=0, column=7, sticky="w", padx=4)
        buttons = ttk.Frame(editor)
        buttons.grid(row=1, column=0, columnspan=8, sticky="w", pady=(6, 0))
        ttk.Button(buttons, text="Add / update", command=self._upsert_param_from_editor).pack(side="left")
        ttk.Button(buttons, text="Send this value", command=self._send_editor_param).pack(side="left", padx=6)
        ttk.Button(buttons, text="Delete selected", command=self._delete_selected_param).pack(side="left", padx=6)
        ttk.Label(editor, text="Values received from QGC are remembered here and saved automatically.", style="Muted.TLabel").grid(row=2, column=0, columnspan=8, sticky="w", pady=(6, 0))

    def _build_memory_tab(self) -> None:
        frame = ttk.Frame(self.memory_tab, padding=8)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text="Parameters and commands received from QGC (persisted in state.json)", style="Muted.TLabel").pack(anchor="w", pady=(0, 6))
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", pady=(0, 6))
        ttk.Button(toolbar, text="Clear memory", command=self._clear_memory).pack(side="left")
        self.memory_tree = ttk.Treeview(frame, columns=("time", "type", "name", "value"), show="headings", height=18)
        for col, text, width in (("time", "Time", 80), ("type", "Type", 150), ("name", "Name", 200), ("value", "Value", 420)):
            self.memory_tree.heading(col, text=text)
            self.memory_tree.column(col, width=width, anchor="w")
        self.memory_tree.pack(fill="both", expand=True)

    def _build_log_tab(self) -> None:
        frame = ttk.Frame(self.log_tab, padding=8)
        frame.pack(fill="both", expand=True)
        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x", pady=(0, 6))
        ttk.Button(toolbar, text="Clear log", command=self._clear_log).pack(side="left")
        ttk.Button(toolbar, text="Save log…", command=self._save_log).pack(side="left", padx=6)
        self.verbose_rx_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(toolbar, text="Log all incoming MAVLink messages", variable=self.verbose_rx_var, command=self._apply_settings).pack(side="left", padx=12)
        self.log_text = scrolledtext.ScrolledText(frame, wrap="word", background=self.colors["field"], foreground=self.colors["fg"], insertbackground=self.colors["fg"], height=24)
        self.log_text.pack(fill="both", expand=True)
        self._log("info", "QGC Nav Bar Tester ready. Configure the link and press Connect.")

    # --------------------------------------------------------------- state sync
    def _load_initial_state(self) -> None:
        data = self.saved_state or {}
        link = data.get("link") or {}
        self.transport_var.set(link.get("transport", "UDP"))
        self.host_var.set(link.get("host", DEFAULT_UDP_HOST))
        self.port_var.set(str(link.get("port", DEFAULT_UDP_PORT)))
        self.bind_host_var.set(link.get("bind_host", "0.0.0.0"))
        self.bind_port_var.set(str(link.get("bind_port", DEFAULT_BIND_PORT)))
        self.serial_port_var.set(link.get("serial_port", "/dev/ttyUSB0"))
        self.baud_var.set(str(link.get("baud", 115200)))
        self.sysid_var.set(str(link.get("sysid", self.args.sysid)))
        self.compid_var.set(str(link.get("compid", self.args.compid)))

        sim_data = data.get("sim") or {}
        if sim_data:
            self.sim.import_state({"sim": sim_data})
        self.sim.import_state(
            {
                "params": data.get("params", []),
                "sim": data.get("sim", {}),
                "memory": data.get("memory", []),
                "settings": data.get("settings", {}),
            }
        )
        if not self.sim.params:
            self._seed_default_params()
        self._update_link_fields()

    def _sync_ui_from_sim(self) -> None:
        self._loading_ui = True
        try:
            state = self.sim.state_snapshot()
            self.vehicle_type_var.set(VEHICLE_TYPE_NAMES.get(int(state["vehicle_type"]), "Quadrotor"))
            self.autopilot_var.set(AUTOPILOT_NAMES.get(int(state["autopilot"]), "PX4"))
            self.flight_mode_var.set(str(state.get("flight_mode_name", "Position")))
            self.custom_mode_var.set(str(state.get("custom_mode", 0)))
            self.armed_var.set(bool(state.get("armed", False)))
            self.prearm_var.set(bool(state.get("prearm_ok", True)))
            self.landed_var.set(LANDED_NAMES.get(int(state.get("landed_state", 1)), "On ground"))
            self.battery_percent_var.set(float(state.get("battery_percent", 100)))
            self.battery_voltage_var.set(float(state.get("battery_voltage", 16.8)))
            self.battery_current_var.set(float(state.get("battery_current", 5.0)))
            self.battery_charging_var.set(bool(state.get("battery_charging", False)))
            self.gps_fix_var.set(GPS_FIX_NAMES.get(int(state.get("gps_fix", 3)), "3D fix"))
            self.gps_sats_var.set(int(state.get("gps_sats", 12)))
            self.lat_var.set("%.7f" % float(state.get("lat", 25.033964)))
            self.lon_var.set("%.7f" % float(state.get("lon", 121.564468)))
            self.alt_var.set(float(state.get("alt", 30.0)))
            self.link_rssi_var.set(int(state.get("link_rssi", 80)))
            self.remote_rssi_var.set(int(state.get("remote_rssi", 80)))
            self.rc_rssi_var.set(int(state.get("rc_rssi", 80)))
            settings = self.saved_state.get("settings") or {}
            self.auto_heartbeat_var.set(bool(settings.get("heartbeat_enabled", self.sim.heartbeat_enabled)))
            self.auto_telemetry_var.set(bool(settings.get("auto_telemetry", self.sim.auto_telemetry)))
            self.telemetry_interval_var.set(float(settings.get("telemetry_interval", self.sim.telemetry_interval)))
            self.param_reply_delay_var.set(float(settings.get("param_reply_delay", self.sim.param_reply_delay)))
            self.verbose_rx_var.set(bool(settings.get("verbose_rx", False)))
            self._refresh_mode_values()
            for name, entry in self._sorted_param_items():
                self._upsert_param_row(name, entry)
            for item in self.sim.memory:
                self._insert_memory_row(item)
        finally:
            self._loading_ui = False

    def _seed_default_params(self) -> None:
        for name, value, ptype in DEFAULT_PARAMS:
            self.sim.add_or_update_param(name, value, ptype, source="default", send=False)

    def _sorted_param_items(self) -> List[Tuple[str, Dict[str, Any]]]:
        return sorted(self.sim.params.items(), key=lambda item: item[0].lower())

    def _refresh_mode_values(self) -> None:
        if not hasattr(self, "flight_mode_combo"):
            return
        modes = PX4_MODES if self.autopilot_var.get() == "PX4" else APM_MODES
        self.flight_mode_combo.configure(values=list(modes.keys()))
        current = self.flight_mode_var.get()
        if current not in modes:
            current = next(iter(modes.keys()))
            self.flight_mode_var.set(current)
        self.custom_mode_var.set(str(modes[current]))

    def _on_flight_mode_changed(self) -> None:
        modes = PX4_MODES if self.autopilot_var.get() == "PX4" else APM_MODES
        mode = self.flight_mode_var.get()
        if mode in modes:
            self.custom_mode_var.set(str(modes[mode]))
            self.sim.update_state(flight_mode_name=mode, custom_mode=modes[mode])
            self._schedule_save()

    def _on_control_changed(self, *_args: Any) -> None:
        if self._loading_ui:
            return
        self._apply_settings()
        try:
            state = {
                "vehicle_type": VEHICLE_TYPES.get(self.vehicle_type_var.get(), DEFAULT_STATE["vehicle_type"]),
                "autopilot": AUTOPILOTS.get(self.autopilot_var.get(), DEFAULT_STATE["autopilot"]),
                "flight_mode_name": self.flight_mode_var.get(),
                "custom_mode": int(float(self.custom_mode_var.get() or 0)),
                "armed": bool(self.armed_var.get()),
                "prearm_ok": bool(self.prearm_var.get()),
                "landed_state": LANDED_STATES.get(self.landed_var.get(), 1),
                "battery_percent": int(round(float(self.battery_percent_var.get()))),
                "battery_voltage": float(self.battery_voltage_var.get()),
                "battery_current": float(self.battery_current_var.get()),
                "battery_charging": bool(self.battery_charging_var.get()),
                "gps_fix": GPS_FIXES.get(self.gps_fix_var.get(), 3),
                "gps_sats": int(self.gps_sats_var.get()),
                "lat": float(self.lat_var.get()),
                "lon": float(self.lon_var.get()),
                "alt": float(self.alt_var.get()),
                "link_rssi": int(self.link_rssi_var.get()),
                "remote_rssi": int(self.remote_rssi_var.get()),
                "rc_rssi": int(self.rc_rssi_var.get()),
            }
            self.sim.update_state(**state)
        except (ValueError, TypeError):
            pass
        self._schedule_save()

    def _apply_settings(self) -> None:
        if self._loading_ui:
            return
        self.sim.heartbeat_enabled = bool(self.auto_heartbeat_var.get())
        self.sim.auto_telemetry = bool(self.auto_telemetry_var.get())
        try:
            self.sim.telemetry_interval = max(0.2, min(10.0, float(self.telemetry_interval_var.get())))
        except Exception:
            self.sim.telemetry_interval = 1.0
        delay_var = getattr(self, "param_reply_delay_var", None)
        if delay_var is not None:
            try:
                self.sim.param_reply_delay = max(0.0, min(60.0, float(delay_var.get())))
            except Exception:
                self.sim.param_reply_delay = DEFAULT_PARAM_REPLY_DELAY
        self.sim.verbose_rx = bool(self.verbose_rx_var.get())
        self._schedule_save()

    # ----------------------------------------------------------------- link UI
    def _update_link_fields(self) -> None:
        transport = self.transport_var.get().upper()
        is_udp = transport == "UDP"
        is_tcp = transport == "TCP SERVER"
        is_serial = transport == "SERIAL"
        for widget in (self.host_label, self.host_entry, self.port_label, self.port_spin):
            widget.grid() if is_udp else widget.grid_remove()
        for widget in (self.bind_port_label, self.bind_port_spin):
            widget.grid() if (is_udp or is_tcp) else widget.grid_remove()
        for widget in (self.serial_port_label, self.serial_port_entry, self.baud_label, self.baud_combo):
            widget.grid() if is_serial else widget.grid_remove()

    def _toggle_connection(self) -> None:
        if self._link_connected:
            self.sim.disconnect()
            self._link_connected = False
            self.connect_button.configure(text="Connect")
            self.link_state_label.configure(text="Disconnected", foreground="#ff9f43")
        else:
            self._connect()

    def _connect(self) -> None:
        try:
            transport = self.transport_var.get().upper()
            host = self.host_var.get().strip() or DEFAULT_UDP_HOST
            port = int(self.port_var.get())
            bind_host = self.bind_host_var.get().strip() or "0.0.0.0"
            bind_port = int(self.bind_port_var.get())
            serial_port = self.serial_port_var.get().strip()
            baud = int(self.baud_var.get())
            self.sim.set_ids(int(self.sysid_var.get()), int(self.compid_var.get()))
            self._log("info", "MAVLink sysid=%d compid=%d" % (self.sim.sysid, self.sim.compid))
            endpoint = Endpoint(
                transport=transport,
                host=host,
                port=port,
                bind_host=bind_host,
                bind_port=bind_port,
                serial_port=serial_port,
                baud=baud,
                on_bytes=self.sim.feed_bytes,
                on_log=lambda level, text: self.events.put(("log", level, text)),
            )
            self.sim.connect(endpoint)
            self._link_connected = True
            self.connect_button.configure(text="Disconnect")
            self.link_state_label.configure(text="Connected", foreground="#00d084")
            self._schedule_save()
        except Exception as exc:
            try:
                self.sim.disconnect()
            except Exception:
                pass
            self._link_connected = False
            self.connect_button.configure(text="Connect")
            self.link_state_label.configure(text="Disconnected", foreground="#ff9f43")
            messagebox.showerror(APP_NAME, "Unable to open link:\n%s" % exc)
            self._log("error", "Link error: %s" % exc)

    # ------------------------------------------------------------- actions
    def _send_message(self) -> None:
        severity = SEVERITIES.get(self.severity_var.get(), 4)
        text = self.message_var.get().strip()
        if text:
            self.sim.send_statustext(severity, text)

    def _send_telemetry_now(self) -> None:
        self.sim.send_telemetry()
        self._log("tx", "Telemetry bundle sent")

    def _send_heartbeat_now(self) -> None:
        self.sim.send_heartbeat()
        self._log("tx", "Heartbeat sent")

    # ------------------------------------------------------------- params UI
    def _upsert_param_row(self, name: str, entry: Dict[str, Any]) -> None:
        values = (
            _format_param_value(entry.get("value", "")),
            _param_type_name(int(entry.get("type", PARAM_TYPES["REAL32"]))),
            entry.get("source", ""),
            entry.get("updated", ""),
        )
        if self.param_tree.exists(name):
            self.param_tree.item(name, values=values)
        else:
            self.param_tree.insert("", "end", iid=name, text=name, values=values)

    def _on_param_selected(self, _event: Any = None) -> None:
        selection = self.param_tree.selection()
        if not selection:
            return
        name = selection[0]
        entry = self.sim.params.get(name)
        if entry is None:
            return
        self.param_name_var.set(name)
        self.param_value_var.set(_format_param_value(entry["value"]))
        self.param_type_var.set(_param_type_name(int(entry["type"])))
        self.param_source_var.set(str(entry.get("source", "")))

    def _upsert_param_from_editor(self, send: bool = False) -> None:
        name = self.param_name_var.get().strip()
        if not name:
            messagebox.showwarning(APP_NAME, "Parameter name is required.")
            return
        if len(name) > MAX_PARAM_NAME:
            messagebox.showwarning(APP_NAME, "Parameter names are limited to %d characters." % MAX_PARAM_NAME)
            return
        try:
            value = self.param_value_var.get().strip()
        except Exception:
            value = "0"
        if not self.sim.add_or_update_param(name, value, self.param_type_var.get(), source="local", send=send):
            return
        self.param_source_var.set("local")
        self._schedule_save()

    def _send_editor_param(self) -> None:
        self._upsert_param_from_editor(send=True)

    def _send_selected_param(self) -> None:
        selection = self.param_tree.selection()
        if selection:
            self.sim.send_param_value(selection[0])
            self._log("tx", "PARAM_VALUE %s" % selection[0])

    def _send_all_params(self) -> None:
        self.sim.send_all_params()

    def _delete_selected_param(self) -> None:
        selection = self.param_tree.selection()
        for name in selection:
            self.sim.delete_param(name)
        self._schedule_save()

    def _load_default_params(self) -> None:
        for name, value, ptype in DEFAULT_PARAMS:
            if name not in self.sim.params:
                self.sim.add_or_update_param(name, value, ptype, source="default")
        self._schedule_save()

    def _import_params(self) -> None:
        path = filedialog.askopenfilename(title="Import parameters", filetypes=[("JSON", "*.json"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            rows = data.get("params", data) if isinstance(data, dict) else data
            for row in rows:
                if isinstance(row, dict):
                    name = row.get("name") or row.get("param")
                    value = row.get("value", 0)
                    ptype = _param_type_name(int(row.get("type", PARAM_TYPES["REAL32"]))) if isinstance(row.get("type"), int) else row.get("type", "REAL32")
                    if name:
                        self.sim.add_or_update_param(name, value, ptype, source="import")
        except Exception as exc:
            messagebox.showerror(APP_NAME, "Import failed:\n%s" % exc)

    def _export_params(self) -> None:
        path = filedialog.asksaveasfilename(title="Export parameters", defaultextension=".json", filetypes=[("JSON", "*.json")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump({"params": self.sim.export_state()["params"]}, fh, indent=2, ensure_ascii=False)
        except Exception as exc:
            messagebox.showerror(APP_NAME, "Export failed:\n%s" % exc)

    # ------------------------------------------------------------- memory/log
    def _insert_memory_row(self, item: Dict[str, Any]) -> None:
        self.memory_tree.insert(
            "",
            0,
            values=(
                item.get("time", ""),
                item.get("type", ""),
                item.get("name", ""),
                item.get("value", ""),
            ),
        )

    def _clear_memory(self) -> None:
        self.sim.memory.clear()
        for child in self.memory_tree.get_children():
            self.memory_tree.delete(child)
        self._schedule_save()

    def _log(self, level: str, text: str) -> None:
        prefix = {"info": "•", "rx": "←", "tx": "→", "error": "!"}.get(level, "•")
        line = "%s %s %s\n" % (_now_stamp(), prefix, text)
        self.log_text.insert("end", line)
        self.log_text.see("end")
        try:
            self.log_text.tag_add(level, "end-2l", "end-1c")
            self.log_text.tag_config(level, foreground={"rx": "#7fd1ff", "tx": "#9ee37d", "error": "#ff7b72"}.get(level, self.colors["fg"]))
        except Exception:
            pass

    def _clear_log(self) -> None:
        self.log_text.delete("1.0", "end")

    def _save_log(self) -> None:
        path = filedialog.asksaveasfilename(title="Save log", defaultextension=".txt", filetypes=[("Text", "*.txt"), ("All files", "*.*")])
        if not path:
            return
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(self.log_text.get("1.0", "end"))
        except Exception as exc:
            messagebox.showerror(APP_NAME, "Save failed:\n%s" % exc)

    # ------------------------------------------------------------------ events
    def _poll_events(self) -> None:
        try:
            for _ in range(300):
                event = self.events.get_nowait()
                kind = event[0]
                if kind == "log":
                    self._log(event[1], event[2])
                elif kind == "param":
                    self._upsert_param_row(event[1], event[2])
                elif kind == "param_deleted":
                    if self.param_tree.exists(event[1]):
                        self.param_tree.delete(event[1])
                elif kind == "memory":
                    self._insert_memory_row(event[1])
                elif kind == "state":
                    self._apply_remote_state(event[1])
                elif kind == "link":
                    self._link_connected = bool(event[1])
                    self.connect_button.configure(text="Disconnect" if self._link_connected else "Connect")
                    self.link_state_label.configure(text=event[2], foreground="#00d084" if self._link_connected else "#ff9f43")
        except queue.Empty:
            pass
        self.stats_var.set("RX %d | TX %d" % (self.sim.rx_count, self.sim.tx_count))
        self.root.after(80, self._poll_events)

    def _apply_remote_state(self, changes: Dict[str, Any]) -> None:
        self._loading_ui = True
        try:
            if "armed" in changes:
                self.armed_var.set(bool(changes["armed"]))
            if "custom_mode" in changes:
                self.custom_mode_var.set(str(changes["custom_mode"]))
            if "flight_mode_name" in changes:
                self.flight_mode_var.set(str(changes["flight_mode_name"]))
            if "prearm_ok" in changes:
                self.prearm_var.set(bool(changes["prearm_ok"]))
            if "landed_state" in changes:
                self.landed_var.set(LANDED_NAMES.get(int(changes["landed_state"]), "On ground"))
        finally:
            self._loading_ui = False

    # ------------------------------------------------------------------- save
    def _schedule_save(self) -> None:
        if self._save_after_id is not None:
            try:
                self.root.after_cancel(self._save_after_id)
            except Exception:
                pass
        self._save_after_id = self.root.after(700, self._save_state)

    def _save_state(self) -> None:
        self._save_after_id = None
        data = self.sim.export_state()
        data["link"] = {
            "transport": self.transport_var.get(),
            "host": self.host_var.get(),
            "port": self.port_var.get(),
            "bind_host": self.bind_host_var.get(),
            "bind_port": self.bind_port_var.get(),
            "serial_port": self.serial_port_var.get(),
            "baud": self.baud_var.get(),
            "sysid": self.sysid_var.get(),
            "compid": self.compid_var.get(),
        }
        data["settings"]["verbose_rx"] = bool(self.verbose_rx_var.get())
        data["settings"]["heartbeat_enabled"] = bool(self.auto_heartbeat_var.get())
        data["settings"]["auto_telemetry"] = bool(self.auto_telemetry_var.get())
        try:
            data["settings"]["telemetry_interval"] = float(self.telemetry_interval_var.get())
        except Exception:
            data["settings"]["telemetry_interval"] = 1.0
        delay_var = getattr(self, "param_reply_delay_var", None)
        if delay_var is not None:
            try:
                data["settings"]["param_reply_delay"] = float(delay_var.get())
            except Exception:
                data["settings"]["param_reply_delay"] = DEFAULT_PARAM_REPLY_DELAY
        self.store.save(data)

    def _on_close(self) -> None:
        try:
            self._save_state()
        except Exception:
            pass
        try:
            self.sim.disconnect()
        except Exception:
            pass
        self.root.destroy()


def run_self_test() -> int:
    codec = MavlinkCodec(1, 1)
    parser = MavlinkCodec(2, 1)
    msg = codec.sender.heartbeat_encode(
        int(getattr(mavlink2, "MAV_TYPE_QUADROTOR", 2)),
        int(getattr(mavlink2, "MAV_AUTOPILOT_PX4", 12)),
        1,
        196608,
        int(getattr(mavlink2, "MAV_STATE_ACTIVE", 4)),
    )
    data = codec.pack(msg)
    parsed = parser.parse(data)
    assert parsed and parsed[0].get_type() == "HEARTBEAT", "heartbeat encode/decode failed"

    events: "queue.Queue[Tuple[Any, ...]]" = queue.Queue()
    sim = VehicleSimulator(events.put)
    sim.add_or_update_param("TEST_PARAM", 1.25, "REAL32")
    assert sim.params["TEST_PARAM"]["value"] == 1.25
    state = sim.export_state()
    sim2 = VehicleSimulator(events.put)
    sim2.import_state(state)
    assert sim2.params["TEST_PARAM"]["value"] == 1.25
    assert sim2.param_reply_delay == DEFAULT_PARAM_REPLY_DELAY
    print("SELF-TEST OK")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=APP_NAME)
    parser.add_argument("--host", default=DEFAULT_UDP_HOST, help="QGC UDP host (default 127.0.0.1)")
    parser.add_argument("--port", type=int, default=DEFAULT_UDP_PORT, help="QGC UDP/TCP port (default 14550)")
    parser.add_argument("--bind-port", type=int, default=DEFAULT_BIND_PORT, help="local bind port (default 14555)")
    parser.add_argument("--serial-port", default="/dev/ttyUSB0", help="serial port for Serial transport")
    parser.add_argument("--baud", type=int, default=115200, help="serial baud rate")
    parser.add_argument("--sysid", type=int, default=DEFAULT_SYSID, help="MAVLink system id (default 42; PX4/ArduPilot SITL usually uses 1)")
    parser.add_argument("--compid", type=int, default=DEFAULT_COMPID, help="MAVLink component id (default 1)")
    parser.add_argument("--state-file", default=str(DEFAULT_STATE_PATH), help="JSON file used to remember parameters/state")
    parser.add_argument("--auto-connect", action="store_true", help="open the saved link on startup")
    parser.add_argument("--allow-multiple", action="store_true", help="allow a second tester instance")
    parser.add_argument("--self-test", action="store_true", help="run a headless encode/decode test and exit")
    args = parser.parse_args()

    if args.self_test:
        return run_self_test()

    lock = None
    if not args.allow_multiple:
        lock = acquire_instance_lock(Path.home() / ".qgc_navbar_tester" / "tester.lock")
        if lock is None:
            print(
                "Another QGC Nav Bar Tester instance is already running.\n"
                "Close it first, or pass --allow-multiple if you really need two instances.",
                file=sys.stderr,
            )
            return 1

    root = tk.Tk()
    app = QGCNavBarTesterApp(root, args)
    # Command-line values override the saved link on first launch.
    if not app.saved_state.get("link"):
        app.host_var.set(args.host)
        app.port_var.set(str(args.port))
        app.bind_port_var.set(str(args.bind_port))
        app.serial_port_var.set(args.serial_port)
        app.baud_var.set(str(args.baud))
    root.protocol("WM_DELETE_WINDOW", app._on_close)
    try:
        root.mainloop()
    finally:
        if lock is not None:
            try:
                lock.close()
            except Exception:
                pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

