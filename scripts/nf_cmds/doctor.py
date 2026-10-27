"""CLI 处理器：doctor（环境自检；自 scripts/nf.py 抽出，按检查项拆小函数，行为逐字保留）。"""
from __future__ import annotations

import os
import sys

from nf_cmds.common import ROOT, _no_machine_paths


def _check_files(chk):
    for rel in ("README.md", "01_核心协议.md", "02_联动注册表.md",
                "06_Agent执行协议.md", "07_官方核心出厂与社区预设导航.md",
                "AGENTS.md", "STRATEGY.md", "verify.sh"):
        chk("文件在场 %s" % rel, os.path.isfile(os.path.join(ROOT, rel)), rel)


def _check_registry(chk):
    import json as _json

    reg_path = os.path.join(ROOT, "desktop", "src", "core", "registry.json")
    try:
        with open(reg_path, encoding="utf-8") as fh:
            reg = _json.load(fh)
        n_modules = len(reg.get("modules") or [])
        n_prots = len(reg.get("protocols") or [])
        chk("registry 可解析（modules=%d protocols=%d）" % (n_modules, n_prots),
            n_modules >= 13 and n_prots >= 5,
            "desktop/src/core/registry.json")
    except Exception as exc:
        chk("registry 可解析", False, "desktop/src/core/registry.json: %s" % exc)


def _check_schema(chk):
    sdir = os.path.join(ROOT, "protocol", "schema")
    try:
        n_schema = len([f for f in os.listdir(sdir) if f.endswith(".json")])
    except OSError as exc:
        n_schema = 0
        chk("IDL schema 定义在场", False, str(exc))
    if os.path.isdir(sdir):
        # 判据是「五份核心 IDL 定义在场」而非「恰好五份」——扩展协议面（发布策略 / 接入面 schema）
        # 会合法增份；写成 ==5 会把扩容判成缺陷（2026-10-05 实测：7 份被判 FAIL）。
        _core_idl = ("contract.schema.json", "module.schema.json", "pipeline.schema.json",
                     "protocol.schema.json", "asset.schema.json")
        _names = set(os.listdir(sdir))
        chk("IDL schema 定义在场（%d 份）" % n_schema,
            all(x in _names for x in _core_idl), "protocol/schema")


def _check_core_import(chk):
    try:
        sys.path.insert(0, os.path.join(ROOT, "desktop", "src"))
        from core import schema_lint  # noqa: F401
        chk("核心库可导入（schema_lint）", True, "desktop/src/core")
    except Exception as exc:
        chk("核心库可导入（schema_lint）", False, str(exc))


def _check_baseline(chk):
    try:
        from core import quality_baseline as qb
        q_issues, q_stats = qb.scan(ROOT)
        chk("基线自描述一致（verify %s · check1-%d PASS=%d）"
            % (q_stats["verify_version"], q_stats["checks"], qb.EXPECTED_PASS),
            not q_issues,
            "verify/README/CHANGELOG/VERSION-MATRIX")
    except Exception as exc:
        chk("基线自描述一致", False, str(exc))


def _check_jsonschema(chk):
    try:
        import json as _j
        from jsonschema import Draft202012Validator
        for f in sorted(os.listdir(os.path.join(ROOT, "protocol", "schema"))):
            if f.endswith(".json"):
                with open(os.path.join(ROOT, "protocol", "schema", f),
                          encoding="utf-8") as fh:
                    Draft202012Validator.check_schema(_j.load(fh))
        chk("schema 标准对照（jsonschema）", True, "CI 与本地同跑")
    except Exception as exc:
        chk("schema 标准对照（jsonschema）", True,
            "可选依赖未装（CI 已装真跑）：%s" % exc)


def _check_toolface(chk):
    try:
        from core import tool_face as tf
        tf_issues, tf_stats = tf.scan(ROOT)
        chk("模块工具面（tool_face）",
            not tf_issues,
            "模块 %d · 条目 %d · 候选 %d"
            % (tf_stats["modules"], tf_stats["entries"],
               tf_stats["candidates"]))
    except Exception as exc:
        chk("模块工具面（tool_face）", False, str(exc))


def _check_worldmodel(chk):
    try:
        from core import world_model as wm
        from core import world_slots as ws
        wm_issues, wm_stats = wm.scan(ROOT)
        ws_issues, ws_stats = ws.scan(ROOT)
        chk("world_model 契约",
            not wm_issues,
            "模块 %d · 变量 %d · checks %d · slots %d/%d"
            % (wm_stats["modules"], wm_stats["variables"],
               wm_stats.get("checks", 0), wm_stats.get("slots", 0),
               wm_stats.get("slot_registry", 0)))
        chk("world_slots 注册表",
            not ws_issues,
            "slots %d · arrays %d" % (ws_stats["slots"], ws_stats["arrays"]))
    except Exception as exc:
        chk("world_model/world_slots", False, str(exc))


def _check_yaml(chk):
    # 可选依赖降级面（2026-10-10 审计 Y7，P2）：缺 PyYAML 时上面几条扫描会**静默降级**
    # （tool_face 1/1/1→0/0/0、world_model 计数塌成 0），而此前只有 stderr 一行 WARN ⇒
    # 「计数塌成 0」照样显示 N/N 通过、--json 面无从判别 = 降级报绿。现在它是一条**会 FAIL 的
    # 检查**（CI 装了 PyYAML，故 CI 不受影响），并在 --json 面加 degraded 标记（fail-closed）。
    from core import lazy_yaml as _ly_doc
    yaml_ok = _ly_doc.module() is not None
    chk("可选依赖 PyYAML 在场（YAML 字段不降级）", yaml_ok,
        "PyYAML" if yaml_ok else
        "缺 PyYAML：YAML 面计数会塌成 0——本行即 FAIL（修复指引：pip install pyyaml；"
        "若只想静默 stderr 告警可设 NF_QUIET_YAML=1）")
    return yaml_ok


def run(args, version):
    """nf doctor：环境自检（快速只读体检；不开 verify 慢跑）。"""
    import json as _json

    checks = []

    def chk(name, ok, detail):
        # 体检明细只回**可移植**写法（2026-10-01 收口）：`detail` 此前会把 `sdir` 这类
        # 本机绝对路径原样写进 `--json`（隐私 + 换机不可解释）。兜一层 `_no_machine_paths`
        # 与失败消息同款纪律；各检查项自身也必须给仓库相对口径。
        checks.append({"name": name, "ok": bool(ok),
                       "detail": _no_machine_paths(str(detail))})

    _check_files(chk)
    _check_registry(chk)
    _check_schema(chk)
    _check_core_import(chk)
    _check_baseline(chk)
    _check_jsonschema(chk)
    _check_toolface(chk)
    _check_worldmodel(chk)
    yaml_ok = _check_yaml(chk)

    n_pass = sum(1 for c in checks if c["ok"])
    if args.json:
        print(_json.dumps({
            "kind": "doctor",
            "version": version,
            "ok": n_pass == len(checks),
            "passed": n_pass,
            "total": len(checks),
            "degraded": not yaml_ok,
            "checks": checks,
        }, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf doctor（nf %s）==" % version)
        for c in checks:
            print("  [%s] %s（%s）" % ("PASS" if c["ok"] else "FAIL",
                                       c["name"], c["detail"]))
        print("  体检：%d/%d 通过" % (n_pass, len(checks)))
    return 0 if n_pass == len(checks) else 1
