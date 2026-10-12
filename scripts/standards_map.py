#!/usr/bin/env python3
"""P6-05 / P6-09 / P6-10 整改件：标准面映射与场景集（**可机检**）。

计划 §21.5 对这三条的验收原文：
  P6-05 ISO 29119 四层映射 —— 「过程/文档/技术/覆盖各一例」
  P6-09 NIST AI RMF 映射   —— 「治理/映射/度量/管理四段各一条」
  P6-10 ATAM 轻量场景集    —— 「场景可判定；风险与敏感点成表」

「可机检」在本模块的具体含义（避免把映射写成散文）：
  1. 每一条都必须点名一个**在场**的仓库件（文档 / 脚本 / 判据），件不在场即 FAIL；
  2. 覆盖必须**恰好**是规范要求的那些层/段/属性，多一条少一条都 FAIL（防止事后凑数）；
  3. ATAM 每条场景必须同时给风险点、敏感点、权衡点三项非空文本——ATAM 的产出正是这三张表，
     只写「场景」不写三项就等于没做 ATAM。

用法：
    python scripts/standards_map.py --json
    python scripts/standards_map.py --self-test
"""
import argparse
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

#: P6-05：ISO 29119 的四层，各点名一件在场所指。
ISO29119_LAYERS = (
    {"layer": "process", "cn": "过程层", "example": "三段式门禁主执行体（check1..check40）",
     "artifact": "verify.sh"},
    {"layer": "documentation", "cn": "文档层", "example": "一致性声明与覆盖口径",
     "artifact": "protocol/CONFORMANCE.md"},
    {"layer": "technique", "cn": "技术层", "example": "跨语言差分测试（规范派生向量 + 三实现对拍）",
     "artifact": "desktop/tests/test_cross_lang_matrix.py"},
    {"layer": "coverage", "cn": "覆盖层", "example": "逐模块覆盖率下限取数",
     "artifact": "scripts/coverage_summary.sh"},
)
ISO29119_REQUIRED = ("process", "documentation", "technique", "coverage")

#: P6-09：NIST AI RMF 的四段职能，各点名一件在场所指（只涉 AI 编排面，不越界到全仓）。
AI_RMF = (
    {"function": "GOVERN", "cn": "治理", "requirement": "agent 行为纪律与安全闸门",
     "artifact": "AGENTS.md"},
    {"function": "MAP", "cn": "映射", "requirement": "标准面清单与适用范围",
     "artifact": "protocol/standards_catalog.json"},
    {"function": "MEASURE", "cn": "度量", "requirement": "可复算的验证报告",
     "artifact": "protocol/verification_report.json"},
    {"function": "MANAGE", "cn": "管理", "requirement": "发布策略与停止规则",
     "artifact": "protocol/release_policy.json"},
)
AI_RMF_REQUIRED = ("GOVERN", "MAP", "MEASURE", "MANAGE")

#: P6-10：ATAM 轻量场景集。每条 = 可判定的质量属性场景 + 风险点 + 敏感点 + 权衡点 + 判据件。
ATAM_SCENARIOS = (
    {"attribute": "性能", "scenario": "门禁在 docs 增量变更下 30s 内出结论",
     "response": "走快车道，跳过与读面无关的模块",
     "measure": "protocol/perf_budget.json 的预算字段未被突破",
     "evidence": "desktop/tests/test_perf_budget.py",
     "risk": "读面观测失败时快车道可能漏跑依赖模块",
     "sensitivity": "门禁选择器的读面完整度",
     "tradeoff": "跳过越多越快，但漏判风险越高——故观测缺失时 fail-closed 到全跑"},
    {"attribute": "可靠性", "scenario": "守护进程在插件崩溃/超时后仍存活",
     "response": "子进程隔离 + 回退参考实现 + 记录降级",
     "measure": "降级记录非空且宿主进程继续服务",
     "evidence": "desktop/tests/test_plugin_wasm_host.py",
     "risk": "回退路径本身有缺陷时会静默给出错误结果",
     "sensitivity": "燃料预算与超时阈值的取值",
     "tradeoff": "阈值越松越不易误杀，但越难拦住失控插件"},
    {"attribute": "安全性", "scenario": "内容/参数里夹带 ../ 路径",
     "response": "包含性判据 fail-closed 拒绝",
     "measure": "逃逸样本全部被拒且错误消息带修复指引",
     "evidence": "desktop/tests/test_trust_boundary.py",
     "risk": "判据只覆盖语法面，符号链接等运行时逃逸不在其内",
     "sensitivity": "validate_path 的词法规则集",
     "tradeoff": "规则越严越安全，但可能拒掉合法文件名"},
    {"attribute": "可维护性", "scenario": "新增 core 模块引入模块级环",
     "response": "耦合基线棘轮判红并要求登记",
     "measure": "环数 0 且 SDP 违例不超过冻结基线",
     "evidence": "desktop/tests/test_coupling_metrics.py",
     "risk": "基线重冻可能被当成「修好了」",
     "sensitivity": "冻结基线的重冻纪律",
     "tradeoff": "重冻越方便越容易掩盖新增债务"},
    {"attribute": "可移植性", "scenario": "同一实现换绑定形态（C ABI / PyO3）",
     "response": "两条绑定路径报同一 ABI 版本并可互证",
     "measure": "engine_loader.engine_abi 与扩展模块 abi_version 一致",
     "evidence": "desktop/tests/test_engine_ffi_binding.py",
     "risk": "两条路径分叉出不同的失败语义",
     "sensitivity": "ABI_VERSION 的升级判据",
     "tradeoff": "路径越多越灵活，维护成本按路径数增长（晋升门的判据 c）"},
)
ATAM_REQUIRED_ATTRS = ("性能", "可靠性", "安全性", "可维护性", "可移植性")


def _default_exists(root: Path) -> Callable[[str], bool]:
    return lambda rel: (root / rel).is_file()


def check_mapping(rows: tuple, key: str, required: tuple, exists: Callable[[str], bool],
                  label: str) -> list[str]:
    """映射类整改件的通用判据：覆盖恰好 + 条目齐备 + 所指件在场。"""
    issues: list[str] = []
    got = [str(r.get(key)) for r in rows]
    if sorted(got) != sorted(required):
        issues.append(f"{label} 覆盖不等于要求的集合：得到 {got}，要求 {list(required)}")
    for row in rows:
        rel = str(row.get("artifact") or "")
        if not rel:
            issues.append(f"{label}/{row.get(key)} 未点名在场件")
        elif not exists(rel):
            issues.append(f"{label}/{row.get(key)} 所指件不在场：{rel}")
    return issues


def atam_issues(rows: tuple, exists: Callable[[str], bool]) -> list[str]:
    """ATAM 场景集判据：属性覆盖 + 三项成表 + 场景可判定 + 判据件在场。"""
    issues: list[str] = []
    attrs = [str(r.get("attribute")) for r in rows]
    if sorted(attrs) != sorted(ATAM_REQUIRED_ATTRS):
        issues.append(f"ATAM 属性覆盖不等于要求：得到 {attrs}")
    for row in rows:
        who = f"ATAM/{row.get('attribute')}"
        for field in ("scenario", "response", "measure"):
            if not str(row.get(field) or "").strip():
                issues.append(f"{who} 缺可判定字段：{field}")
        for field in ("risk", "sensitivity", "tradeoff"):
            if not str(row.get(field) or "").strip():
                issues.append(f"{who} 缺 {field}（ATAM 的产出就是风险/敏感点/权衡点三张表）")
        rel = str(row.get("evidence") or "")
        if not rel or not exists(rel):
            issues.append(f"{who} 的判据件不在场：{rel or '(未点名)'}")
    return issues


def report(root: Path = ROOT, exists: Callable[[str], bool] | None = None) -> dict[str, Any]:
    """→ P6-05/P6-09/P6-10 的合并报告（机器面）。"""
    has = exists or _default_exists(root)
    issues = (check_mapping(ISO29119_LAYERS, "layer", ISO29119_REQUIRED, has, "P6-05 ISO 29119")
              + check_mapping(AI_RMF, "function", AI_RMF_REQUIRED, has, "P6-09 NIST AI RMF")
              + atam_issues(ATAM_SCENARIOS, has))
    return {
        "schema": "nf-standards-map/1",
        "ok": not issues,
        "issues": issues,
        "iso29119": [dict(r) for r in ISO29119_LAYERS],
        "ai_rmf": [dict(r) for r in AI_RMF],
        "atam": [dict(r) for r in ATAM_SCENARIOS],
    }


def _self_test() -> int:
    checks = 0
    always = lambda _rel: True  # noqa: E731 - 自证用的桩：这里要的就是「一律在场」
    assert report(ROOT, exists=always)["ok"], report(ROOT, exists=always)["issues"]
    checks += 1
    never = lambda _rel: False  # noqa: E731
    bad = report(ROOT, exists=never)
    assert not bad["ok"] and len(bad["issues"]) >= len(ISO29119_LAYERS) + len(AI_RMF), bad["issues"]
    checks += 1
    # 变异自证：少一层 / 属性名不符 / ATAM 缺权衡点，都必须判红
    short = check_mapping(ISO29119_LAYERS[:3], "layer", ISO29119_REQUIRED, always, "P6-05")
    assert short, short
    tampered = tuple({**r, "layer": "extra"} if i == 0 else r
                     for i, r in enumerate(ISO29119_LAYERS))
    assert check_mapping(tampered, "layer", ISO29119_REQUIRED, always, "P6-05")
    no_tradeoff = tuple({**r, "tradeoff": ""} if i == 0 else r
                        for i, r in enumerate(ATAM_SCENARIOS))
    assert atam_issues(no_tradeoff, always)
    checks += 1
    print(f"self-test OK（{checks} 例）")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="P6-05/09/10 标准面映射与场景集（只读）")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args(argv)
    if args.self_test:
        return _self_test()
    rep = report(ROOT)
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"== P6-05/09/10 标准面映射（{'OK' if rep['ok'] else 'NG'}）==")
        for issue in rep["issues"]:
            print(f"  ✗ {issue}")
        print(f"  ISO 29119 {len(rep['iso29119'])} 层 · NIST AI RMF {len(rep['ai_rmf'])} 段"
              f" · ATAM {len(rep['atam'])} 场景")
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    for _s in (sys.stdout, sys.stderr):
        if hasattr(_s, "reconfigure"):
            _s.reconfigure(encoding="utf-8")
    raise SystemExit(main())
