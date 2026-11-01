#!/usr/bin/env python3
"""P6-04 / P6-06 / P6-11 整改件：威胁模型、收益度量取数、评估可复算。

计划 §21.5 的验收原文：
  P6-04 「六类威胁各有缓解项与测试」
  P6-06 「可复算的提速曲线（门禁耗时前后）」
  P6-11 「同输入同输出」

三条各有一条「不许含糊」的纪律：

  - **P6-04**：缓解项必须点名一个**在场**的判据件；六类少一类即 FAIL。威胁模型写成散文就无法
    被推翻，也无法被回归——故这里要求每条都能指到一条会变红的判据。
  - **P6-06**：DORA 的四键里，「部署频率」与「变更前置时间」在本仓**有真数据**（25 个 tag +
    提交历史），故按定义算出来、写明口径；「变更失败率」与「恢复时长」需要**事故记录**，
    本仓没有 ⇒ 记 UNKNOWN 并写明缺什么，**不用代理指标冒充**。提供 records 输入面后即可算。
    SPACE 同理：活动度/流动效率/沟通可测，满意与绩效需要问卷与结果指标 ⇒ UNKNOWN。
  - **P6-11**：把 P6-04..P6-10 的报告规范化后取摘要（走 core.attest 的仓库 canonical），
    同输入必得同一 digest；快照只是加速比对的缓存，不是权威。

用法：
    python scripts/risk_baseline.py --json
    python scripts/risk_baseline.py --timings <samples.json> --records <deliveries.json> --json
    python scripts/risk_baseline.py --snapshot .rivet/scratch/p6_snapshot.json --check
    python scripts/risk_baseline.py --self-test
"""
import argparse
import hashlib
import json
import re
import shutil
import subprocess  # nosec B404 - 只读 git 取数
import sys
from collections import Counter
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
#: git 用**绝对路径**：bandit B607 / ruff S607 针对「部分路径起进程」，结构上消掉它，
#: 而不是靠 noqa 免责（免责会让这条规则将来对别处失效）。
GIT = shutil.which("git") or "git"
sys.path.insert(0, str(ROOT / "desktop" / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import data_quality as dq  # noqa: E402
import standards_map as sm  # noqa: E402
from core import (  # noqa: E402 - 必须先插入 desktop/src 才能 import core
    atomic_write,
    attest,
    json_doc,
)

#: P6-04：STRIDE 六类。每类 = 威胁 + 缓解 + 判据件（件必须真实在场）。
STRIDE = (
    {"class": "Spoofing", "cn": "仿冒", "threat": "外部进程冒充工具/插件身份调用内部面",
     "mitigation": "可信边界与参数准入（只认声明面，匿名调用 fail-closed）",
     "evidence": "desktop/tests/test_trust_boundary.py"},
    {"class": "Tampering", "cn": "篡改", "threat": "落盘件在写入过程中被截断或半写",
     "mitigation": "原子写 + 删除留证（半写不产生可核验产出）",
     "evidence": "desktop/tests/test_atomic_write.py"},
    {"class": "Repudiation", "cn": "抵赖", "threat": "对「谁改了什么」无据可查",
     "mitigation": "透明链 + Merkle 回执（叶子/根/包含证明可复核）",
     "evidence": "desktop/tests/test_transparency_log.py"},
    {"class": "InformationDisclosure", "cn": "信息泄露", "threat": "公开面泄漏内部路径/密钥/会话",
     "mitigation": "泄漏面判据 + 敏感文件忽略表 + 密钥扫描",
     "evidence": "desktop/tests/test_leak_surface.py"},
    {"class": "DenialOfService", "cn": "拒绝服务", "threat": "失控插件/超大输入耗尽宿主",
     "mitigation": "燃料计量 + 墙钟超时 + 崩溃回退参考实现",
     "evidence": "desktop/tests/test_plugin_wasm_host.py"},
    {"class": "ElevationOfPrivilege", "cn": "权限提升", "threat": "插件越权拿 fs/net/env",
     "mitigation": "能力 deny by default（装载期硬拒）+ 包含性判据",
     "evidence": "desktop/tests/test_plugin_manifest.py"},
)
STRIDE_CLASSES = ("Spoofing", "Tampering", "Repudiation", "InformationDisclosure",
                  "DenialOfService", "ElevationOfPrivilege")
DORA_KEYS = ("deployment_frequency", "lead_time_for_changes", "change_failure_rate",
             "time_to_restore")
SPACE_KEYS = ("satisfaction", "performance", "activity", "communication", "efficiency_and_flow")
NEEDS_RECORDS = "需要部署/事故记录（--records），本仓无采集面 ⇒ 不造代理指标"
#: 事故记录真源：复盘件（postmortems/PO-*.md）——**不是**代理指标，是本仓对「出了什么事」的
#: 正式登记；关联规则显式写在 _incidents_by_release 里，可逐条复核。
POSTMORTEM_DIR = "postmortems"
NEEDS_SURVEY = "需要团队问卷/结果指标，本仓无采集面 ⇒ 不造代理指标"
#: 提速曲线样本与交付记录的形状（写成常量，供测试与使用者对账）
TIMINGS_SCHEMA = "nf-timings/1"
RECORDS_SCHEMA = "nf-delivery-records/1"
#: 提速曲线的**自带基线**（缺省读它；每条样本都必须带出处）。
DEFAULT_TIMINGS = "protocol/generated/eval_timings.json"


def stride_report(root: Path = ROOT, exists: Callable[[str], bool] | None = None) -> dict[str, Any]:
    """→ 六类威胁的缓解映射 + 判据件在场结论。"""
    has = exists or (lambda rel: (root / rel).is_file())
    issues: list[str] = []
    rows = []
    for row in STRIDE:
        present = has(str(row["evidence"]))
        rows.append(dict(row, evidence_present=present))
        if not str(row.get("mitigation") or "").strip():
            issues.append(f"P6-04 {row['class']} 无缓解项")
        if not present:
            issues.append(f"P6-04 {row['class']} 的缓解判据件不在场：{row['evidence']}")
    got = sorted(r["class"] for r in STRIDE)
    if got != sorted(STRIDE_CLASSES):
        issues.append(f"P6-04 覆盖不等于 STRIDE 六类：{got}")
    return {"schema": "nf-stride/1", "ok": not issues, "issues": issues, "rows": rows}


def _git(root: Path, *args: str) -> str:
    """只读 git 取数；失败返回空串（环境事实，不裸崩）。"""
    try:
        # bandit 只看「调用起点」那一行，ruff 也按起点行认 noqa——故标记全放在这一行。
        # git 用绝对路径（shutil.which）：B607/S607 由结构消掉，而不是靠 noqa 免责。
        proc = subprocess.run([GIT, *args], cwd=str(root),  # nosec B603  # noqa: S603
                              capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return proc.stdout.strip() if proc.returncode == 0 else ""


def _tags_with_time(root: Path) -> list[tuple[str, int]]:
    """打了时间戳的 tag（按创建时间升序）——本仓的**部署记录**真源。"""
    out: list[tuple[str, int]] = []
    for line in _git(root, "for-each-ref", "--sort=creatordate",
                     "--format=%(refname:short)\t%(creatordate:unix)",
                     "refs/tags").splitlines():
        name, _, ts = line.partition("\t")
        if name and ts.strip().isdigit():
            out.append((name.strip(), int(ts)))
    return out


def _commit_times(root: Path, revs: str = "--all") -> dict[str, int]:
    """一次性取「提交 → committer 时间」全表（`git log --format=%H %ct`）。

    为什么要批量（2026-10-15 实测）：门禁 check12 里 `test_p6_evaluations` 一个文件
    实测 **1352 次 git 子进程**（本机每次约 52–143 ms）⇒ 112 s。根因是 `_lead_lags` 与
    调用方**逐 revision** 起 git（N+1）。改成一次全表读入、之后在内存里查表，
    把「每次调用 O(标签数) 个子进程」降为**1 个**。
    """
    out: dict[str, int] = {}
    for line in _git(root, "log", revs, "--format=%H %ct").splitlines():
        sha, _, ts = line.partition(" ")
        if sha and ts.strip().isdigit():
            out[sha.strip()] = int(ts)
    return out


def _lead_lags(root: Path, tags: list[tuple[str, int]]) -> list[int]:
    """逐次发布的「变更进入 → 被部署」滞后秒数（DORA 前置时间的定义口径）。

    口径**逐字未变**：对每对相邻 tag，取 `prev..cur` 区间里**最早**那个提交的 committer 时间，
    与 `cur` 的创建时间相减。变的只是取数方式——原先每个 tag 对起 2 次 git
    （`rev-list` 拿区间 + `log -1` 拿时间），现在区间仍用一次 `rev-list`，
    但「提交→时间」改用一张**批量全表**在内存里查。
    """
    lags: list[int] = []
    times = _commit_times(root)
    for (prev, _), (cur, cur_ts) in zip(tags, tags[1:], strict=False):
        revs = _git(root, "rev-list", "--reverse", f"{prev}..{cur}").split()
        if not revs:
            continue
        first = times.get(revs[0])
        if first is None:                      # 全表未覆盖（浅克隆等）→ 退回单查，不猜
            raw = _git(root, "log", "-1", "--format=%ct", revs[0])
            first = int(raw) if raw.isdigit() else None
        if first is not None:
            lags.append(cur_ts - int(first))
    return lags


def _median(values: list[int]) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) // 2


def _date_to_epoch(text: Any) -> int | None:
    """'YYYY-MM-DD' → 本地时区秒（解析失败 → None，不猜）。"""
    raw = str(text or "").strip()[:10]
    try:
        return int(datetime.strptime(raw, "%Y-%m-%d").timestamp())
    except ValueError:
        return None


def postmortems(root: Path = ROOT) -> list[dict]:
    """读复盘件的 front-matter（id/date/status/trigger + 可选 restored）。

    这是本仓**正式的事故登记面**，不是「用别的东西冒充事故」——故可据此算变更失败率。
    """
    out: list[dict] = []
    base = root / POSTMORTEM_DIR
    if not base.is_dir():
        return out
    for path in sorted(base.glob("*.md")):
        if path.name == "README.md":
            continue
        text = path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            continue
        block = text.split("---", 2)[1]
        meta: dict[str, Any] = {}
        for line in block.splitlines():
            key, _, value = line.partition(":")
            key, value = key.strip(), value.strip()
            if key and value and not value.startswith("-"):
                meta[key] = value
        if meta.get("id"):
            meta["file"] = path.name
            out.append(meta)
    return out


def _incidents_by_release(tags: list[tuple[str, int]], posts: list[dict]) -> dict[str, list[str]]:
    """把事故按**显式规则**关联到发布：事故日期落在 [tag_i, tag_{i+1}) 内即计入第 i 次发布。

    最后一段的右端为「现在」。规则写在这里而不是藏在结论里——换规则必须改这段并重算。
    """
    mapping: dict[str, list[str]] = {name: [] for name, _ in tags}
    for i, (name, ts) in enumerate(tags):
        end = tags[i + 1][1] if i + 1 < len(tags) else int(datetime.now().timestamp())
        for pm in posts:
            when = _date_to_epoch(pm.get("date"))
            if when is not None and ts <= when < end:
                mapping[name].append(str(pm.get("id")))
    return mapping


def _read_records(records_path: str) -> tuple[list[dict], str]:
    """读交付记录；缺文件/坏件 → 空表 + 原因（不静默当成功）。"""
    if not records_path:
        return [], "未提供 --records"
    path = Path(records_path)
    if not path.is_file():
        return [], f"记录文件不在场：{records_path}"
    try:
        doc = json_doc.load(path, dict, what=path.name)
    except (OSError, ValueError) as exc:
        return [], f"记录不可解析：{exc}"
    if doc.get("schema") != RECORDS_SCHEMA:
        return [], f"记录 schema 不是 {RECORDS_SCHEMA}"
    return list(doc.get("deployments") or []), ""


def delivery_counts(root: Path = ROOT) -> dict[str, Any]:
    """能**确定性**取到的交付计数（不含任何估计）。"""
    tests = sorted((root / "desktop" / "tests").glob("test_*.py"))
    verify = root / "verify.sh"
    checks = (re.findall(r"^check\d+\(\)", verify.read_text(encoding="utf-8"), re.M)
              if verify.is_file() else [])
    core_modules = [p for p in (root / "desktop" / "src" / "core").glob("*.py")
                    if p.stem != "__init__"]
    integrations = list((root / "integrations").glob("*/integration.json"))
    commits = _git(root, "rev-list", "--count", "HEAD")
    stamps = [int(x) for x in _git(root, "log", "--format=%ct").split() if x.isdigit()]
    authors = Counter(x for x in _git(root, "log", "--format=%an").splitlines() if x.strip())
    days = None
    per_day = None
    if commits.isdigit() and len(stamps) >= 2:
        oldest, newest = min(stamps), max(stamps)
        if newest > oldest:
            days = max(1, round((newest - oldest) / 86400))
            per_day = round(int(commits) / days, 3)
    return {"test_files": len(tests), "verify_checks": len(checks),
            "core_modules": len(core_modules), "integrations": len(integrations),
            "commits": int(commits) if commits.isdigit() else None,
            "active_days": days, "commits_per_day": per_day,
            "authors": len(authors)}


def _incident_from_records(records: list[dict]) -> tuple[dict, dict]:
    """显式交付记录（--records）→ (变更失败率, 恢复时长)。"""
    failed = [d for d in records if d.get("failed")]
    cfr = {"value": round(len(failed) / len(records), 4), "unit": "比例",
           "basis": f"{RECORDS_SCHEMA} 的 deployments[].failed", "why": ""}
    restored = [int(d["restored_s"]) for d in failed
                if str(d.get("restored_s") or "").isdigit()]
    mttr = {"value": None if not restored else round(_median(restored) / 60.0, 3),
            "unit": "分钟（中位）",
            "basis": f"{RECORDS_SCHEMA} 的 deployments[].restored_s",
            "why": "" if restored else "记录里没有恢复时长字段"}
    return cfr, mttr


def _incident_from_postmortems(root: Path, tags: list[tuple[str, int]]) -> tuple[dict, dict]:
    """本仓**正式的事故登记面**（复盘件）→ (变更失败率, 恢复时长)；规则显式、可逐条复核。"""
    missing = {"value": None, "unit": "", "basis": "",
               "why": f"{POSTMORTEM_DIR}/ 无复盘件或 tag 不足 ⇒ 无事故记录可算"}
    posts = postmortems(root)
    if not (tags and posts):
        return dict(missing), dict(missing)
    mapping = _incidents_by_release(tags, posts)
    hit = [name for name, ids in mapping.items() if ids]
    cfr = {
        "value": round(len(hit) / len(tags), 4), "unit": "比例",
        "basis": (f"{POSTMORTEM_DIR}/ 复盘件按日期落入发布区间"
                  f"（规则见 _incidents_by_release）：{len(hit)}/{len(tags)} 次发布有登记事故"),
        "why": ""}
    days = []
    for pm in posts:
        start, end = _date_to_epoch(pm.get("date")), _date_to_epoch(pm.get("restored"))
        if start is not None and end is not None and end >= start:
            days.append((end - start) / 86400.0)
    mttr = {
        "value": None if not days else round(_median([int(d * 86400) for d in days]) / 60.0, 3),
        "unit": "分钟（中位）",
        "basis": f"{POSTMORTEM_DIR}/ 复盘件的 date → restored 字段",
        "why": "" if days else
               "复盘件没有 restored（恢复时刻）字段 ⇒ 无法算恢复时长；补该字段即可算"
               "（也支持 --records 走另一条路）"}
    return cfr, mttr


def dora_values(root: Path = ROOT, records_path: str = "") -> tuple[dict, dict, str]:
    """→ (DORA 四键, 派生口径明细, records 原因)。两键真取数，两键要事故记录。"""
    tags = _tags_with_time(root)
    lags = _lead_lags(root, tags)
    span_days = None
    if len(tags) >= 2:
        span_days = max(1, round((tags[-1][1] - tags[0][1]) / 86400))
    deploys_per_week = (round(len(tags) / (span_days / 7.0), 3)
                        if span_days and span_days > 0 else None)
    median_lag = _median(lags)
    derived = {"tag_count": len(tags), "tag_span_days": span_days,
               "first_tag": tags[0][0] if tags else None,
               "last_tag": tags[-1][0] if tags else None,
               "lead_samples": len(lags),
               "median_lead_s": median_lag}
    values = {
        "deployment_frequency": {
            "value": deploys_per_week, "unit": "次/周",
            "basis": "git tag 时间戳（本仓的部署记录真源）",
            "why": "" if deploys_per_week is not None else "tag 少于 2 个，跨度不可算"},
        "lead_time_for_changes": {
            "value": None if median_lag is None else round(median_lag / 86400.0, 3),
            "unit": "天（中位）",
            "basis": "每个 tag 区间内**最早提交**到该 tag 的滞后中位数",
            "why": "" if median_lag is not None else "无可用 tag 区间"},
        "change_failure_rate": {"value": None, "unit": "", "basis": "", "why": NEEDS_RECORDS},
        "time_to_restore": {"value": None, "unit": "", "basis": "", "why": NEEDS_RECORDS},
    }
    records, why = _read_records(records_path)
    if records:
        values["change_failure_rate"], values["time_to_restore"] = _incident_from_records(records)
        return values, derived, why

    values["change_failure_rate"], values["time_to_restore"] = _incident_from_postmortems(
        root, tags)
    return values, derived, why


def space_values(root: Path = ROOT, records_path: str = "") -> dict[str, Any]:
    """→ SPACE 五键：能测的测（活动/流动/沟通），要问卷与结果指标的如实记 UNKNOWN。"""
    counts = delivery_counts(root)
    _, derived, _ = dora_values(root, records_path)
    days = counts.get("active_days")
    commits = counts.get("commits")
    per_week = (round(commits / (days / 7.0), 2) if days and commits else None)
    lead_days = (None if derived["median_lead_s"] is None
                 else round(derived["median_lead_s"] / 86400.0, 3))
    return {
        "satisfaction": {"value": None, "unit": "", "basis": "", "why": NEEDS_SURVEY},
        "performance": {"value": None, "unit": "", "basis": "", "why": NEEDS_SURVEY},
        "activity": {"value": per_week, "unit": "提交/周", "basis": "git 提交时间戳",
                     "why": "" if per_week is not None else "提交历史不可用"},
        "communication": {"value": counts.get("authors"), "unit": "提交作者数",
                          "basis": "git 提交作者",
                          "why": "" if counts.get("authors") else "作者面不可用"},
        "efficiency_and_flow": {"value": lead_days, "unit": "天（中位前置时间）",
                                "basis": "与 DORA 前置时间同源", "why": ""},
    }


def dora_metrics(root: Path = ROOT, timings_path: str = "",
                 records_path: str = "") -> dict[str, Any]:
    """→ 交付计数 + DORA/SPACE 结论 + 可选提速曲线 + 可选采样/基准器在场情况。"""
    dora, derived, records_why = dora_values(root, records_path)
    timings_path = timings_path or str(root / DEFAULT_TIMINGS)
    curve, curve_why = None, f"未提供实测样本（--timings，缺省 {DEFAULT_TIMINGS}）⇒ 记 UNKNOWN"
    if timings_path:
        path = Path(timings_path)
        if not path.is_file():
            curve_why = f"样本文件不在场：{timings_path}"
        else:
            samples = json_doc.load(path, dict, what=path.name).get("samples") or []
            if samples and all(s.get("source") for s in samples):
                curve = [{"face": s.get("face"), "before_s": s.get("before_s"),
                          "after_s": s.get("after_s"),
                          "speedup": round(float(s["before_s"]) / float(s["after_s"]), 3)
                          if float(s.get("after_s") or 0) > 0 else None,
                          "source": s["source"]} for s in samples]
                curve_why = ""
            else:
                curve_why = "样本缺 source（无出处的数字不入报告）"
    return {
        "schema": "nf-dora-space/1",
        "counts": delivery_counts(root),
        "dora": dora,
        "dora_derived": derived,
        "dora_records_why": records_why,
        "space": space_values(root, records_path),
        "speedup_curve": curve,
        "speedup_curve_why": curve_why,
        "schemas": {"timings": TIMINGS_SCHEMA, "records": RECORDS_SCHEMA},
    }


def collect_reports(root: Path = ROOT, timings_path: str = "",
                    records_path: str = "") -> dict[str, Any]:
    """→ P6-04..P6-10 的合并报告（P6-11 的输入）。"""
    return {
        "P6-04": stride_report(root),
        "P6-05/09/10": sm.report(root),
        "P6-06": dora_metrics(root, timings_path, records_path),
        "P6-07/08": dq.report(root),
    }


def evaluation_digest(root: Path = ROOT, timings_path: str = "",
                      records_path: str = "") -> dict[str, Any]:
    """→ 逐面摘要 + 总摘要（同输入同输出，走仓库 canonical）。"""
    reports = collect_reports(root, timings_path, records_path)
    parts = {face: "sha256:" + hashlib.sha256(attest.canonical(rep)).hexdigest()
             for face, rep in sorted(reports.items())}
    overall = "sha256:" + hashlib.sha256(attest.canonical(parts)).hexdigest()
    return {"schema": "nf-eval-digest/1", "digest": overall, "parts": parts,
            "versions": {"attest_canonical": "nf-canonical/1",
                         "reports": sorted(reports)},
            "ok": all(bool(rep.get("ok", True)) for rep in reports.values())}


def _st_stride() -> int:
    """P6-04：真仓全绿 + 抽掉判据件必须全红（缺一不可）。"""
    rep = stride_report(ROOT)
    assert rep["ok"], rep["issues"]  # nosec B101  # noqa: S101
    bad = stride_report(ROOT, exists=lambda _rel: False)
    assert not bad["ok"] and len(bad["issues"]) == len(STRIDE_CLASSES), bad["issues"]  # nosec B101  # noqa: S101
    return 1


def _st_digest() -> int:
    """P6-11：摘要形状 + 同输入同输出。"""
    d = evaluation_digest(ROOT)
    assert d["digest"].startswith("sha256:") and len(d["parts"]) == 4, d  # nosec B101  # noqa: S101
    assert evaluation_digest(ROOT)["digest"] == d["digest"], "同输入必须同输出"  # nosec B101  # noqa: S101
    return 1


def _st_delivery() -> int:
    """P6-06：计数为真 + 提速曲线带出处 + **每个数字都有 basis、每个空值都有 why**。"""
    m = dora_metrics(ROOT)
    assert m["counts"]["test_files"] > 0 and m["counts"]["verify_checks"] > 0, m["counts"]  # nosec B101  # noqa: S101
    assert m["speedup_curve"] and len(m["speedup_curve"]) >= 2, m["speedup_curve_why"]  # nosec B101  # noqa: S101
    assert all(s["source"] for s in m["speedup_curve"]), m["speedup_curve"]  # nosec B101  # noqa: S101
    for key, val in m["dora"].items():
        if val["value"] is not None:
            assert str(val.get("basis") or "").strip(), f"{key} 有数字却没出处"  # nosec B101  # noqa: S101
        else:
            assert str(val.get("why") or "").strip(), f"{key} 为空却没写原因"  # nosec B101  # noqa: S101
    # 本仓有 25 个 tag + 1 件复盘 ⇒ 三键应真取到数；只有恢复时长因缺字段为空。
    for key in ("deployment_frequency", "lead_time_for_changes", "change_failure_rate"):
        assert m["dora"][key]["value"] is not None, m["dora"]  # nosec B101  # noqa: S101
    assert m["dora"]["time_to_restore"]["value"] is None, m["dora"]  # nosec B101  # noqa: S101
    assert m["dora"]["change_failure_rate"]["value"] == round(1 / 25, 4), m["dora"]  # nosec B101  # noqa: S101
    return 1


def _st_records() -> int:
    """--records 面：给了记录，另两键必须真算得出来（否则「可算」只是说法）。"""
    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        rec = Path(tmp) / "rec.json"
        rec_doc = {"schema": RECORDS_SCHEMA, "deployments": [
            {"id": "a", "failed": False}, {"id": "b", "failed": True, "restored_s": 600},
            {"id": "c", "failed": True, "restored_s": 1800}]}
        atomic_write.write_text(rec, json.dumps(rec_doc))
        got = dora_metrics(ROOT, "", str(rec))["dora"]
        assert got["change_failure_rate"]["value"] == round(2 / 3, 4), got  # nosec B101  # noqa: S101
        assert got["time_to_restore"]["value"] == round(1200 / 60.0, 3), got  # nosec B101  # noqa: S101
    return 1


def _self_test() -> int:
    checks = _st_stride() + _st_digest() + _st_delivery() + _st_records()
    print(f"self-test OK（{checks} 例）")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="P6-04/06/11 风险与度量取数（只读）")
    ap.add_argument("--timings", default="", help=f"带出处的实测样本 JSON（{TIMINGS_SCHEMA}）")
    ap.add_argument("--records", default="", help=f"交付/事故记录 JSON（{RECORDS_SCHEMA}）")
    ap.add_argument("--snapshot", default="", help="快照路径（配合 --check / --write）")
    ap.add_argument("--check", action="store_true", help="与快照比较，漂移即 exit 1")
    ap.add_argument("--write", action="store_true", help="写快照")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return _self_test()
    if args.check or args.write:
        if not args.snapshot:
            print("缺 --snapshot 路径（修复指引：给一个可写路径）", file=sys.stderr)
            return 2
        path = Path(args.snapshot)
        cur = evaluation_digest(ROOT, args.timings, args.records)
        if args.write or not path.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            atomic_write.write_text(path, json.dumps(cur, ensure_ascii=False, indent=2,
                                                     sort_keys=True) + "\n")
            print(f"快照已写：{path} · {cur['digest']}")
            return 0
        old = json_doc.load(path, dict, what=path.name)
        drift = [f for f in cur["parts"] if old.get("parts", {}).get(f) != cur["parts"][f]]
        if drift or old.get("digest") != cur["digest"]:
            print(f"评估漂移（{drift or ['总摘要']}）（修复指引：复核后 --write 重签）",
                  file=sys.stderr)
            return 1
        print(f"评估一致：{cur['digest']}")
        return 0
    rep = collect_reports(ROOT, args.timings, args.records)
    dig = evaluation_digest(ROOT, args.timings, args.records)
    rep["digest"] = dig
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        ok_faces = sum(1 for v in rep.values() if isinstance(v, dict) and v.get("ok"))
        print(f"== P6-04/06/11（{ok_faces}/4 面 OK）· digest {dig['digest'][:19]}… ==")
        st = rep["P6-06"]["counts"]
        print(f"  P6-04 STRIDE：{len(rep['P6-04']['rows'])} 类"
              f"（{'OK' if rep['P6-04']['ok'] else 'NG'}）")
        print(f"  P6-06 计数：{st}")
        for key, val in rep["P6-06"]["dora"].items():
            print(f"    DORA {key:<24} {val['value']} {val.get('unit', '')}"
                  f"{'' if val['value'] is not None else '（' + val['why'] + '）'}")
        print(f"  P6-06 提速曲线：{rep['P6-06']['speedup_curve_why'] or '在场'}")
        for face, val in sorted(rep.items()):
            if isinstance(val, dict) and val.get("ok") is False:
                for issue in val.get("issues", []):
                    print(f"  ✗ {face}: {issue}")
    return 0 if dig["ok"] else 1


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")
    raise SystemExit(main())
