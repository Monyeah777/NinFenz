"""pytest 公共夹具/工具。

- 仓库根 = parents[2]；app/cli 加进 sys.path（python -m nf_app 需要）。
- run_cli：以子进程方式跑 python -m nf_app（cwd=仓库根），断言 --json 单行信封。
- core fixture：Rust 核心（app/core/target/{release,debug}/nf-app-core[.exe] 或 NF_APP_CORE）。
  核心缺失时用 pytest.xfail 显式挂起（owner: rust-core）；最终必须去掉，
  设 NF_REQUIRE_CORE=1 可直接失败以便门禁。
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
APP = REPO / "app"
CLI_DIR = APP / "cli"
SCHEMA_DIR = APP / "schema"
FIXTURES = APP / "fixtures"
TESTS_DIR = APP / "tests"

if str(CLI_DIR) not in sys.path:
    sys.path.insert(0, str(CLI_DIR))


class CliResult:
    def __init__(self, proc: subprocess.CompletedProcess) -> None:
        self.proc = proc
        self.returncode = proc.returncode
        self.stdout = proc.stdout.decode("utf-8", errors="replace")
        self.stderr = proc.stderr.decode("utf-8", errors="replace")

    def json(self) -> dict:
        text = self.stdout.strip()
        assert text, f"stdout 为空（stderr={self.stderr[:1000]}）"
        assert "\n" not in text, f"--json 必须是单行 JSON，实际 stdout={text!r}"
        return json.loads(text)

    def envelope(self) -> dict:
        env = self.json()
        assert set(env) == {"ok", "exit", "result", "error"}, env
        assert env["exit"] == self.returncode, (env, self.returncode)
        assert env["ok"] is (env["exit"] == 0), env
        if env["exit"] != 0:
            assert env["error"] and env["error"]["code"], env
            assert env["error"]["message"] and env["error"]["fix"], env
        return env


def run_cli(*args: str, cwd: Path | None = None, stdin: bytes | None = None, env: dict | None = None) -> CliResult:
    environ = os.environ.copy()
    existing = environ.get("PYTHONPATH")
    environ["PYTHONPATH"] = str(CLI_DIR) + (os.pathsep + existing if existing else "")
    environ.setdefault("PYTHONIOENCODING", "utf-8")
    environ.setdefault("PYTHONUTF8", "1")
    if env:
        environ.update(env)
    proc = subprocess.run(
        [sys.executable, "-m", "nf_app", *args],
        cwd=str(cwd or REPO),
        input=stdin if stdin is not None else b"",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=300,
        env=environ,
        check=False,
    )
    return CliResult(proc)


def run_core_raw(core: Path, op: str, request: dict) -> tuple[int, bytes, bytes]:
    payload = json.dumps(request, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    proc = subprocess.run(
        [str(core), op, "--in", "-"],
        input=payload,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=300,
        check=False,
    )
    return proc.returncode, proc.stdout, proc.stderr


@pytest.fixture(scope="session")
def repo() -> Path:
    return REPO


@pytest.fixture(scope="session")
def schema_dir() -> Path:
    return SCHEMA_DIR


@pytest.fixture(scope="session")
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture(scope="session")
def sample_pack() -> Path:
    return FIXTURES / "sample-pack"


@pytest.fixture(scope="session")
def sample_pack_v2() -> Path:
    return FIXTURES / "sample-pack-v2"


@pytest.fixture(scope="session", autouse=True)
def core_in_tmp(tmp_path_factory):
    """把 nf-app-core 复制到系统临时目录再跑（ENV-01）。

    本机 DSH 沙箱对"工作区内可执行文件"的外写有约束：仓库里的 exe 写
    result.md/zip 会 os error 5，而同一 exe 复制到临时目录后写盘正常；
    这不是核心缺陷（lead 已记入 results/app/BASELINE.md ENV-01）。
    复制后设置 NF_APP_CORE，子进程 CLI 与核心调用都走该副本。
    核心不可用时不设置，相关测试由 core fixture 显式报告阻塞。
    """
    from nf_app.core import AppError, abi_version, available

    source = available()
    if source is None:
        yield None
        return
    try:
        abi_version()
    except AppError:
        yield None
        return
    target_dir = tmp_path_factory.mktemp("nf-core")
    target = target_dir / source.name
    if not target.exists():
        shutil.copy2(source, target)
    previous = os.environ.get("NF_APP_CORE")
    os.environ["NF_APP_CORE"] = str(target)
    try:
        yield target
    finally:
        if previous is None:
            os.environ.pop("NF_APP_CORE", None)
        else:
            os.environ["NF_APP_CORE"] = previous


@pytest.fixture(scope="session")
def core() -> Path:
    """可用核心 = 存在 + --abi-version 返回 {abi: ...} 的 JSON。

    不把"文件存在"当可用：rust-core 的 main 曾经是空实现（exit 0 无输出），
    这里必须真探活，否则 E2E 会假绿。
    """
    from nf_app.core import AppError, abi_version, available

    path = available()
    reason = None
    if path is None:
        reason = "nf-app-core 缺失（可用 NF_APP_CORE 指定）"
    else:
        try:
            info = abi_version()
        except AppError as exc:
            reason = f"nf-app-core 不可用（{exc.message}）"
        else:
            if not isinstance(info, dict) or not info.get("abi"):
                reason = "nf-app-core 的 --abi-version 未返回 {abi,...}（CLI 面未接通）"
    if reason is not None:
        if os.environ.get("NF_REQUIRE_CORE") == "1":
            pytest.fail(reason + "（NF_REQUIRE_CORE=1）")
        pytest.xfail(reason + "：等 rust-core 接通 CLI 后必须去掉 xfail（owner: rust-core）")
    return path


@pytest.fixture(scope="session")
def schemas() -> dict[str, dict]:
    return {
        path.name[: -len(".schema.json")]: json.loads(path.read_text(encoding="utf-8"))
        for path in sorted(SCHEMA_DIR.glob("*.schema.json"))
    }


@pytest.fixture(scope="session")
def error_codes() -> dict[str, dict]:
    data = json.loads((SCHEMA_DIR / "error_codes.json").read_text(encoding="utf-8"))
    return {row["code"]: row for row in data["codes"]}
