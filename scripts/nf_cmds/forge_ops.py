"""CLI 处理器：forge 族遗留命令（register/import-ir/design/pipeline/demo/lint/st-validate；自 nf.py 抽出）。"""
from __future__ import annotations

import os
import sys

from nf_cmds.common import (ROOT, _machine_fail, _open_store, _rel_display, _rel_out, json_doc)

def _seed_store(store, techdoc=False):
    """装载官方核心 + 轻混组合包（+ 技术文档域包，techdoc=True）。返回统计 dict。"""
    import glob
    from pathlib import Path
    from core.parser import parse_module
    stats = {"core": 0, "combo": 0, "techdoc": 0}
    for f in sorted(glob.glob(os.path.join(ROOT, "04_模块库", "*", "*.md"))):
        try:
            store.save_module(parse_module(Path(f).read_text(encoding="utf-8")))
            stats["core"] += 1
        except Exception:  # nosec B110/B112 —— 尽力而为：跳过不可读/不可解析项；该类缺口由对应门禁与 AUD-0016 静默跳过清单另行报出
            continue
    for f in sorted(glob.glob(os.path.join(ROOT, "community",
                                           "校园西幻轻混组合包", "modules", "*.md"))):
        try:
            store.save_module(parse_module(Path(f).read_text(encoding="utf-8")))
            stats["combo"] += 1
        except Exception:  # 尽力而为：跳过不可读/不可解析项（该类缺口由对应门禁与 AUD-0016 静默跳过清单另行报出）  # nosec B112 —— 尽力而为：跳过不可读/不可解析项（对应门禁另报；见 AUD-0016）
            continue
    if techdoc:
        # T3.1：交付物演示默认走技术文档域包（M97 术语管理 / M98 修订记录），
        # 与 `nf run --seed` 的历史口径（核心 + 轻混组合包）解耦——不改变既有 seed 行为。
        for f in sorted(glob.glob(os.path.join(ROOT, "community",
                                               "技术文档域包", "modules", "*.md"))):
            try:
                store.save_module(parse_module(Path(f).read_text(encoding="utf-8")))
                stats["techdoc"] += 1
            except Exception:  # nosec B112 —— 尽力而为：跳过不可读/不可解析项
                continue
    return stats

def _cmd_register(args) -> int:
    """nf register：本地登记助手（B3-B）。--check 只读 / --apply 合并写。"""
    from core.protocol_projection import project_entry
    from core.registry_sync import check_registerable, merge_protocols

    reg_path = args.registry or os.path.join(ROOT, "desktop", "src", "core", "registry.json")
    doc_path = os.path.join(ROOT, "02_联动注册表.md")

    # 三要件校验（② 02 在册；① protocol.yaml 由 check_registerable 内置）
    with open(doc_path, encoding="utf-8") as f:
        doc = f.read()
    issues = check_registerable(args.pkg_dir, doc)
    if issues:
        for msg in issues:
            print(f"  [拒绝] {msg}", file=sys.stderr)
        print("✗ 校验未通过——须先满足登记三要件（02 §8.3）；详见 02 §9.2 同步纪律", file=sys.stderr)
        return 1

    entry = project_entry(args.pkg_dir)

    import json
    with open(reg_path, encoding="utf-8") as f:
        reg = json_doc.loads(f.read(), dict, what=reg_path)
    cur = reg.get("protocols")
    if not isinstance(cur, list):
        print("✗ registry protocols[] 缺失或非列表", file=sys.stderr)
        return 1

    # 键序无关比较：merge 结果与现状在规范化（sorted keys）意义上相等 → 无实质变化
    def _canon(prots):
        return sorted(json.dumps(p, sort_keys=True, ensure_ascii=False) for p in prots)

    existing = next((p for p in cur if p["id"] == entry["id"]), None)
    merged = merge_protocols(cur, [entry])
    changed = _canon(merged) != _canon(cur)
    print(f"== nf register {entry['id']} [{args.mode}] ==")
    if not changed:
        print("  投影与 registry 现状一致，无更新（幂等，不写盘）")
        if args.mode == "apply":
            return 0
        return 0
    print("  将更新 protocols[]：%s" % ("新增" if existing is None else "覆盖"))
    diff_keys = sorted(k for k in entry if not existing or existing.get(k) != entry.get(k))
    if diff_keys:
        print("  差异字段：%s" % ", ".join(diff_keys))

    if args.mode != "apply":
        print("  [--check] 未写盘（--apply 才合并写入）")
        return 0

    reg["protocols"] = merged
    # EOL 纪律：仓库 = LF（.gitattributes `* text=auto eol=lf`）——Windows 文本模式默认 CRLF，
    # 实测会把 registry.json 写成 CRLF 并被 check33 编码卫生判 FAIL（2026-09-22 实测修）。
    # 原子写（2026-09-30 收口）：registry.json 是**全仓消费真源**（verify 各 check、
    # `nf run`/`nf serve` 都读它），半截的 registry 会让并发读者当场判「registry 不可读」。
    # 读-改-写串行化（2026-10-01）：原子写只保证「读者不见半截」，**不保证不丢更新**——
    # 实测两个进程各「读→改→原子写」同一 JSON 会丢一条（最终只剩后写者那条）。registry 是
    # 共享真源，故取排他锁后**重读并重并**（merge_protocols 按 id 幂等，重并即可合并并发写入）。
    from core import atomic_write
    with atomic_write.lock_file(reg_path, what="registry.json（nf register --apply）"):
        with open(reg_path, encoding="utf-8") as f:
            latest = json_doc.loads(f.read(), dict, what=reg_path)
        latest["protocols"] = merge_protocols(latest.get("protocols") or [], [entry])
        atomic_write.write_text(reg_path,
                                json.dumps(latest, ensure_ascii=False, indent=2) + "\n")
    print(f"  ✓ 已写入 {reg_path}（protocols[] {len(cur)} → {len(merged)} 条，只增不删）")
    print("  下一步：跑 `bash verify.sh` 由 check14 ⑦ 元素级断言自证")
    return 0

def _cmd_import_ir(args, fmt: str, rest: list) -> int:
    """T9.2 导入器路由：`nf import docx|dita <file> [--json/--out]`（只读面）。"""
    import json
    if len(rest) != 1:
        print("  ✗ 用法：nf import %s <file>（修复指引：一个导入器只收**单件**；"
              "`--out` 落点写成可选旗标）" % fmt, file=sys.stderr)
        return 2
    if getattr(args, "register", False):
        print("  ✗ docx/dita 导入为只读面，不支持 --register（修复指引：先 `--out` 出规范形 "
              "Markdown 再走内容库登记）", file=sys.stderr)
        return 2
    target = rest[0] if os.path.isabs(rest[0]) else os.path.join(ROOT, rest[0])
    if not os.path.isfile(target):
        print("  ✗ 文件不存在：%s（修复指引：给出在场的 .%s 路径——相对仓库根或绝对皆可）"
              % (rest[0], "docx" if fmt == "docx" else "dita"), file=sys.stderr)
        return 2
    if fmt == "docx":
        from core import import_docx as imp
    else:
        from core import import_dita as imp
    try:
        res = imp.import_file(target, base_dir=ROOT)
    except (imp.DocxImportError if fmt == "docx" else imp.DitaImportError) as exc:
        if getattr(args, "json", False):
            print(json.dumps({"schema": imp.SCHEMA, "kind": "import-%s" % fmt,
                              "file": rest[0], "ok": False, "error": str(exc)},
                             ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("  ✗ 导入失败：%s" % exc, file=sys.stderr)
        return 2
    report = res.to_dict()
    report.update({"ok": True, "kind": "import-%s" % fmt, "file": rest[0]})
    out_path = str(getattr(args, "out", "") or "")
    if out_path:
        from core import atomic_write
        from core import paths as _paths
        op = out_path if os.path.isabs(out_path) else _rel_out(out_path)
        op = _paths.validate_path(ROOT, op) if not os.path.isabs(op) else op
        try:
            atomic_write.write_text(op, res.markdown)
        except OSError as exc:
            print("  ✗ 写规范形失败：%s（修复指引：给可写路径；相对路径按仓库根解析）"
                  % exc, file=sys.stderr)
            return 2
        report["out"] = _rel_display(op)
    if getattr(args, "json", False):
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    stats = report.get("stats") or {}
    print("== nf import %s（%s → 内容 IR）==" % (fmt, rest[0]))
    print("  标题：%s" % (report.get("title") or "（无 H1）"))
    print("  节点：section %d · paragraph %d · table %d · list %d · claim %d"
          % (stats.get("sections", 0), stats.get("paragraphs", 0),
             stats.get("tables", 0), stats.get("lists", 0),
             stats.get("claims", 0)))
    if report.get("out"):
        print("  ✓ 规范形已写入：%s" % report["out"])
    for w in report.get("warnings") or []:
        print("  [WARN] %s" % w)
    if not (report.get("warnings") or []):
        print("  ✓ 无未覆盖元素/无降级告警")
    return 0

def _cmd_design(args) -> int:
    """nf design steelman：钢人论证工作单（v2.6-A，可选决策辅助）。

    init "<问题>"            → 生成空白工作单（frontmatter + 六段 + 引导模板）
    steelman --check <file>  → 结构自检（缺项 warn 列表，空 = 通过）
    steelman ls [--root]     → 列决策档案索引（已有 steelman.md）
    """
    from pathlib import Path
    from core.steelman import (init_worksheet, check_worksheet,
                               scan_steelman)

    if args.check_file:
        p = Path(args.check_file)
        if not p.exists():
            print(f"  ✗ 文件不存在: {p}（修复指引：用 `nf design steelman init \\\"<问题>\\\"` "
                  f"先生成工作单，再对该文件跑 --check）")
            return 1
        warns = check_worksheet(p.read_text(encoding="utf-8"))
        if not warns:
            print(f"  ✓ 结构自检通过（四步齐备 + meta 在场）: {p}")
            return 0
        print(f"== nf design steelman --check {p} ==")
        for w in warns:
            print(f"  ⚠ {w}")
        print(f"  → 缺项 {len(warns)} 条（补齐后重跑 --check）")
        return 1
    if args.action == "init":
        if not args.question:
            print("  ✗ init 需要问题描述: nf design steelman init \"<问题>\"")
            return 2
        out = Path(args.out) if args.out else Path.cwd() / "steelman.md"
        # 形状闸门（2026-10-01）：`--out <目录>` 此前落到 write 抛 `[Errno 13]`
        # 冒成「内部错误」（与 attest/st-validate 的 `--out` 同类）。
        if out.is_dir():
            return _machine_fail(
                args, "--out 落点是目录：%s（修复指引：`--out` 给**文件**路径（缺省 = "
                      "当前目录 steelman.md））" % args.out, 1)
        out.parent.mkdir(parents=True, exist_ok=True)
        init_worksheet(args.question, context=args.context,
                       decider=args.decider, path=out)
        print("== nf design steelman init ==")
        print(f"  ✓ 工作单已生成: {out}")
        print("    用三套引导模板之一填充六段，然后跑 --check 自检")
        return 0
    # ls
    root = Path(args.root)
    if not root.is_dir():
        print(f"  ✗ 目录不存在: {root}")
        return 1
    hits = scan_steelman(root)
    print("== nf design steelman ls ==")
    if not hits:
        print("  （无 steelman 工作单——nf design steelman init 生成第一份）")
        return 0
    print(f"  决策档案 {len(hits)} 份:")
    for h in hits:
        print(f"  · {h}")
    return 0

def _cmd_pipeline(args) -> int:
    """nf pipeline new：P00 骨架派生新管线（v2.8.0 波B S4）。"""
    if getattr(args, "pipeline_cmd", None) == "dryrun":
        from core import pipelinerun as pr
        import json as _json
        if args.all or not args.pipeline:
            if getattr(args, "write_advisory", False):
                doc = pr.advisory_report(ROOT, write=True)
                print("  ✓ advisory 台账已写入：共 %d 条 · %s"
                      % (doc["total"], doc["counts"]))
                return 0
            issues, tot = pr.sweep(ROOT)
            if args.json:
                print(_json.dumps({"kind": "pipeline-dryrun", "issues": issues,
                                   "stats": {k: v for k, v in tot.items()
                                             if k != "advisory_items"}},
                                  ensure_ascii=False, indent=2, sort_keys=True))
            else:
                print("== nf pipeline dryrun --all ==")
                print("  管线 %d · 模块 %d · 官方核心基座 %d · advisory %d"
                      % (tot["pipelines"], tot["modules"], tot["core_base"],
                         tot["notes"]))
                for cat, n in sorted(tot.get("advisory_buckets", {}).items()):
                    print("    · %-14s %d" % (cat, n))
                for i in issues:
                    print("  [FAIL] %s" % i, file=sys.stderr)
                if not issues:
                    print("  ✓ 全仓管线零 hard 缺陷（advisory 为同层序/跨包事件，不作判死）")
            return 1 if issues else 0
        try:
            g = pr.graph(args.pipeline, ROOT)
        except (OSError, ValueError) as exc:
            return _machine_fail(args, str(exc), 1)
        if args.json:
            print(_json.dumps({"kind": "pipeline-dryrun", **g},
                              ensure_ascii=False, indent=2, sort_keys=True))
            return 1 if g["issues"] else 0
        print("== nf pipeline dryrun：%s（%s）==" % (g["pipeline"]["id"], g["pipeline"]["name"]))
        print("  层 %d · 模块 %d · token %d · 事件 %d · hard %d · advisory %d"
              % (g["stats"]["layers"], g["stats"]["modules"], g["stats"]["tokens"],
                 g["stats"]["events_published"], g["stats"]["issues"],
                 g["stats"]["notes"]))
        for s in g["steps"]:
            mods = "、".join(m["id"] for m in s["modules"]) or "（空）"
            print("  %2d. %-4s %-14s %s" % (s["index"], s["layer"],
                                            s["layer_name"][:12], mods))
        for i in g["issues"]:
            print("  [FAIL] %s" % i, file=sys.stderr)
        for n in g["notes"][:6]:
            print("  [note] %s" % (n.get("detail") if isinstance(n, dict) else n))
        return 1 if g["issues"] else 0
    from core.pipeline_scaffold import scaffold_pipeline, default_filename
    tmpl = args.template or os.path.join(ROOT, "03_管线库",
                                         "P00_通用文档生成管线.md")
    try:
        with open(tmpl, encoding="utf-8") as fh:
            template = fh.read()
        new_text = scaffold_pipeline(template, args.id, args.name,
                                     domain=args.domain)
    except (OSError, ValueError) as exc:
        return _machine_fail(args, str(exc))
    dest = args.dest or os.path.join(ROOT, "03_管线库",
                                     default_filename(args.id.upper(), args.name))
    dest = os.path.abspath(dest)
    if os.path.exists(dest):
        print("  ✗ 目标已存在，不覆盖：%s" % dest, file=sys.stderr)
        return 1
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    from core import atomic_write          # 派生管线（在仓件）：原子写
    atomic_write.write_text(dest, new_text)
    print("== nf pipeline new ==")
    print("  ✓ 派生管线落盘：%s" % dest)
    print("  后续三步：① 按 01 §2 填层名 / default / allowed；② 新模块落 04_模块库 或复用通用件；")
    print("            ③ 登记 02_联动注册表 → Agent 即调度（I5，引擎不改）")
    print("  试跑：python scripts/nf.py run --pipeline %s"
          " --modules <领域模块 full_id> --seed --fmt ccv3" % dest)
    return 0

def _demo_pipeline_path(mode: str) -> str:
    """演示域 → 管线件路径（T3.1：缺省 techdoc，叙事域用 narrative）。"""
    if mode == "narrative":
        return os.path.join(ROOT, "community", "校园西幻轻混组合包",
                            "pipelines", "P04_轻混装配流管线.md")
    return os.path.join(ROOT, "community", "技术文档域包",
                        "pipelines", "P06_技术文档题材装配流管线.md")

def _cmd_demo(args) -> int:
    """nf demo：一键交付物演示——默认 P06 技术文档全链 → Markdown。

    T3.1 身份整改：缺省域 = techdoc（交付物路径），叙事域保留为 `nf demo narrative`
    （P04 轻混 → CCV3 卡）。两域共用同一 pipe（retrieve→compose→gate→export），
    差异仅在管线、取件模块与导出格式。
    """
    import tempfile
    import time
    from core.pipeline import pipe
    from core.pipeline_loader import load_pipeline_file
    mode = str(getattr(args, "mode", "") or "techdoc")
    pipeline_path = _demo_pipeline_path(mode)
    pipeline = load_pipeline_file(pipeline_path)
    if pipeline is None:
        print("  ✗ 演示管线解析失败：%s" % pipeline_path, file=sys.stderr)
        return 1
    store, err = _open_store(args)          # NF_HOME 不可用 ⇒ 干净拒绝（2026-10-01）
    if err is not None:
        return err
    stats = _seed_store(store, techdoc=(mode != "narrative"))
    dest = args.dest or tempfile.mkdtemp(prefix="nf_demo_")
    # 形状闸门（2026-10-01）：`--dest <文件>` 此前落到 makedirs 抛 `[WinError 183]`
    # 冒成「内部错误 + 机器路径」（与 `nf render --dest` 同类）。
    if os.path.exists(dest) and not os.path.isdir(dest):
        return _machine_fail(
            args, "--dest 落点是文件：%s（修复指引：`--dest` 给**目录**（缺省 = 系统临时目录）；"
                  "产物文件名由本命令决定）" % dest, 2)
    t0 = time.time()
    if mode == "narrative":
        selected = ["通用类:M00", "轻混类:M91", "轻混类:M92", "通用类:M80"]
        fmt = "ccv3"
    else:
        # 技术文档域：M00 数据基座 / M97 术语管理 / M98 修订记录 / M80 唯一输出门
        # （M90 结构装配经 P06 core 依赖引用，不占取件槽——见 P06 管线件 R2 段）
        selected = ["通用类:M00", "技术文档类:M97", "技术文档类:M98", "通用类:M80"]
        fmt = "md"
    r = pipe(store, pipeline, selected, include_references=(mode == "narrative"),
             fmt=fmt, dest_dir=dest)
    elapsed = time.time() - t0
    if mode == "narrative":
        print("== nf demo narrative（叙事域演示 · P04 轻混 → CCV3）==")
        print("  seed 装载：官方核心 %d 件 + 轻混组合包 %d 件"
              % (stats["core"], stats["combo"]))
    else:
        print("== nf demo（一键交付物演示 · P06 技术文档 → Markdown）==")
        print("  seed 装载：官方核心 %d 件 + 技术文档域包 %d 件"
              % (stats["core"], stats["techdoc"]))
    print("  全链计时：%.1f s（retrieve→compose→gate→export）" % elapsed)
    print("  质量门：PASS %d · WARN %d · FAIL %d"
          % (r.gate.n_pass, r.gate.n_warn, r.gate.n_fail))
    if r.export is not None and r.export.files:
        for f in r.export.files:
            print("  产物：%s" % f)
        if mode == "narrative":
            print("  装载：把上述 chara.json 导入任意 AI 前端 / SillyTavern 即可开跑")
        else:
            print("  装载：Markdown 可直接交付/审阅；再跑 `nf assemble \"…\" --check` 可机器验收")
    return 0 if r.ok else 1

def _cmd_lint(args):
    """nf lint：机械检查/修复（与 doc_hygiene / prose_lint 同源判据）。"""
    from core import autofix
    import json as _json
    if getattr(args, "kinds", False):
        from core import doc_hygiene as dh
        warns = dh.kind_rules(ROOT)
        print("== nf lint --kinds（四型写法判据）==")
        for w in warns:
            print("  [WARN] %s" % w)
        if not warns:
            print("  ✓ 四型写法齐（每型都有该型必备的结构块）")
        return 0
    try:
        if args.target:
            targets = []
            for t in args.target:
                p = t if os.path.isabs(t) else os.path.join(ROOT, t)
                if os.path.isdir(p):
                    for dirpath, _dirs, files in os.walk(p):
                        targets += [os.path.join(dirpath, f) for f in sorted(files)
                                    if f.endswith(".md")]
                elif os.path.exists(p):
                    targets.append(p)
                else:
                    return _machine_fail(
                        args, "目标不存在：%s（修复指引：给出在场路径（文件或目录，相对仓库根"
                              "或绝对皆可）；`ls` 列根级面，`nf lint` 缺省扫全仓）" % t)
        else:
            from core import doc_hygiene as dh
            rels = sorted(set(dh.REQUIRED_DOCS) | set(dh.INSTRUCTION_DOCS))
            targets = [os.path.join(ROOT, r) for r in rels
                       if os.path.exists(os.path.join(ROOT, r))]
        reports, prose = [], []
        for p in targets:
            if args.fix:
                rep = autofix.fix_file(p, root=ROOT, dry_run=args.dry_run)
                if rep["rules"]:
                    reports.append(rep)
            else:
                with open(p, encoding="utf-8") as fh:
                    text = fh.read()
                rules = autofix.lint_rules(p, text, ROOT)
                if rules:
                    reports.append({"path": p, "changed": False,
                                    "rules": [r["rule"] for r in rules]})
            if args.prose:
                from core import prose_lint
                extra = prose_lint.load_custom_terms(ROOT)
                with open(p, encoding="utf-8") as fh:
                    for f in prose_lint.lint_text(fh.read(), extra_terms=extra):
                        f = dict(f)
                        f["path"] = os.path.relpath(p, ROOT).replace("\\", "/")
                        prose.append(f)
        if args.json:
            print(_json.dumps({"kind": "lint", "mechanical": reports, "prose": prose},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            mode = ("修复（dry-run）" if args.dry_run
                    else "修复" if args.fix else "报告")
            print("== nf lint（%s · %d 目标）==" % (mode, len(targets)))
            for rep in reports:
                rel = os.path.relpath(rep["path"], ROOT).replace("\\", "/")
                print("  %s %s" % ("✎" if rep.get("changed") else "·", rel))
                print("      %s" % "、".join(rep["rules"]))
            if not reports:
                print("  ✓ 机械面无待办")
            if prose:
                print("  正文 lint：%d 条" % len(prose))
                for f in prose[:20]:
                    print("    [%s] %s:%d %s" % (f["rule"], f["path"],
                                                f["line"], f["message"]))
        if args.fix:
            return 0
        return 1 if (reports or prose) else 0
    except (OSError, ValueError) as exc:
        return _machine_fail(args, str(exc))

def _cmd_st_validate(args):
    """nf st-validate：ST 制卡校验器原型（A-S3）。"""
    from core import st_validator as sv
    from pathlib import Path
    import json as _json
    sp = args.path if os.path.isabs(args.path) else os.path.join(ROOT, args.path)
    if not os.path.isfile(sp):
        return _machine_fail(
            args, "目标不存在：%s（修复指引：给出在场卡/世界书 JSON 路径；"
                  "示例见 desktop/tests/fixtures/external/chara.json）" % args.path)
    try:
        # 打开用**绝对落点**（口径：相对路径按仓库根解析，不依赖进程 cwd；2026-10-01 修——
        # 此前把调用方原串直接递给 `sv.validate`，它 `Path(path).read_text()` 按 cwd 打开，
        # 从 `desktop/` 里跑仓内路径必判失败）。展示仍用调用方原串，不回吐机器路径。
        rep = sv.validate(sp)
        rep["path"] = args.path
    except _json.JSONDecodeError as exc:   # 在场但不是合法 JSON ⇒ 给口径，不给裸解析错误
        return _machine_fail(
            args, "不是合法 JSON：%s（%s）（修复指引：本命令收 chara_card_v3 卡 / 世界书 "
                  "JSON；示例见 desktop/tests/fixtures/external/chara.json）"
                  % (args.path, exc))
    except (OSError, ValueError) as exc:
        return _machine_fail(args, str(exc))
    md = sv.report_markdown(rep)
    if args.out:
        outp = args.out if os.path.isabs(args.out) else os.path.join(ROOT, args.out)
        # 形状闸门 + 兜底（2026-09-30 二扫）：`--out <目录>` 此前落到 open 抛
        # IsADirectoryError，且这段在 try 之外 ⇒ 冒到 CLI 兜底报「内部错误 + 机器路径」。
        if os.path.isdir(outp):
            return _machine_fail(
                args, "--out 落点是目录：%s（修复指引：给**文件**路径，如 "
                      "st-report.md）" % args.out, 1)
        try:
            Path(outp).parent.mkdir(parents=True, exist_ok=True)
            from core import atomic_write      # 校验报告：原子写
            atomic_write.write_text(outp, md)
        except OSError as exc:
            return _machine_fail(args, "写报告失败：%s（修复指引：给可写文件路径）"
                                 % exc, 1)
    if args.json:
        # `rep` 自带 `kind`（卡型：chara / worldbook）——那是**被检物**的类型判别，
        # 不是面判别；不得覆盖（覆盖会让消费方误读被检物类型）。
        print(_json.dumps(rep, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        c = rep.get("counts", {})
        print("== nf st-validate %s（%s：fail %d · warn %d · info %d）=="
              % (args.path, rep.get("kind"), c.get("fail", 0), c.get("warn", 0),
                 c.get("info", 0)))
        for i in rep.get("issues") or []:
            print("  [%s] %s %s" % (i["severity"].upper(), i["rule"], i["detail"]))
        if not rep.get("issues"):
            print("  ✓ 可自动化项全部通过（R1/R3/R4）")
        if args.out:
            print("  报告已写入：%s" % args.out)
    return 1 if (rep.get("counts", {}).get("fail", 0) > 0) else 0
