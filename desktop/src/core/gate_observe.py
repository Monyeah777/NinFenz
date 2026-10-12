"""门禁读面观测：跑测试模块并记录它们读过哪些仓库件（数据落缓存区，不入库）。

为什么数据不入库：读面含本机路径与耗时，是**环境相关的可再生数据**；
入库等于把机器状态混进源码。

观测方式：每个模块起一个子进程，子进程装 audit hook 记录 open 事件；再经 PYTHONPATH
注入 sitecustomize，让**子进程的子进程**（python nf.py …）的读面也进日志。
观测不到的部分（原生工具 ruff/node 等）由 gate_select 按 fail-closed 常跑，不在这里猜。

判据：tests/test_gate_observe.py
"""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import subprocess  # nosec B404 - 只跑仓库内测试（argv 列表、无 shell、路径自仓库）
import sys
import tempfile
import time
from pathlib import Path

from core import atomic_write, disk_cache, json_doc
from core.gate_select import FACES_NAME, FACES_TAG, SCHEMA

#: 子进程观测器（-c 传入，不落仓库文件）：装 audit hook → 跑一个测试模块 → 写 JSON。
RUNNER = r"""
import io, json, os, sys, unittest
out_path, mod = sys.argv[1], sys.argv[2]
seen = set()
def _hook(event, args):
    if event != "open":
        return
    try:
        p = args[0]
    except (IndexError, TypeError):
        return
    if isinstance(p, int):
        return
    try:
        seen.add(os.fsdecode(p))
    except (TypeError, ValueError):
        return
sys.addaudithook(_hook)
sys.path.insert(0, os.getcwd())
status = "ok"
try:
    suite = unittest.TestLoader().loadTestsFromName("tests." + mod)
    res = unittest.TextTestRunner(verbosity=0, stream=io.StringIO()).run(suite)
    if res.failures or res.errors:
        status = "tests_failed"
except Exception:
    status = "import_error"
with open(out_path, "w", encoding="utf-8") as fh:
    json.dump({"status": status, "reads": sorted(seen)}, fh, ensure_ascii=False)
sys.stdout.flush()
os._exit(0)
"""

#: 注入子进程的 sitecustomize：把它们的 open 也写进同一个日志（写日志本身会触发 open，
#: 故用重入闸门短路，避免自递归）。
SITE = r"""
import os, sys
_LOG = os.environ.get("NF_FACE_LOG")
if _LOG:
    _busy = [False]
    _fh = open(_LOG, "a", buffering=1, encoding="utf-8", errors="replace")
    def _hook(event, args):
        if event != "open" or _busy[0]:
            return
        try:
            p = args[0]
        except (IndexError, TypeError):
            return
        if isinstance(p, int):
            return
        _busy[0] = True
        try:
            _fh.write(os.fsdecode(p) + "\n")
        except (OSError, TypeError, ValueError):
            pass
        finally:
            _busy[0] = False
    sys.addaudithook(_hook)
"""

_SKIP_PREFIX = (".rivet/", ".git/", "__pycache__/")
_SKIP_SUFFIX = (".pyc", ".pyo")


def faces_path() -> Path:
    """与 gate_select 同一落点（缓存区）。"""
    return disk_cache.dir_for(FACES_TAG) / FACES_NAME


def normalize_reads(root: str, paths, workdir: str | None = None) -> list:
    """路径 → 仓库相对 posix；仓外、私有面、字节码一律丢弃（去重排序）。"""
    base = os.path.abspath(workdir or root)
    rp = os.path.normcase(os.path.abspath(root))
    out = set()
    for p in paths:
        raw = str(p)
        cand = raw if os.path.isabs(raw) else os.path.join(base, raw)
        n = os.path.normcase(os.path.abspath(cand))
        if not (n == rp or n.startswith(rp + os.sep)):
            continue
        rel = n[len(rp):].lstrip("\\/").replace("\\", "/")
        if rel.startswith(_SKIP_PREFIX) or rel.endswith(_SKIP_SUFFIX):
            continue
        out.add(rel)
    return sorted(out)


def _run_child(mod: str, cwd: str, out_path: str, capture_children: bool,
               site_dir: str | None, timeout: int = 600) -> None:
    env = dict(os.environ)
    if capture_children and site_dir:
        env["PYTHONPATH"] = site_dir + os.pathsep + env.get("PYTHONPATH", "")
        env["NF_FACE_LOG"] = out_path + ".child"
    subprocess.run([sys.executable, "-c", RUNNER, out_path, mod], cwd=cwd,  # noqa: S603
                   env=env, capture_output=True, check=False, timeout=timeout)  # nosec B603


def observe_one(mod: str, root: str, cwd: str | None = None, timeout: int = 600,
                capture_children: bool = True) -> dict:
    """跑一个模块 → 读面记录（含子进程读面与观测状态）。"""
    workdir = cwd or os.path.join(root, "desktop")
    started = time.perf_counter()
    status, parent_reads, child_lines = "timeout", [], []
    with tempfile.TemporaryDirectory(prefix="nf-face-") as tmp:
        out_path = os.path.join(tmp, "faces.json")
        site_dir = None
        if capture_children:
            site_dir = os.path.join(tmp, "site")
            os.makedirs(site_dir, exist_ok=True)
            with open(os.path.join(site_dir, "sitecustomize.py"), "w",
                      encoding="utf-8", newline="\n") as fh:
                fh.write(SITE)
        try:
            _run_child(mod, workdir, out_path, capture_children, site_dir, timeout)
        except subprocess.TimeoutExpired:
            status = "timeout"               # 超时也是「说不清」：常跑兜底，不当成功
        except OSError:
            status = "import_error"          # 起不来进程：同样如实记
        else:
            try:
                got = json_doc.loads(Path(out_path).read_text(encoding="utf-8"), dict,
                                     what="观测结果")
                status = str(got.get("status") or "unknown")
                parent_reads = list(got.get("reads") or [])
            except (OSError, ValueError):
                status = "unknown"           # 观测件缺失/半截：一律「说不清」
        child_log = Path(out_path + ".child")
        if child_log.is_file():
            child_lines = child_log.read_text(encoding="utf-8", errors="replace").splitlines()
    reads = normalize_reads(root, list(parent_reads) + child_lines, workdir)
    return {"status": status, "reads": reads, "seconds": round(time.perf_counter() - started, 2),
            "child_reads_captured": len(child_lines)}


def load_doc(path: Path | None = None) -> dict:
    """读回已观测数据（坏件 / schema 不符 → 空表，等价于「未观测」）。"""
    try:
        got = json_doc.loads((path or faces_path()).read_text(encoding="utf-8"), dict,
                             what="门禁读面数据")
    except (OSError, ValueError):
        return {"schema": SCHEMA, "modules": {}}
    if not isinstance(got, dict) or got.get("schema") != SCHEMA:
        return {"schema": SCHEMA, "modules": {}}
    if not isinstance(got.get("modules"), dict):
        got["modules"] = {}
    return got


def save_doc(doc: dict, path: Path | None = None) -> Path:
    """原子落盘（缓存区；目录不存在则建）。"""
    p = path or faces_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    atomic_write.write_text(p, json.dumps(doc, ensure_ascii=False, indent=1, sort_keys=True))
    return p


def run_all(root: str, mods=None, workers: int = 5, timeout: int = 600,
            force: bool = False, cwd: str | None = None, path: Path | None = None,
            on_progress=None) -> dict:
    """并行观测（可续跑）：已观测且未 force 的模块直接跳过。"""
    tdir = Path(cwd or os.path.join(root, "desktop")) / "tests"
    todo = sorted(mods) if mods else sorted(p.stem for p in tdir.glob("test_*.py"))
    doc = {"schema": SCHEMA, "modules": {}} if force else load_doc(path)
    doc["schema"] = SCHEMA
    todo = [m for m in todo if force or m not in doc["modules"]]
    if not todo:
        return doc

    def one(mod):
        try:
            return mod, observe_one(mod, root, cwd=cwd, timeout=timeout)
        except Exception as exc:              # 单模块异常 ⇒ 如实记「说不清」，不崩整轮
            return mod, {"status": "observe_error", "reads": [], "seconds": 0,
                         "child_reads_captured": 0, "error": type(exc).__name__}

    done = 0
    with cf.ThreadPoolExecutor(max_workers=max(1, int(workers))) as pool:
        for mod, rec in pool.map(one, todo):
            done += 1
            doc["modules"][mod] = rec
            save_doc(doc, path)
            if on_progress is not None:
                on_progress(done, len(todo), mod, rec)
    return doc

