"""conformance_scan 私有子模块 _scan：一致性分级扫描真算（模块 mc / 协议包 / 导出 manifest 三面）。

门面 core.conformance_scan 按原 API 重新导出；本文件只承载实现，不改变对外面。
"""
from __future__ import annotations

import copy
import os

from core import import_graph as _ig

from core import conformance_scan as _dm



def _mc_id_issues(rel: str, mid: str, seen_mc_id: dict) -> List[str]:
    """模块 id 文件级唯一判据（重复即问题；首次出现记入 seen）。"""
    if not mid:
        return []
    if mid in seen_mc_id:
        return ["%s: 模块 id 与 %s 重复（mc.id=%s）——编号是全局寻址面，"
                "运行时索引会静默择一，须改号"
                "（修复指引：按 01 §1.6.11 换类内段号或 M91-M99 段号）"
                % (rel, seen_mc_id[mid], mid)]
    seen_mc_id[mid] = rel
    return []


def _module_contract_issues(root: str, evidence: set,
                            seen_mc_id: dict) -> Tuple[int, List[str]]:
    """模块文档 machine_contract 面（id 全局唯一 / conformance 不虚标）→ (条数, issues)。"""
    issues: List[str] = []
    modules_mc = 0
    #: 模块 id 全局唯一（01 §1.6.11）——登记面由 check14 ⑤b 管；但**两个模块文件声明同一 mc.id**
    #: 此前无判据，运行时索引 first-wins 静默择一（`mcp_runtime` / `pipelinerun`）会让编号指向不确定
    #: 的模块。此处补文件级唯一判据（极端渗透 D3）。
    for doc in _dm._module_docs(root):
        rel = os.path.relpath(doc, root).replace(os.sep, "/")
        try:
            text = _dm.read_text_cached(doc)      # 共享语料：同一份模块文档一次只读一遍
        except Exception as exc:
            issues.append(f"{rel}: 读取失败 {exc}")
            continue
        parsed = _dm._fence_yaml(text, "machine_contract")
        if "machine_contract" not in parsed:
            continue
        mc = parsed["machine_contract"]
        mid = str((mc or {}).get("id") or "")
        issues.extend(_mc_id_issues(rel, mid, seen_mc_id))
        modules_mc += 1
        declared = mc.get("conformance")
        if declared not in ("L1", "L2", "L3"):
            issues.append(f"{rel}: machine_contract 缺/非法 conformance 声明 {declared!r}")
            continue
        mid = mc.get("id")
        provable = 2 if isinstance(mid, str) and mid in evidence else 1
        order = {"L1": 1, "L2": 2, "L3": 3}
        if order[declared] > provable:
            issues.append(
                f"{rel}: conformance 虚标 {declared} > 可证 L{provable}"
                f"（{mid!r} 不在装配在册证据）"
            )
    return modules_mc, issues


def _package_issues(root: str, reg_ids: set) -> Tuple[int, List[str]]:
    """community 协议包 conformance 面 → (包数, issues)。"""
    issues: List[str] = []
    packages = 0
    for rel in _dm.iter_files(root, "community/*/protocol.yaml"):
        proto = os.path.join(root, *rel.split("/"))
        try:
            # 共享语料 + 内容键解析（同一份 protocol.yaml 一轮只读一次、只解析一次）
            data = _dm.load_yaml_cached(_dm.read_text_cached(proto))
        except Exception as exc:
            issues.append(f"{rel}: protocol.yaml 解析失败 {exc}")
            continue
        packages += 1
        pkg = (data or {}).get("package") or {}
        declared = pkg.get("conformance")
        pid = pkg.get("id")
        if declared not in ("L1", "L2", "L3"):
            issues.append(f"{rel}: package 缺/非法 conformance 声明 {declared!r}")
            continue
        provable = 2 if isinstance(pid, str) and pid in reg_ids else 1
        order = {"L1": 1, "L2": 2, "L3": 3}
        if order[declared] > provable:
            issues.append(f"{rel}: conformance 虚标 {declared} > 可证 L{provable}（包不在 registry p"
                f"rotocols[]）")
    return packages, issues


def _export_issues(root: str) -> Tuple[int, List[str]]:
    """导出契约面 manifest（L3 = 导出契约门禁锁定面）→ (export_items, issues)。"""
    issues: List[str] = []
    manifest_path = os.path.join(root, "protocol", "export_conformance.json")
    manifest, err = _dm._read_json(manifest_path)
    if not isinstance(manifest, dict):
        issues.append(f"protocol/export_conformance.json 缺失/解析失败：{err}")
        return 0, issues
    verify_txt = ""
    verify_path = os.path.join(root, "verify.sh")
    if os.path.isfile(verify_path):
        with open(verify_path, encoding="utf-8") as fh:
            verify_txt = fh.read()
    man_issues, export_items = _dm.export_manifest_issues(root, verify_txt, manifest)
    issues.extend(man_issues)
    return export_items, issues


def scan(root: str = ".") -> Tuple[List[str], Dict[str, int]]:
    """检查（外层）：派生结果按**输入内容指纹**跨调用缓存（输入面见 `SCAN_INPUTS`，已穷举）。

    依据（实测）：本函数一次调用约 0.4 s，而它只依赖那 6 类输入——守护逐请求清空按 root 的
    缓存时，这些派生账会被白交一遍。键即内容 ⇒ 输入一变指纹就变，故不需要随请求清空。

    再叠一层**持久**缓存（`core.disk_cache`：键里还含**代码面 + 运行时**）：新进程也能免付
    这笔派生账。读回时按 `result_pair_ok` 校验形状，不可信即重算。

    「读到的文件必须全部落在输入面内」有判据守着（test_conformance_scan.DerivedResultCacheTest）：
    将来给本函数加新读取，判据会先红、逼着把新输入补进来——不会悄悄读到陈旧结果。
    """
    fp = _dm.face_fingerprint(root, _dm.SCAN_INPUTS)
    hit = _dm._SCAN_CACHE.get(fp)
    if hit is None:
        from core import disk_cache
        dkey = disk_cache.key("scan", fp, root=root,
                              code_scope=_ig.code_scope_fingerprint(root,
 ("core.conformance_scan",
)))
        cached = disk_cache.load("scan", dkey, validate=_dm.result_pair_ok)
        if cached is None:
            got = _dm._scan_impl(root)
            cached = disk_cache.canonical({"issues": list(got[0]), "stats": got[1]})
            disk_cache.store("scan", dkey, cached)
        # 命中与未命中必须**逐字节一致**：落盘是 `sort_keys` 规范化过的，新算的那份也要过同一道
        # 规范化（否则首跑/次跑换序——见 `disk_cache.canonical` 的取证）。
        hit = _dm._SCAN_CACHE[fp] = (list(cached["issues"]), dict(cached["stats"]))
    return copy.deepcopy(hit[0]), copy.deepcopy(hit[1])
