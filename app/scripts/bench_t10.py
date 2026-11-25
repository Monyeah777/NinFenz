#!/usr/bin/env python3
"""T10：500 页 PDF 导入在 25/50/75% 断点续传；最终 SDIR/构建可复现。"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SOURCE_CORE = Path(os.environ.get("NF_APP_CORE", REPO / "app" / "core" / "target" / "release" / "nf-app-core.exe"))
CORE_DIR = Path(tempfile.mkdtemp(prefix="nf-t10-core-"))
CORE = CORE_DIR / SOURCE_CORE.name
if SOURCE_CORE.exists():
    shutil.copy2(SOURCE_CORE, CORE)
OUT = REPO / "results" / "app" / "governance" / "trials"
PDF_TOOL = Path(os.environ.get("PDFTOHTML", "C:/Program Files/Calibre2/app/bin/pdftohtml.exe"))


def core(op: str, req: dict) -> tuple[int, dict]:
    p = subprocess.run(
        [str(CORE), op, "--in", "-"],
        input=json.dumps(req, ensure_ascii=False).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=300,
    )
    return p.returncode, json.loads(p.stdout.decode("utf-8"))


def digest(obj: object) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def pages_in(sdir: dict) -> set[int]:
    return {b["page"] for b in sdir["provenance"] if isinstance(b.get("page"), int)}


def run_layout(pdf: Path, out_json: Path, checkpoint: Path | None = None, stop_after: int = 0, chunk: int = 125) -> dict:
    cmd = [
        sys.executable,
        str(REPO / "app" / "scripts" / "pdf_layout.py"),
        "--pdf",
        str(pdf),
        "--out",
        str(out_json),
        "--chunk",
        str(chunk),
        "--meta-out",
        str(out_json) + ".meta.json",
    ]
    if checkpoint is not None:
        cmd += ["--checkpoint", str(checkpoint)]
    if stop_after:
        cmd += ["--stop-after", str(stop_after)]
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=600, env={**os.environ, "PDFTOHTML": str(PDF_TOOL)})
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode("utf-8", errors="replace")[:500])
    if stop_after:
        return {}
    return json.loads(Path(str(out_json) + ".meta.json").read_text(encoding="utf-8"))


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="nf-t10-"))
    pdf = tmp / "corpus.pdf"
    subprocess.run([sys.executable, str(REPO / "app" / "scripts" / "make_pdf.py"), "--pages", "500", "--out", str(pdf)], check=True, stdout=subprocess.DEVNULL)
    full_req = tmp / "full.json"
    t0 = time.perf_counter()
    full_meta = run_layout(pdf, full_req)
    full_time = time.perf_counter() - t0
    full_pages = json.loads(full_req.read_text(encoding="utf-8"))["pages"]
    code, full_env = core("layout-import", json.loads(full_req.read_text(encoding="utf-8")))
    assert code == 0, full_env
    full_sdir = full_env["result"]

    # 25/50/75% 断点：每次只处理 125 页；最后一次跑到 500。
    cp = tmp / "checkpoint.json"
    resume_points = [125, 250, 375, 500]
    peak = 0.0
    for point in resume_points:
        req = tmp / f"resume-{point}.json"
        meta = run_layout(pdf, req, checkpoint=cp, stop_after=125 if point < 500 else 0)
        peak = max(peak, float(meta.get("peak_mb", 0)))
        if point < 500:
            state = json.loads(cp.read_text(encoding="utf-8"))
            assert len(state["pages"]) >= point, (point, len(state["pages"]))
    resumed_pages = json.loads((tmp / "resume-500.json").read_text(encoding="utf-8"))["pages"]
    code, resumed_env = core("layout-import", json.loads((tmp / "resume-500.json").read_text(encoding="utf-8")))
    assert code == 0, resumed_env
    resumed_sdir = resumed_env["result"]

    out = tmp / "out"
    out.mkdir()
    code, b1 = core("build-run", {"sdir": resumed_sdir, "outputs": [{"path": "out.md", "format": "md"}], "out_dir": str(out)})
    assert code == 0, b1
    sha1 = b1["result"]["artifacts"][0]["sha256"]
    code, b2 = core("build-run", {"sdir": resumed_sdir, "outputs": [{"path": "out.md", "format": "md"}], "out_dir": str(out)})
    assert code == 0, b2
    sha2 = b2["result"]["artifacts"][0]["sha256"]

    full_digest = digest(full_sdir)
    resumed_digest = digest(resumed_sdir)
    same = full_digest == resumed_digest
    page_cover = pages_in(resumed_sdir) >= set(range(1, 501))
    no_loss = len(full_pages) == len(resumed_pages) == 500 and page_cover
    ok = same and no_loss and sha1 == sha2 and peak <= 300
    result = {
        "trial": "T10",
        "ok": ok,
        "pages": 500,
        "resume_points": resume_points,
        "full_pages": len(full_pages),
        "resumed_pages": len(resumed_pages),
        "sdir_same": same,
        "full_sha": full_digest,
        "resumed_sha": resumed_digest,
        "page_cover": page_cover,
        "build_reproducible": sha1 == sha2,
        "peak_mb": round(peak, 1),
        "full_parse_seconds": round(full_time, 2),
        "criteria": {"recovery": "100%", "loss": 0, "peak_mb": "<=300", "build": "same sha"},
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "T10.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    shutil.rmtree(tmp, ignore_errors=True)
    print(json.dumps(result, ensure_ascii=False))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
