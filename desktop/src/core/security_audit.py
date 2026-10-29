"""Tamper-evident local audit records plus host-independent event retention.

The local JSONL file is chained with the active cryptographic suite so edits or
removals become detectable. Every record is also sent to the operating
system's independent log service: Windows Event Log or POSIX syslog.
"""
from __future__ import annotations

import ctypes
import hmac
import json
import os
from pathlib import Path
from typing import Any, NoReturn, Protocol

from core import atomic_write, crypto_policy, storage

AUDIT_NAME = "security-audit.jsonl"
ENV_FILE = "NF_SECURITY_AUDIT_FILE"
MAX_AUDIT_ROW_BYTES = 64 << 10


class EventSink(Protocol):
    kind: str

    def emit(self, payload: str) -> None:
        ...


class WindowsEventLogSink:
    """Write warning records to the Windows Application event log."""

    kind = "windows-eventlog"
    EVENTLOG_WARNING_TYPE = 0x0002

    def emit(self, payload: str) -> None:
        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        advapi32.RegisterEventSourceW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
        advapi32.RegisterEventSourceW.restype = ctypes.c_void_p
        advapi32.ReportEventW.argtypes = [
            ctypes.c_void_p,
            ctypes.c_ushort,
            ctypes.c_ushort,
            ctypes.c_uint,
            ctypes.c_void_p,
            ctypes.c_ushort,
            ctypes.c_uint,
            ctypes.POINTER(ctypes.c_wchar_p),
            ctypes.c_void_p,
        ]
        advapi32.ReportEventW.restype = ctypes.c_int
        advapi32.DeregisterEventSource.argtypes = [ctypes.c_void_p]
        handle = advapi32.RegisterEventSourceW(None, "Application")
        if not handle:
            raise OSError(ctypes.get_last_error(), "RegisterEventSourceW failed")
        strings = (ctypes.c_wchar_p * 1)(payload)
        try:
            ok = advapi32.ReportEventW(
                handle,
                self.EVENTLOG_WARNING_TYPE,
                0,
                1,
                None,
                1,
                0,
                strings,
                None,
            )
            if not ok:
                raise OSError(ctypes.get_last_error(), "ReportEventW failed")
        finally:
            advapi32.DeregisterEventSource(handle)


class PosixSyslogSink:
    """Send warning records to the host syslog daemon."""

    kind = "posix-syslog"

    def emit(self, payload: str) -> None:
        import syslog

        syslog.openlog("ninfenz", syslog.LOG_PID, syslog.LOG_AUTH)
        syslog.syslog(syslog.LOG_WARNING, payload)


def default_sink() -> EventSink:
    if os.name == "nt":
        return WindowsEventLogSink()
    return PosixSyslogSink()


def default_path() -> Path:
    override = os.environ.get(ENV_FILE)
    if override:
        return Path(override)
    return Path(storage.default_home()) / AUDIT_NAME


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")


def _audit_error(path: Path, detail: str, cause: Exception | None = None) -> NoReturn:
    raise ValueError(
        f"{path}: {detail}"
        "（修复指引：停止写入并检查磁盘、权限与审计记录完整性后重建或恢复）"
    ) from cause


def _digest(suite_name: str, prev: str, payload: dict[str, Any]) -> str:
    policy = crypto_policy.CryptoPolicy(suite_name)
    preimage = prev.encode("ascii") + b"\n" + _canonical(payload)
    return policy.digest_hex(preimage)


class SecurityAuditLog:
    """Append-only local hash chain with an independent host-log tee."""

    def __init__(self, path: str | Path, sink: EventSink | None = None):
        self.path = Path(path)
        self.sink = sink or default_sink()

    def _rows(self) -> list[dict[str, Any]]:
        if not self.path.is_file():
            return []
        rows: list[dict[str, Any]] = []
        for line_no, line in enumerate(
            self.path.read_text(encoding="utf-8").splitlines(), 1
        ):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                _audit_error(self.path, f"line {line_no}: audit row must be an object")
            rows.append(value)
        return rows

    def _last_digest(self) -> str:
        """Read only the final record so append cost is independent of history size."""
        try:
            with self.path.open("rb") as handle:
                handle.seek(0, os.SEEK_END)
                pos = handle.tell()
                if pos == 0:
                    return ""
                data = b""
                while pos > 0 and len(data) <= MAX_AUDIT_ROW_BYTES + 2:
                    size = min(8192, pos)
                    pos -= size
                    handle.seek(pos)
                    data = handle.read(size) + data
                    stripped = data.rstrip(b"\r\n")
                    if b"\n" in stripped:
                        data = stripped.rsplit(b"\n", 1)[-1]
                        break
                else:
                    data = data.rstrip(b"\r\n")
        except OSError:
            return ""
        if len(data) > MAX_AUDIT_ROW_BYTES:
            _audit_error(self.path, "final audit record exceeds the size limit")
        try:
            row = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            _audit_error(self.path, "final audit record is malformed", exc)
        if not isinstance(row, dict):
            _audit_error(self.path, "final audit record must be an object")
        return str(row.get("digest") or "")

    def append(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with atomic_write.lock_file(self.path, what="security audit append"):
            prev = self._last_digest()
            policy = crypto_policy.CryptoPolicy()
            record = {
                "alg": policy.suite_id,
                "digest": _digest(policy.suite_id, prev, payload),
                "payload": payload,
                "prev": prev,
            }
            encoded = _canonical(record) + b"\n"
            fd = os.open(
                self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600
            )
            try:
                view = memoryview(encoded)
                while view:
                    written = os.write(fd, view)
                    if written <= 0:
                        _audit_error(self.path, "short write to security audit log")
                    view = view[written:]
                os.fsync(fd)
            finally:
                os.close(fd)
            if os.name == "posix":
                os.chmod(self.path, 0o600)
        self.sink.emit(_canonical(record).decode("utf-8"))
        return record

    def verify(self) -> list[str]:
        issues: list[str] = []
        prev = ""
        try:
            rows = self._rows()
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            return [f"audit log unreadable: {exc}"]
        for index, row in enumerate(rows, 1):
            suite_name = str(row.get("alg") or "")
            try:
                crypto_policy.get_suite(suite_name)
            except ValueError:
                issues.append(f"{self.path}:{index}: unknown crypto suite {suite_name!r}")
                continue
            if str(row.get("prev") or "") != prev:
                issues.append(f"{self.path}:{index}: previous digest mismatch")
            payload = row.get("payload")
            if not isinstance(payload, dict):
                issues.append(f"{self.path}:{index}: payload must be an object")
                continue
            expected = _digest(suite_name, prev, payload)
            if not hmac.compare_digest(expected, str(row.get("digest") or "")):
                issues.append(f"{self.path}:{index}: digest mismatch")
            prev = str(row.get("digest") or "")
        return issues


def record(payload: dict[str, Any]) -> dict[str, Any]:
    """Append one payload to the default NF audit chain and OS log sink."""
    return SecurityAuditLog(default_path()).append(payload)


def verify(path: str | Path | None = None) -> list[str]:
    return SecurityAuditLog(path or default_path(), sink=default_sink()).verify()


__all__ = [
    "AUDIT_NAME",
    "ENV_FILE",
    "PosixSyslogSink",
    "SecurityAuditLog",
    "WindowsEventLogSink",
    "default_path",
    "default_sink",
    "record",
    "verify",
]
