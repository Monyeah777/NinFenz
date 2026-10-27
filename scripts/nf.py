#!/usr/bin/env python3
"""NinFenz 全链管道 CLI（v2.1.0 B2：retrieve→compose→gate→export 单命令）。

用法：
  python scripts/nf.py run --pipeline <P04管线.md> \
      --modules 通用类:M00,轻混类:M91,轻混类:M92,通用类:M80 \
      [--store <dir>] [--seed] [--fmt ccv3|skill] [--dest <out>] \
      [--no-include-refs] [--force-export]

- 全链 = pipe()：模块选择 → compose（E3 references 并入）→ render_ir
  → quality_gate（三态）→ export（exporter._REGISTRY）。
- --seed：把 04_模块库 + community 组合包模块装载进临时 store（演示/自测用，
  等同 e2e 前置）；缺省要求 --store 指向已含所选模块的工作区。
- 打印 GateResult 摘要（PASS/WARN/FAIL）+ 产物路径；FAIL 且非 --force-export
  → exit 1（CLI 层门禁镜像 verify 铁律）。
- 产物×适配矩阵：skill 拒 narrative（适配器内拒出，warnings 带说明）——
  CLI 原样透传 warnings。
"""
import argparse
import os
import sys
from typing import Any, Dict, List, Optional

# argparse 的每个**内建** help 串都要过一次 `gettext.translation`（本机实测：建一次命令面 **432 次
# → 0.11 s**，每次都去 stat locale 目录），而本 CLI 不做本地化（help 全是中文字面量）。把翻译钩子
# 短路成恒等函数：实测 `_build_parser()` **102.8 → 8.4 ms**，~1900 次 stat 降到近乎零。必须在建面
# 之前打这个补丁（argparse 在 import 期就把 `gettext.gettext` 绑成了模块级 `_`）。
argparse._ = lambda message: message                                     # type: ignore[attr-defined,assignment]
argparse.ngettext = lambda singular, plural, n: singular if n == 1 else plural  # type: ignore[attr-defined]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
# stderr 同样钉 UTF-8：argparse 的用法错误与中文错误信息走 stderr，若随 locale（Windows 上
# 常为 GBK）落盘/进管道，UTF-8 消费方会解码失败（实测：管道读取方 UnicodeDecodeError）。
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "desktop", "src"))
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if _SCRIPT_DIR not in sys.path:
    sys.path.insert(0, _SCRIPT_DIR)
from core import interp_diet  # noqa: E402 - 紧接路径设定；`-S` 下补回 site-packages（见其 docstring）
from nf_cmds.common import (json_doc, _file_shape_issue, _existing_nonfile_issue, _portable_path, _rel_display, _rel_out, _machine_fail, _page_text, _surface_module_on_disk, _shell_baseline, _release_freeze)
from nf_cmds.surfaces import (_cmd_lsp, _cmd_facts, _cmd_license, _cmd_endpoint, _cmd_assertions, _cmd_conformance, _cmd_stats, _cmd_registry, _cmd_model, _cmd_spec, _cmd_ir, _cmd_ops, _cmd_glossary, _cmd_security, _cmd_privacy)
from nf_cmds.misc import (_cmd_sig, _cmd_diff, _cmd_telemetry, _cmd_changelog, _cmd_receipts, _cmd_layers, _cmd_attest, _cmd_runtime, _cmd_agent)
from nf_cmds.shelf import (_cmd_combine, _cmd_output, _cmd_market)
from nf_cmds.domain import _cmd_domain
from nf_cmds.knowledge import _cmd_knowledge
from nf_cmds.asset import _cmd_asset
from nf_cmds.library import _cmd_library
from nf_cmds.module import _cmd_module
from nf_cmds.assemble import _cmd_assemble
from nf_cmds.govern import (_cmd_design_audit, _cmd_approve, _cmd_handover, _cmd_postmortem, _cmd_audit, _cmd_decide, _cmd_decisions, _cmd_review, _cmd_workloop)
from nf_cmds.integrate import (_cmd_toolface, _cmd_transparency, _cmd_locales, _cmd_events, _cmd_driver, _cmd_state_front, _cmd_interop, _cmd_render, _cmd_bench)
from nf_cmds.library_ops import (_cmd_patterns, _cmd_related, _cmd_impact, _cmd_rename, _cmd_who_refers, _cmd_cognition, _cmd_rfc)
interp_diet.restore()





NF_CLI_VERSION = "1.1.0"
NF_CLI_EPILOG = (
    "入门：\n"
    "  nf shell              # 交互终端（能力菜单 + 命令直通；端壳退役后的人机入口）\n"
    "  nf --help             # 全命令总览\n"
    "  nf help <cmd>         # 查看任意子命令帮助\n"
    "  nf doctor             # 环境自检（快速只读体检）\n"
    "  nf completion bash    # 生成 shell 补全（>> ~/.bashrc）\n"
    "  nf run / nf demo      # 作者五分钟上手（README「五分钟快速开始」含逐条示例）\n"
    "退出码：0 成功 · 1 运行/校验失败 · 2 用法错误（argparse 约定）。"
)


#: 命令面缓存（效率）：argparse 面构建 ≈100 ms/次，而一次终端命令往往要建 3 次以上
#: （索引 + 命令树 + 真正解析）——`--verify --deep` 的全命令扫描更是 64 次。
#: 缓存后同一进程内只建一次；解析器只读复用（构建期之外无人改它）。
_PARSER_CACHE = None
_TREE_CACHE = None
_INDEX_CACHE = None


def _build_parser() -> argparse.ArgumentParser:
    """取命令面（**带缓存**）：首次构建，其后复用同一实例（只读）。"""
    global _PARSER_CACHE
    if _PARSER_CACHE is None:
        _PARSER_CACHE = _make_parser()
    return _PARSER_CACHE


def _make_parser() -> argparse.ArgumentParser:
    """真正构建 argparse 命令面（实现已抽到 scripts/nf_parser/；注册顺序保持不变）。"""
    import importlib.util as _ilu
    _pkg_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "nf_parser")
    _spec = _ilu.spec_from_file_location("nf_parser",
                                          os.path.join(_pkg_dir, "__init__.py"),
                                          submodule_search_locations=[_pkg_dir])
    _mod = _ilu.module_from_spec(_spec)
    sys.modules["nf_parser"] = _mod
    _spec.loader.exec_module(_mod)
    return _mod.make_parser(root=ROOT, version=NF_CLI_VERSION, epilog=NF_CLI_EPILOG)


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












def _cmd_import(args) -> int:
    """nf import：旧面（SKILL.md/chara.json）+ T9.2 导入器（docx/dita → 内容 IR）。

    旧面：SKILL.md → parse_skill（含 skill_dir 随行资源扫描）；chara.json →
    parse_ccv3。--register 把 IR 模块幂等装载进 Store（save_module 覆盖式幂等，
    同 seed_from_repo 模式）。
    导入面：`nf import docx <file>` / `nf import dita <file>`（子命令式路由：首个位置
    参数是 `docx`/`dita` 时走导入器，旧面的单文件调用 **保持不变**）。
    """
    import json
    from pathlib import Path
    from core.import_adapter import parse_skill, parse_ccv3
    from core.models import Module

    raw_files = getattr(args, "file", [])
    files = list(raw_files) if isinstance(raw_files, (list, tuple)) else [raw_files]
    files = [str(f) for f in files if str(f).strip()]
    if files and files[0] in ("docx", "dita"):
        return _cmd_import_ir(args, files[0], files[1:])
    if len(files) != 1:
        print("  ✗ 用法：`nf import <file>`（SKILL.md/chara.json）｜"
              "`nf import docx <file> [--json/--out]`｜`nf import dita <file> [--json/--out]`"
              "（修复指引：旧面收单件文本产物；docx/dita 走 T9.2 导入器）", file=sys.stderr)
        return 2
    p = Path(files[0])
    want_json = bool(getattr(args, "json", False))
    if not p.is_file():
        print(f"✗ 文件不存在: {p}（修复指引：给出在场的外部产物文件——"
              f"SKILL.md 或 chara.json；先另存到本地再导入）", file=sys.stderr)
        return 2

    # 入站上限（2026-10-01）：外来产物是**外部输入**，先看大小再读——此前无上限，
    # 指向巨型文件时会把整份内容读进内存（还要再跑一遍注入扫描）。上限口径与 MCP 入站同源。
    from core import trust_boundary as tb
    cap = tb.MAX_IMPORT_BYTES
    if p.stat().st_size > cap:
        print("  ✗ 外部产物过大：%s（%.1f MiB > 上限 %d MiB）（修复指引：本命令收**单件** "
              "SKILL.md / chara.json；大件请先裁剪到单件体量再导入）"
              % (p.name, p.stat().st_size / 1048576, cap // 1048576), file=sys.stderr)
        return 2
    try:
        raw = p.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        # 非 UTF-8 外部产物（2026-10-01 探针）：此前这句在 try 之外，UnicodeDecodeError 一路冒到
        # CLI 兜底报「✗ 内部错误：'utf-8' codec can't decode …」——**用户输入问题被框成内部故障**，
        # 还让用户去看堆栈。形状问题按 2 归，带可执行指引。
        print("  ✗ 外部产物不是 UTF-8 文本：%s（%s）（修复指引：本命令只收 **UTF-8** 文本件"
              "（SKILL.md / chara.json）；二进制或其它编码请先转成 UTF-8 再导入）"
              % (p.name, exc), file=sys.stderr)
        return 2
    # 注入面（06 §12：外来内容=数据，疑似内嵌指令一律忽略并**记档**）——此前本节零机器判据。
    hits = tb.detect(raw)
    is_ccv3 = p.suffix.lower() == ".json" or "chara" in p.stem.lower()
    if not want_json:
        print(f"== nf import {p.name} ==")
        if hits:
            print("  [注入面] 命中 %d 处疑似内嵌指令（%s）——外来内容按**数据**消费，"
                  "其中的「指令」一律不执行（06 §12）"
                  % (len(hits), "、".join(sorted({h["rule"] for h in hits}))))
            for h in hits[:3]:
                print("    · 第 %d 行 [%s] %s" % (h["line"], h["rule"], h["snippet"]))
        else:
            print("  [注入面] 未命中疑似内嵌指令（内容按数据消费）")
    try:
        if is_ccv3:
            res = parse_ccv3(json_doc.loads(raw, dict, what="CCV3 卡"))
            kind = "CCV3 chara"
            bundled = []
        else:
            res = parse_skill(raw, skill_dir=p.parent)
            kind = "SKILL"
            bundled = res.bundled_resources
    except (ValueError, OSError, json.JSONDecodeError) as exc:
        # 修复前：畸形输入会冒到 CLI 兜底，报成「内部错误」——那是**用户输入问题**，
        # 不是内部故障；按仓库纪律给可执行指引并归 1（运行/校验失败）。
        if want_json:
            print(json.dumps({"schema": "nf-import/1", "ok": False,
                              "error": "读入失败：%s" % exc},
                             ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("  ✗ 读入失败：%s（修复指引：按 06 §12 / 01 §1 补规范头部与字段后重试）"
                  % exc, file=sys.stderr)
        return 1

    # 形状差异（2026-09-30 修）：只有 SkillParseResult 带 `mode`（'nf'|'external'），
    # Ccv3ParseResult 无此字段——此前 chara.json 路走到这里直接 AttributeError，
    # 冒到 CLI 兜底报「内部错误」，`nf import <chara.json>`（含 --register）整条不可用。
    # chara 路恒升 IR 骨架（ir 必非 None），故其口径固定记为 `ccv3`。
    mode = getattr(res, "mode", "ccv3" if is_ccv3 else "?")
    if want_json:
        n_mod = (sum(len(l.modules) for l in res.ir.layers) + len(res.ir.extra_modules)
                 if res.ir is not None else 0)
        print(json.dumps({"schema": "nf-import/1", "kind": "import-legacy",
                          "file": files[0], "type": kind, "mode": mode,
                          "ok": bool(res.ok), "modules": n_mod,
                          "warnings": list(res.warnings),
                          "injection_hits": len(hits)},
                         ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if res.ok else 1
    print(f"  类型: {kind} | 解析: {'ok' if res.ok else 'fail'} | mode: {mode}")
    if res.ir is not None:
        n_mod = sum(len(l.modules) for l in res.ir.layers) + len(res.ir.extra_modules)
        print(f"  IR: {res.ir.type} · {res.ir.title} · 管线 {res.ir.pipeline_id} · {n_mod} 模块")
    if bundled:
        print(f"  随行资源: {', '.join(bundled)}")
    for w in res.warnings:
        print(f"  [警告] {w}")

    if not args.register:
        return 0
    if res.ir is None:
        print("✗ 无 IR 可登记（external 模式未升 IR）", file=sys.stderr)
        return 1

    store, err = _open_store(args, args.store)   # 落点不可用 ⇒ 干净拒绝（含 OSError：盘/权限）
    if err is not None:
        return err
    n = 0
    for layer in res.ir.layers:
        for im in layer.modules:
            fid = im.full_id
            cat, num = fid.rsplit(":", 1) if ":" in fid else ("通用类", fid)
            store.save_module(Module(id=num, name=im.name, category=cat,
                                    layer=im.layer, source_md=im.content))
            n += 1
    for im in res.ir.extra_modules:
        fid = im.full_id
        cat, num = fid.rsplit(":", 1) if ":" in fid else ("通用类", fid)
        store.save_module(Module(id=num, name=im.name, category=cat,
                                layer=im.layer, source_md=im.content))
        n += 1
    print(f"  ✓ 已幂等装载 {n} 模块 → {_portable_path(store.home)}")
    # 闭环指引（实测缺口 2026-09-30）：该 store 里**只有导入件**，直接拿去 `nf run` 会因缺
    # 官方核心锚点（P00/P80）报「本地不存在 / 未装配」——这里如实告诉下一步。
    print("  下一步：这个 store 里只有本次导入的模块；跑全链前先补官方核心 —— "
          "`nf run --seed --store %s`（临时装载核心）或把 04_模块库 也 register 进来。"
          % _portable_path(store.home))
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








def _cmd_serve(args) -> int:
    """nf serve [mcp.json]：stdio JSON-RPC 服务（C1，MCP client 拉起）。

    默认路径（无参）= **实时仓库面**：不要求先产快照——直接起只读 resources/tools/prompts
    面（数据源 = 仓库只读扫描），适合 agent 密集重复调用（免掉「先 run 再 serve」两跳）。
    给快照路径时行为不变（烧快照面）。

    transport 纪律：stdout 只写 MCP 消息（换行分隔 JSON-RPC）——初始化说明走 stderr。
    """
    from core.mcp_runtime import load_snapshot, McpRuntime

    if args.snapshot:
        label = os.path.basename(args.snapshot)
        try:
            snapshot = load_snapshot(args.snapshot)
        except OSError as exc:
            print("  ✗ 快照不可读：%s（修复指引：确认路径；或直接 `nf serve` 走实时仓库面，无需快照"
                "）"
                  % exc, file=sys.stderr)
            return 2
        except ValueError as exc:
            print("  ✗ 快照形状不合规：%s" % exc, file=sys.stderr)
            return 2
    else:
        label = "live（实时仓库面，无需快照）"
        snapshot = {"mcp": {"name": "nf-repo-live", "version": NF_CLI_VERSION,
                            "resources": []}}
    print(f"== nf serve {label} =="
          f"（stdio JSON-RPC，Ctrl+C 退出）", file=sys.stderr)
    # 参数 ⇄ inputSchema 校验器**在此注入**（依赖倒置：mcp_runtime 是稳定侧，不反向依赖
    # 校验器；见其 __init__ docstring）——上架通道因此逐条执行 tools/list 里那份声明。
    from core import json_schema
    return McpRuntime(snapshot, schema_check=json_schema.json_schema_check).serve_stdio()


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




#: `--root` 受闸门的**读类**命令（落点必须是在场目录）。写类（`asset add` 会自建台账目录）
#: 不在此列——它们本来就该能创建落点。
_ROOT_READERS = {
    ("asset", "ls"), ("asset", "verify"), ("asset", "inventory"),
    ("asset", "density"), ("asset", "usage"), ("asset", "thickness"),
    ("asset", "ledger"), ("asset", "baseline"),
    ("module", "ls"), ("module", "verify"),
    ("design", "audit"), ("design", "steelman"),
    ("lsp", ""),
}


def _root_pair(args) -> tuple:
    """→ `(顶层命令, 二级子命令)`（`--root` 落点闸门用的分类键）。"""
    cmd = str(getattr(args, "cmd", "") or "")
    sub = ""
    for att in ("asset_cmd", "module_cmd", "design_cmd", "registry_cmd", "ops_cmd"):
        val = getattr(args, att, None)
        if val:
            sub = str(val)
            break
    return (cmd, sub)















def _open_store(args, home: str = ""):
    """构造 Store → (store, err_code)；NF_HOME / --store 不可用时**干净拒绝**。

    为什么（2026-10-01 取证）：`NARRATIVE_FORGE_HOME=Z:\\nope`（盘符不存在）或指向一个**文件**
    时，`nf preset ls` / `nf demo` / `nf run --seed` 都冒到 CLI 兜底报「✗ **内部错误**：
    [WinError 3] …（重跑 NF_DEBUG=1 看堆栈）」——**用户配置问题被框成内部故障**，零指引还让人去
    看堆栈。既有两处守卫只捕 `ValueError`（形状不符），漏了 `OSError`（盘/权限），另两处
    （`demo` / `preset`）根本没有守卫；四处共用一个构造点，故在此收口。
    """
    from core.storage import Store
    try:
        # 口径统一（2026-10-01）：**相对路径按仓库根**解析（与 `--out` / `--dest` / `--root` 同）。
        # 实测此前 `--store relstore` 落在**进程 cwd**（从临时目录跑就落到临时目录），而同一个
        # CLI 的 `--out` / `--root` 都是仓根语义——同名概念两套解析，读者没法预测落点。
        if home and not os.path.isabs(home):
            home = os.path.join(ROOT, home)
        return (Store(home=home) if home else Store()), None
    except (OSError, ValueError) as exc:
        # 内层 `storage.Store` 的守卫自带修复指引（落点是文件/越界）；重复追加只会让读者看到
        # 两条「修复指引」——故只在内层没给时补我们这条（2026-10-01 实测去重）。
        msg = str(exc)
        if "修复指引" not in msg:
            msg += ("（修复指引：`--store` / `NARRATIVE_FORGE_HOME` 须给**目录**路径——不存在会"
                    "自动创建；指向文件、不存在的盘符或无权限位置都会在此失败）")
        return None, _machine_fail(
            args, msg, 1)


CHECK_GUIDE = {
    "1": "缺什么：官方核心目录结构件缺失（01/02/06/07/README/LICENSE + 官方管线 P00/P01/P90）。补什"
        "么：按 07 §7 项1 清单补齐根级文件与 03_管线库 官方管线。",
    "2": "缺什么：重号 ID 未全限定（官方层裸号重复）。补什么：官方核心层模块引用一律全限定（通用:M1"
        "0/事件:M22），07 §7 项5。",
    "3": "缺什么：五条不变式落点缺失或错位。补什么：核对 01 §5 ↔ 07 §7 项6 的逐条落点声明。",
    "4": "缺什么：认知边界断链（06 §4 管线 ↔ M23 认知域不一致）。补什么：对齐执行协议与 M23 的裁剪/"
        "过滤口径。",
    "5": "缺什么：质检门流水线违约（M80 gate_action ↔ 06 §5）。补什么：核对输出生成器的 gate_action"
        " 三态与执行协议一致。",
    "6": "缺什么：入口导航断链（README → 07 → 协议链/官方目录）。补什么：按 07 §7 项6 修 README 路"
        "由。",
    "7": "缺什么：社区两包结构完整度违约。补什么：校园/西幻包 modules/pipelines/protocol.yaml/READM"
        "E 与 02 §8 在册数一致。",
    "8": "缺什么：社区资产外形与基线不一致（文件数 / 行数 / 逐文件摘要）。补什么：核对内容后显式重"
        "签 `nf asset baseline --write`（07 §7 项3）。",
    "9": "缺什么：模块-资产引用不可寻址或社区 README 重号未限定。补什么：资产键真实可寻址 + 社区重"
        "号限定引用。",
    "10": "缺什么：EXT 闭合违约或社区红线未落地。补什么：EXT 实体闭合 + 红线条目对齐 07 §7 项2/8。",
    "11": "缺什么：资产-模块三方对账不一致（02 §8.1 ↔ modules/ ↔ assets/README）。补什么：三方条目"
        "对齐（08 方案 T5 A5）。",
    "12": "缺什么：desktop/src 或 scripts 语法/单测失败。补什么：跑 python -m unittest discover -s desktop/tests 修到全绿；示例：新模块未补测试→先写测试再实现。",
    "13": "缺什么：02 头部与 registry.json 协议版本不一致或迁移记录不全。补什么：版本改动需 02 §9.3"
        " 四步（快照/bump/迁移说明/回读）。",
    "14": "缺什么：社区协议登记缺 protocol.yaml/Schema 12 字段/登记三要件。补什么：01 §6.1 + 02 §8."
        "3 补齐并保持 registry protocols[] 一致。",
    "15": "缺什么：组合引用 references 违约（不在册/闭包未闭合/层冲突/schema 不兼容/双源不一致）。"
        "补什么：按 02 §8.4 五断言核对。",
    "16": "缺什么：machine_contract 机读结构或装配 publish⊆subscribe 违约。补什么：01 §1.1 契约字段"
        " + 运行时寻址授权一致。",
    "17": "缺什么：质量门 unittest 失败。补什么：装配/锚点/资产悬空需过 quality_gate 语义。",
    "18": "缺什么：导出契约 unittest 失败。补什么：ccv3_adapter/exporter 映射层检查锚点与条目。",
    "19": "缺什么：导出产物 shape 与 schema 不符。补什么：对照 export_schema 5 格式自检。",
    "20": "缺什么：模块文档必填项缺失。补什么：按文档完整性清单补必填字段。",
    "21": "缺什么：registry 引用图悬空/裸号重复。补什么：清理 source_package/module_id 引用。",
    "22": "缺什么：导出物规范体检失败（spec_version/name/description 超限）。补什么：按 export_sche"
        "ma 硬约束修正。",
    "23": "缺什么：资产供应链台账违约（不可溯源/不可发现/键孤儿）。补什么：05_资产库/provenance.jso"
        "n + 文件头双源一致。",
    "24": "缺什么：模块状态位异常或 deprecated/retired 被引用。补什么：module deprecate/restore 流"
        "转或移除引用方。",
    "25": "缺什么：01-36 编号方案文档签名不可复现/结构缺标题。补什么：文档须 UTF-8 且含 # 标题，同"
        "一内容重复生成须逐字节一致；示例：nf sig --verify。",
    "26": "缺什么：语义矛盾（techdoc 链订阅事件无发布方 / 挂载点或类别漂移）。补什么：全库补发布方"
        "或修正漂移；示例：nf related 反查 + semantic_conflict.scan。",
    "27": "缺什么：架构纯度违约（端壳残留/私货可变物/重复标题/raise 消息缺修复指引/第三方 import 未"
        "登记）。补什么：purity_scan 五规则逐条修；示例：R1 端壳关键词残留清理、R5 第三方 import 改"
        "软导入并在 SOFT_IMPORTS 登记理由。",
    "28": "缺什么：协议层 IDL 违约（schema 定义缺失或协议件字段漂移）。补什么：protocol/schema 五定"
        "义在场 + 在场 machine_contract/管线/协议包/台账过 schema；示例：nf doctor 看 schema 在场。"
        "",
    "29": "缺什么：Conformance 虚标或声明缺失（声明级别 > 可证级别）。补什么：按 01 §1.2 与 conform"
        "ance_scan 提示降级或补证据。",
    "30": "缺什么：扩展判据缺失或版本字段 bump 无迁移记录。补什么：protocol/EXTENSION.md 判据 + bum"
        "p 变更带 01 §7/02 §9.3 四步迁移记录。",
    "31": "缺什么：生成物过期（protocol/generated 与当前 schema/协议件不一致）。补什么：重跑 protoc"
        "ol_golden.write_golden 并随变更一并提交。",
    "32": "缺什么：质量纵深汇总违约（载荷注册表/资产 ledger/指令审计/资产密度·厚度·零引用/tool_face"
        "/world_model/world_slots 任一缺口）。补什么：跑 nf release 看细分失败项，修复后 verify 全"
        "绿；world_model 契约自查可用 nf worldmodel。",
    "33": "缺什么：新面汇总任一子扫描红（MCP dual-era/stdio 帧纪律、attestation、基线回归评分、机械"
        "修复、正文 lint、编辑器面（能力/诊断定位/didClose/退出码/领域智能/配置生成）、许可证门、遥"
        "测 semconv、编码卫生、互操作导出与入仓面、文档命令面、决策层面、构建回路）。补什么：`nf do"
        "ctor` 先定位，再按面跑 `nf interop --check` / `nf lint` / `nf score` / `nf telemetry` / `n"
        "f conformance`；编码卫生命中按 `docs/text-hygiene.md` 处置（隐形字符/行尾/重复键）。",
    "34": "缺什么：云端图书馆面违约（frontmatter 真源缺字段、INDEX·ALIAS 投影漂移、生命周期状态越表"
        "、文档四型未覆盖、llms.txt 入口缺失、内容分级未声明）。补什么：`nf library verify` 看逐条"
        "失败；改条目 frontmatter 后 `nf library reindex` 重建投影（投影不是真源）。",
    "35": "缺什么：深化面违约（管线抽象执行 GraphSpec、馆藏回执单根、模块边界冻结、内容绑定批准、一"
        "致性报告工件、无效语料）。补什么：按失败项分别跑 `nf pipeline dryrun --all` / `nf library "
        "receipts --write` / `nf module signature --write` / `nf approve --verify` / `nf conformanc"
        "e --write`。",
    "36": "缺什么：治理面违约（一致性声明 CONFORMANCE、RFC 版本史、指令档机器面路由、实践包、跑分台"
        "、端点契约）。补什么：`nf conformance` 看契约面，并用 `nf rfc` / `nf driver` / `nf pattern"
        "s verify` / `nf endpoint` 逐条对；改声明件后重跑。",
    "37": "缺什么：双源知识层违约（权威分层、查询有序、时效、消化可追溯、认知裁剪越权）。补什么：`n"
        "f knowledge lint` 逐条看巡检结论（`nf knowledge order|visible` 可复核顺序与可见性；本子命"
        "令**没有** `--check`）；补 `protocol/knowledge_sources.json` 声明或消化记录后重跑（越权源"
        "不得进入任何 clearance 的查询顺序）。",
    "38": "缺什么：出口自动化违约（自述数字与实算不一致、他证通道缺回填、GEO 出口过期、FDE 样例不过"
        "）。补什么：`nf stats --write` 重写生成区；`docs/standards/index.md` 与 `protocol/geo_expo"
        "rt.json` 重渲染；FDE 样例跑 `python scripts/fde_sample_run.py` 看失败项。",
    "39": "缺什么：端壳残留回潮 / 终端三件缺失 / 菜单指向死命令 / 命令面未策展 / 输出不确定。补什么"
        "：按 `docs/L3_FROZEN.md` 裁决删除残留件；`nf shell --verify` 看终端自检逐项失败；新增命令"
        "要登记进 `core/terminal.py` 的能力族。",
    "40": "缺什么：数字资产契约违约（数据格式/字段完整性/输入输出一致性/防篡改；代码 AST 规范、可证空指针、测试用例在场；脚本 nf-io 头与声明双源不一致、链上 A 输出不匹配 B 输入）。补什么：`nf asset contract` 逐条看；数据件改声明或补字段；脚本补 `# nf-io: inputs=… outputs=…` 头并与 protocol/asset_contracts.json 对齐；sha256 漂移确认后用 `nf asset contract --freeze` 重冻。",
    "41": "缺什么：构建隔离违约（构建入口出现取网/取包命令；Dockerfile 基座未按 @sha256 钉或写了"
          " :latest；engines.node / engine/rust/Cargo.lock 缺位；CI 的 setup-python / setup-node 未给"
          "具体版本号）。补什么：先跑 core.build_isolation.scan 看逐条；构建入口改读仓内既有件、基座"
          "换成 name:tag@sha256:*、工具链把版本写死（不浮动 major）。",
    "42": "缺什么：provenance 校验不过（回执单根形状坏 / 独立子进程验签失败 / 篡改未被检出）。补什么"
          "：nf receipts --scope protocol --write 重建单根；确认 nf attest --key-file 与"
          " core.attest.verify 的口径一致；篡改必须被判否——否则这份证据是摆设。",
    "43": "缺什么：契约语义规则不过（层序闭包/域隔离/门全性 FAIL）。补什么：跑 nf spec check "
          "--core 看 rule/subject/evidence；修注册表或管线声明；不可判定项按 WARN 记录，不假装通过。",
    "44": "缺什么：注册表 CID 与在盘索引不一致（包内文件被改/增删）。补什么："
          "nf registry index --write 重签；确认改动是预期的，否则回滚该包文件。",
    "45": "缺什么：内容供应链扫描出现 critical（可执行内容/明文凭据）。补什么："
          "nf security scan 定位 file:line；删除或转义危险内容；合法安全研究样本走显式白名单。",
    "46": "缺什么：隐私/air-gap 门禁不过（PII/本机绝对路径/凭据 critical，或网络站点静态审计"
          "命中未登记出口）。补什么：跑 nf privacy scan / nf privacy check 看 file:line；"
          "改写绝对路径、删除或掩码凭据、把合法网络出口登记进 allowlist；warn 只报告不判死。",
    "47": "缺什么：CLI IA 生成件与实时重算不一致，或命令覆盖率不闭合（未归族/重复归族/空族/"
          "虚指）。补什么：跑 nf cli map --json/--check 看 coverage；重跑 nf cli map --write；"
          "新命令须在 terminal.FAMILIES 恰好归一族。",
}

def _cmd_preset(args):
    """nf preset：预设配置（一份存档 = 管线 + 模块 + 资产包 的**一次组装**）。

    为什么补（2026-10-01）：`core/preset_manager.py` 是退役端壳（L3_FROZEN：桌面 GUI 永久
    退役）留下的 UI 面预设语义（snapshot / apply / export / import），而 `nf` 命令面**零引用**
    ⇒ 预设能力不可达，已在 `test_dead_code.TEST_ONLY_ALLOWED` 如实登记为缺口。本命令按那条
    登记里写明的补齐方向（「端壳能力一律落 CLI」）把预设接成命令。

    落点 = **NF_HOME**（用户态预设库），不写仓库；`apply` 只做**解析**（管线 + 模块 + 资产包
    + 本地缺失提示），真生产仍走 `nf run`。
    """
    import json as _json
    from core import preset_manager as pm
    from core.models import Preset

    sub = getattr(args, "preset_cmd", None) or "ls"
    store, err = _open_store(args, getattr(args, "store", ""))   # 同上：干净拒绝
    if err is not None:
        return err
    want_json = bool(getattr(args, "json", False))
    home_txt = _portable_path(store.presets_root)

    def _find(name: str):
        want = str(name or "").strip()
        return next((p for p in store.list_presets() if p.name == want), None)

    if sub == "ls":
        rows = [p.to_json() for p in store.list_presets()]
        if want_json:
            print(_json.dumps({"kind": "preset-ls", "home": home_txt,
                               "count": len(rows), "rows": rows},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("== nf preset ls（%d 条 · 预设库 %s）==" % (len(rows), home_txt))
            for r in rows:
                print("  %-22s %-6s 模块 %-3d 资产包 %s"
                      % (r.get("name"), r.get("pipeline"),
                         len(r.get("modules") or []), r.get("asset_pack") or "-"))
            if not rows:
                print("  （空；`nf preset save <名> --pipeline P04 --modules 通用类:M00` 建一条）")
        return 0
    if sub == "show":
        p = _find(args.name)
        if p is None:
            return _machine_fail(args, "预设未找到：%s（修复指引：`nf preset ls` 可枚举本机预设）"
                                 % args.name, 1)
        if want_json:
            print(_json.dumps({"kind": "preset-show", "home": home_txt,
                               "preset": p.to_json()},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("== nf preset show %s ==" % p.name)
            print("  管线：%s" % p.pipeline)
            print("  模块：%s" % ("、".join(p.modules) or "（空）"))
            print("  资产包：%s" % (p.asset_pack or "（空）"))
            print("  建档：%s" % (p.created_at or "-"))
        return 0
    if sub == "apply":
        p = _find(args.name)
        if p is None:
            return _machine_fail(args, "预设未找到：%s（修复指引：`nf preset ls` 可枚举本机预设）"
                                 % args.name, 1)
        res = pm.apply_preset(store, p)
        modules = [m.full_id for m in res["modules"]]
        if want_json:
            print(_json.dumps({"kind": "preset-apply", "name": p.name,
                               "pipeline": res["pipeline"], "modules": modules,
                               "asset_pack": res["asset_pack"],
                               "warnings": res["warnings"]},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("== nf preset apply %s ==" % p.name)
            print("  管线：%s · 模块 %d 件：%s"
                  % (res["pipeline"], len(modules), "、".join(modules) or "（空）"))
            print("  资产包：%s" % (res["asset_pack"] or "（空）"))
            for w in res["warnings"]:
                print("  [WARN] %s" % w)
            if not res["warnings"]:
                print("  ✓ 装配清单已解析（本机模块齐备）；真生产：nf run --pipeline %s "
                      "--modules %s --store <store>" % (res["pipeline"], ",".join(modules)))
        return 0
    if sub == "save":
        if _find(args.name) is not None and not args.force:
            return _machine_fail(
                args, "同名预设已存在：%s（修复指引：换名，或加 --force 覆盖；"
                      "`nf preset show %s` 先看现状）" % (args.name, args.name), 1)
        p = Preset(name=args.name.strip(), pipeline=(args.pipeline or "P01").strip(),
                   modules=[m.strip() for m in (args.modules or "").split(",") if m.strip()],
                   asset_pack=(args.assets or "").strip())
        path = store.save_preset(p)
        if want_json:
            print(_json.dumps({"kind": "preset-save", "ok": True, "name": p.name,
                               "path": _portable_path(path), "preset": p.to_json()},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("  ✓ 预设已保存：%s（%s）" % (p.name, _portable_path(path)))
        return 0
    if sub == "rm":
        if not store.remove_preset(args.name):
            return _machine_fail(args, "预设未找到：%s（修复指引：`nf preset ls` 可枚举）"
                                 % args.name, 1)
        if want_json:
            print(_json.dumps({"kind": "preset-rm", "ok": True, "name": args.name},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("  ✓ 已删除预设：%s" % args.name)
        return 0
    if sub == "export":
        p = _find(args.name)
        if p is None:
            return _machine_fail(args, "预设未找到：%s（修复指引：`nf preset ls` 可枚举）"
                                 % args.name, 1)
        if os.path.isdir(_rel_out(args.out)):
            return _machine_fail(args, "--out 落点是目录：%s（修复指引：给**文件**路径，"
                                 "如 my.preset.json）" % args.out, 1)
        if not pm.export_preset_file(p, args.out):
            return _machine_fail(args, "写导出件失败：%s（修复指引：给可写文件路径）" % args.out, 1)
        if want_json:
            print(_json.dumps({"kind": "preset-export", "ok": True, "name": p.name,
                               "out": args.out}, ensure_ascii=False, indent=2,
                              sort_keys=True))
        else:
            print("  ✓ 预设已导出：%s → %s" % (p.name, args.out))
        return 0
    # import
    p = pm.import_preset_file(store, args.file)
    if p is None:
        return _machine_fail(
            args, "预设不可用：%s（修复指引：收 `nf preset export` 产的 JSON（含 name 与 "
                  "pipeline 两个必需字段）；文件须在场且可读）" % args.file, 1)
    if (args.name or "").strip():
        p = Preset(name=args.name.strip(), pipeline=p.pipeline, modules=list(p.modules),
                   asset_pack=p.asset_pack, created_at=p.created_at)
        store.save_preset(p)
    if want_json:
        print(_json.dumps({"kind": "preset-import", "ok": True, "name": p.name,
                           "home": home_txt, "preset": p.to_json()},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("  ✓ 预设已导入本机：%s（%s）" % (p.name, home_txt))
    return 0





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
















#: 收路径的旗标 dest（`--out` / `--dest` / `--store` / `--key-file` / `--trace` …）——写法闸门
#: 只扫这些，**不扫自由文本参数**（`--note` / 需求描述 / 问题陈述里出现 `..` 是正常写法）。
#: 名单由「argparse 面里 help 含路径类词」运行时枚举得到，再逐条人工剔除非路径项。
_PATH_FLAG_DESTS = ("out", "dest", "build_dest", "save_path", "store", "trace", "session_path",
                    "state", "state_path", "key_file", "ssh_key", "ssh_allowed_signers",
                    "registry", "root", "case", "exceptions", "check_file", "check_md",
                    "artifact", "verify", "ledger", "history", "template", "dst", "script_file",
                    "baseline", "pipeline", "questions", "plan", "record", "replay")


def _path_writing_issue(args) -> str:
    """收路径旗标的**写法闸门** → 问题描述（合规返回空串）。

    口径（2026-10-01，与 `core.paths.validate_path` 同源）：**绝对路径按原样**（落到 CI 产物目录 /
    临时导出是设计面），**相对路径一律相对仓库根**且不得含 `..` 段 / 盘符相对写法——后者看着像
    仓内相对路径，实际会静默逃出仓库（实测 `nf interop --kind openapi --out ../x.json` 写到仓外，
    且报成「内部错误」）。集中一处判 ⇒ 覆盖全部收路径命令，错误也框成用户问题。
    """
    from core import paths as _p
    for dest in _PATH_FLAG_DESTS:
        val = getattr(args, dest, "")
        if not isinstance(val, str) or not val.strip() or os.path.isabs(val):
            continue
        try:
            _p.validate_path(ROOT, val)
        except _p.PathEscapeError as exc:
            return ("路径写法越界：--%s %s（修复指引：相对路径一律相对**仓库根**，不得含 `..` 段 / "
                    "盘符相对写法；确实要落到仓库外请给**绝对路径**）（%s）"
                    % (dest.replace("_", "-"), val, exc))
    return ""


#: **读进来当文本**的参数（旗标 + 位置参数）→ 过编码闸。名单口径（2026-10-01 三批后的最终态）：
#: **从 argparse 面运行时枚举**（help 里自称「文件 / 路径 / JSON / md / 信封 / 快照 / 规则 / 脚本 /
#: 台账 / 清单」的非布尔参数），再减去两类：
#:   ① **二进制输入**：`--key-file` / `--ssh-key`（HMAC/SSH 密钥是**字节**，不是文本）；
#:   ② **写侧落点**：`--out` / `--dest` / `--to` / `--session` / `--write`（那些是**目标**，
#:      不是被读的内容；把目标也拦会把「覆盖一个已有二进制文件」误判成输入错误）。
#: 为什么不再手写名单：二批普查抓到 5 处漏网，根因就是「同一概念换了个参数名（`path` / `paths`）
#: 就漏出闸门」——所以改成**枚举为准**，并由 `test_cli_error_framing.PathFlagCoverageTest`
#: 的对账判据保证「枚举到的文本类参数都在这里，或写明为什么豁免」。
_UTF8_BINARY_EXEMPT = {"key_file": "HMAC 密钥是字节", "ssh_key": "SSH 私钥是字节",
                       "fmt": "导出格式枚举（md/ccv3/skill/…，ASCII，非文本件）"}
_UTF8_TEXT_DESTS = ("a", "action", "artifact", "b", "baseline", "check", "check_file",
                    "check_md", "entry", "exceptions", "face", "file", "history", "key", "ledger",
                    "mode", "name", "package", "path", "paths", "pipeline", "pkg",
                    "questions", "registry", "root", "runs", "script_file", "snapshot",
                    "source", "ssh_allowed_signers", "state", "state_path", "subject",
                    "target", "template", "tier", "trace", "verify", "plan", "record", "replay")


def _utf8_text_issue(args) -> str:
    """输入件必须是 UTF-8 文本 → 问题描述（合规 / 不在场 / 超限一律返回空串）。

    依据（2026-10-01 探针）：把**非 UTF-8** 文件喂给 `nf attest` / `nf lint` / `nf import` /
    `nf run --pipeline` / `nf decide --state`，此前要么冒「✗ 内部错误：'utf-8' codec can't
    decode…（重跑 NF_DEBUG=1 看堆栈）」，要么只回裸解码错——**用户输入问题被框成内部故障**，
    且零指引。读盘在各命令里分散，故在入口集中判一次：**文本件一律 UTF-8**（本仓编码卫生口径），
    不合即 clean 拒 + 可执行指引。密钥等二进制输入**不在此列**（那类是字节，不是文本）。
    """
    for dest in _UTF8_TEXT_DESTS:
        raw = getattr(args, dest, "")
        # 位置参数可以是**列表**（`nf lint a.md b.md` 的 `target` 是 `nargs="*"`）——两条形态都判。
        values = raw if isinstance(raw, (list, tuple)) else [raw]
        for val in values:
            if not isinstance(val, str) or not val.strip():
                continue
            path = val if os.path.isabs(val) else os.path.join(ROOT, val)
            if not os.path.isfile(path):
                continue
            # T9.2 二进制导入面：.docx/.doc 是 zip/二进制，不由 UTF-8 文本闸判（各自导入器
            # fail-closed 判 zip/XML 形状）。
            if path.lower().endswith((".docx", ".docm", ".doc")):
                continue
            try:
                if os.path.getsize(path) > 8 * 1024 * 1024:  # 超大件交各命令自己的体量闸门
                    continue
                with open(path, "rb") as fh:
                    fh.read().decode("utf-8")
            except UnicodeDecodeError as exc:
                label = ("--%s" % dest.replace("_", "-") if dest in _PATH_FLAG_DESTS
                         else "<%s>" % dest)
                return ("输入件不是 UTF-8 文本：%s %s（%s）（修复指引：本仓文本面一律 UTF-8；"
                        "其它编码先转换（如 `iconv -f gbk -t utf-8`），二进制请换文本件）"
                        % (label, val, exc))
            except OSError:
                continue
    return ""


























def _cmd_score(args):
    """nf score：基线相对回归评分（绝对门之上的 no-silent-worsening 面）。"""
    from core import regression_score as rs
    from datetime import datetime, timezone
    import json as _json
    try:
        cur = rs.evaluate(ROOT)
        # 形状闸门（2026-09-30 同族扫）：`--baseline <目录>` 此前落到 load_baseline 抛裸
        # Errno；**不在场**仍允许（按空基线起手，`--write-baseline` 可落新基线）。
        _bi = _existing_nonfile_issue(
            args.baseline, "--baseline",
            "修复指引：给基线 JSON 的**文件**路径（缺省 = protocol/score_baseline.json；"
            "不存在时会按空基线起手）")
        if _bi:
            return _machine_fail(args, _bi, 1)
        base_rel = args.baseline or rs.DEFAULT_BASELINE
        base_path = (base_rel if os.path.isabs(base_rel)
                     else os.path.join(ROOT, base_rel))
        if os.path.exists(base_path):
            # 格式闸门（2026-10-01）：坏基线此前落到外层的 `_machine_fail(str(exc))`，
            # 回吐裸解析错（`Expecting property name…`）——与本命令 `--exceptions` 的门
            # 口径不一致（那边有「形如 …」的指引）。同一命令两个相邻旗标，判据必须同款。
            try:
                baseline = rs.load_baseline(base_path)
            except ValueError as exc:
                return _machine_fail(
                    args, "基线不是合法 JSON：%s（%s）（修复指引：给 `nf score "
                          "--write-baseline` 产的基线件；缺省位 %s）" % (base_rel, exc,
                                                                    rs.DEFAULT_BASELINE), 1)
        else:
            baseline = {"schema": rs.SCHEMA}
        exceptions = []
        if args.exceptions:
            exc_path = (args.exceptions if os.path.isabs(args.exceptions)
                        else os.path.join(ROOT, args.exceptions))
            # 形状 + 格式闸门（2026-10-01）：`--exceptions <目录/缺失件>` 此前抛裸
            # `[Errno 13]/[Errno 2]`（零指引），与 `--baseline` 同类。
            if not os.path.isfile(exc_path):
                return _machine_fail(
                    args, "例外表不存在：%s（修复指引：`--exceptions` 给**在场 JSON 文件**，"
                          "形如 `[{\"signal\": \"…\", \"reason\": \"…\"}]`（例外只标注理由、"
                          "不隐藏回归）；不给即按零例外判）" % args.exceptions, 1)
            try:
                with open(exc_path, encoding="utf-8") as fh:
                    exceptions = _json.load(fh)
            except ValueError as exc:
                return _machine_fail(
                    args, "例外表不是合法 JSON：%s（修复指引：形如 "
                          "`[{\"signal\": \"…\", \"reason\": \"…\"}]`）" % exc, 1)
        out = rs.compare(cur, baseline, tolerance=args.tolerance,
                         exceptions=exceptions)
        if args.write_baseline:
            rs.save_baseline(base_path, cur,
                             recorded_at=datetime.now(timezone.utc)
                             .strftime("%Y-%m-%dT%H:%M:%SZ"),
                             note="nf score --write-baseline")
        if args.json:
            print(_json.dumps({"kind": "score", "current": cur, "compare": out},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("== nf score（基线相对回归评分）==")
            print("  当前 %.2f · 基线 %.2f · delta %+.2f · 容差 %.2f"
                  % (out["current_score"], out["baseline_score"],
                     out["delta"], args.tolerance))
            print("  %s" % out["verdict"])
            for s in cur["signals"]:
                print("  · %-18s w=%.2f v=%.2f" % (s["name"], s["weight"], s["value"]))
            for r in out["regressed"]:
                print("    [REGRESS] %s %.4f → %.4f（%.4f）"
                      % (r["signal"], r["from"], r["to"], r["drop"]),
                      file=sys.stderr)
            if args.write_baseline:
                print("  基线已写入：%s" % _rel_display(base_path))
        return 0 if out["ok"] else 1
    except (OSError, ValueError, _json.JSONDecodeError) as exc:
        return _machine_fail(args, str(exc), 1)



def _cmd_explain(args):
    """nf explain：41 波C C5 —— check 修复指引（缺什么/补什么/示例）。"""
    key = args.check.strip().lower()
    if key in ("all", ""):
        print("== nf explain all（check 修复指引全量）==")
        for k in sorted(CHECK_GUIDE):
            print("  check%s：%s" % (k, CHECK_GUIDE[k]))
        return 0
    if key.startswith("check"):
        key = key[5:]
    guide = CHECK_GUIDE.get(key)
    if not guide:
        print("  ✗ 未知 check：%s（可用 all 看全量）" % args.check, file=sys.stderr); return 2
    print("== nf explain check%s ==" % key)
    print("  %s" % guide); return 0



def _cmd_help(args):
    """nf help [COMMAND]：显示 nf 总帮助或指定子命令帮助。"""
    root = _build_parser()
    command = getattr(args, "command", None)
    if command:
        for action in root._actions:
            if isinstance(action, argparse._SubParsersAction):
                choice = action.choices.get(command)
                if choice is not None:
                    choice.print_help()
                    return 0
        print("  ✗ 未知子命令：%s（nf --help 看全量）" % command, file=sys.stderr)
        return 2
    root.print_help()
    return 0


def _cmd_doctor(args):
    """nf doctor：环境自检（实现见 nf_cmds/doctor.py）。"""
    from nf_cmds.doctor import run as _doctor_run
    return _doctor_run(args, NF_CLI_VERSION)


#: 终端检索索引里单行摘要的截断长度（列出命令面时保持一行一条）
_SHELL_SUMMARY_MAX = 100


#: 终端可用的着色模式（与 core/terminal.resolve_color 同词表）
_SHELL_COLOR_MODES = ("auto", "always", "never")




def _shell_command_index() -> list:
    """终端检索索引：从 argparse 面派生（命令真源 = CLI 面，终端不留第二份）。

    每条 = {path, summary, flags}；path 含二级（如 `asset ls`）。check39 断言索引覆盖
    **全部**顶层命令——「最全功能」在终端侧的可机检形态就是「每个命令都能被检索到」。
    """
    global _INDEX_CACHE
    if _INDEX_CACHE is not None:
        return _INDEX_CACHE
    def _flags(parser):
        out = []
        for act in parser._actions:
            if isinstance(act, argparse._SubParsersAction):
                continue
            out += list(act.option_strings)
        return sorted(set(out))

    def _summary(parser):
        text = (parser.description or "").strip()
        if not text:
            return ""
        first = text.splitlines()[0].strip()
        return first if len(first) <= _SHELL_SUMMARY_MAX \
            else first[:_SHELL_SUMMARY_MAX - 1] + "…"

    root = _build_parser()
    out = []
    for act in root._actions:
        if not isinstance(act, argparse._SubParsersAction):
            continue
        for name, sp in act.choices.items():
            out.append({"path": name, "summary": _summary(sp), "flags": _flags(sp)})
            for act2 in sp._actions:
                if isinstance(act2, argparse._SubParsersAction):
                    for n2, sp2 in act2.choices.items():
                        out.append({"path": "%s %s" % (name, n2),
                                    "summary": _summary(sp2), "flags": _flags(sp2)})
    _INDEX_CACHE = sorted(out, key=lambda e: e["path"])
    return _INDEX_CACHE








def _cmd_shell(args) -> int:
    """nf shell（别名 nf terminal）：终端交互入口（端壳退役后的人机面）。"""
    from core import session_watch as _sw, terminal as term   # 会话缓存包装（见 core.session_watch）

    index = _shell_command_index()

    def runner(argv):
        argv = list(argv)
        if argv and argv[0] in ("shell", "terminal"):
            print("  终端内不再开终端（避免递归会话）："
                  "请另开一个终端窗口运行 nf shell。", file=sys.stderr)
            return 2
        return main(argv)

    # 会话状态（`--session`）：显式 CLI 参数 > 会话文件 > 缺省
    state, state_warn = term.load_session_state(args.session_path)
    _s = (state.get("settings") or {}) if state else {}
    color_mode = args.color or str(_s.get("color") or "auto")
    width = args.width or int(_s.get("width") or 0) or 0
    limit = args.limit if args.limit is not None else int(_s.get("limit") or 0)
    color_on = term.resolve_color(color_mode, sys.stdout)
    if state_warn:
        print("  [WARN] %s" % state_warn, file=sys.stderr)
    if args.session_path and not os.path.isabs(args.session_path):
        print("  ✗ --session 须给绝对路径（修复指引：用 <NF_HOME>/shell_session.json 之类的仓库外路"
            "径）",
              file=sys.stderr)
        return 2
    _sess_abs = os.path.abspath(args.session_path) if args.session_path else ""
    _scratch_prefix = os.path.abspath(os.path.join(ROOT, ".rivet")) + os.sep
    _inside_repo = bool(_sess_abs) and _sess_abs.startswith(os.path.abspath(ROOT))
    _in_scratch = bool(_sess_abs) and _sess_abs.startswith(_scratch_prefix)
    if args.session_path and _inside_repo and not _in_scratch:
        print("  ✗ --session 不得落在仓库内（修复指引：会话状态属本机用户态，请放到 NF_HOME 或临时"
            "目录——"
              "仓库内留件会被 git add -A 吞掉，2026-09-26 实测过）", file=sys.stderr)
        return 2
    # 历史落点（交互态；`--exec`/`--file` 一律不写，保确定性）
    history_path = None
    if not args.no_history:
        history_path = args.history or term.default_history_path()
    if args.form_id is not None and not args.form_id:
        if args.json:
            import json as _json
            print(_json.dumps({"kind": "forms", "count": len(term.form_table()),
                               "rows": [{"id": f["id"], "title": f["title"],
                                         "summary": f["summary"],
                                         "steps": [dict(st) for st in f["steps"]],
                                         "argv": list(f["argv"])}
                                        for f in term.form_table()]},
                              ensure_ascii=False, indent=2))
            return 0
        print(term.render_forms("", width or None, color_on))
        return 0
    if args.form_id:
        form = term.form_by_id(args.form_id)
        if form is None:
            print("  ✗ 未识别的表单：%s（可用：%s；或 nf shell --form 列全部）"
                  % (args.form_id, "、".join(str(f["id"]) for f in term.form_table())),
                  file=sys.stderr)
            return 2
        answers = {}
        for pair in args.answer or []:
            k, _, v = str(pair).partition("=")
            answers[k.strip()] = v.strip()
        missing = term.form_missing(form, answers)
        if missing:
            print("  [FAIL] 表单 %s 还缺必填项：%s（修复指引：--answer %s=…）"
                  % (form["id"], "、".join(missing), missing[0]), file=sys.stderr)
            return 2
        argv = term.build_argv(form, answers)
        if args.json:
            import json as _json
            if not args.yes:
                print(_json.dumps({"kind": "form-plan", "id": form["id"],
                                   "argv": argv, "executed": False},
                                  ensure_ascii=False, indent=2))
                return 0
            code = runner(argv)
            print(_json.dumps({"kind": "form-run", "id": form["id"], "argv": argv,
                               "executed": True, "exit": code},
                              ensure_ascii=False, indent=2))
            return code
        if not args.yes:
            print("== 表单 %s（%s）==" % (form["title"], form["id"]))
            print("  组装命令：nf %s" % " ".join(argv))
            print("  （dry-run：加 --yes 才执行；交互态用 /form %s 逐项追问）" % form["id"])
            return 0
        print("== 表单 %s（%s）· 执行 ==" % (form["title"], form["id"]))
        print("  nf %s" % " ".join(argv))
        return runner(argv)

    if args.surface_write is not None:
        tree = _collect_cli_tree()
        payload = term.surface_payload(tree["commands"], tree["root_flags"])
        target = args.surface_write or term.SURFACE_MODULE_PATH
        try:
            from core import paths as _paths
            full = _paths.validate_path(ROOT, target)
        except Exception as exc:                         # noqa: BLE001 - 落点不合法即用法错误
            return _machine_fail(args, "生成件落点不合法：%s" % exc, 2)
        text = term.render_surface_module(payload)
        parent = os.path.dirname(full)
        if parent and not os.path.isdir(parent):
            os.makedirs(parent, exist_ok=True)
        from core import atomic_write
        atomic_write.write_text(full, text)
        rel = os.path.relpath(full, ROOT).replace("\\", "/")
        if args.json:
            import json as _json
            print(_json.dumps({"kind": "surface-write", "ok": True, "path": rel,
                               "digest": payload["digest"],
                               "lines": len(text.splitlines()),
                               "source": payload["source"]["module"]},
                              ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        print("  ✓ 终端面投影已刷新：%s（真源 %s · %s）"
              % (rel, payload["source"]["module"], payload["digest"][:19]))
        return 0
    if args.surface:
        tree = _collect_cli_tree()
        payload = term.surface_payload(tree["commands"], tree["root_flags"])
        if args.json:
            import json as _json
            print(_json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        print(_page_text(term.render_surface(payload, width or None, color_on), args.pager))
        return 0
    if args.commands is not None:
        if args.json:
            import json as _json
            filt = (args.commands or "").lower()
            rows = [e for e in index
                    if not filt or filt in str(e.get("path")).lower()
                    or filt in str(e.get("summary") or "").lower()]
            print(_json.dumps({"kind": "commands", "filter": args.commands or "",
                               "count": len(rows), "rows": rows},
                              ensure_ascii=False, indent=2))
            return 0
        print(_page_text(term.render_commands(index, args.commands or "",
                                              limit=limit, width=width or None,
                                              color=color_on), args.pager))
        return 0
    if args.family_map is not None:
        if args.json:
            import json as _json
            fams = term.families_for(args.family_map or "")
            print(_json.dumps({"kind": "map", "filter": args.family_map or "",
                               "count": len(fams),
                               "families": [{"id": f["id"], "name": f["name"],
                                             "summary": f["summary"],
                                             "commands": list(f["commands"])}
                                            for f in fams]},
                              ensure_ascii=False, indent=2))
            return 0
        print(_page_text(term.render_map(args.family_map or "", width or None,
                                         color_on), args.pager))
        return 0
    if args.search:
        text, hits = term.render_search(index, args.search, width=width or None,
                                        color=color_on)
        print(_page_text(text, args.pager))
        return 0 if hits else 2
    if args.baseline:
        import contextlib
        import io

        def _capture(argv, stdin_text=None):
            """证据行执行：捕获输出（基线表只判「输出里有没有/有没有违规片段」）。"""
            buf = io.StringIO()
            old_in = sys.stdin
            if stdin_text is not None:
                sys.stdin = io.StringIO(str(stdin_text))
            try:
                with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                    code = main(list(argv))
            finally:
                sys.stdin = old_in
            return code, buf.getvalue()

        self_issues = term.baseline_argv_issues()
        results, stats = term.run_baseline(_capture)
        failed = [r for r in results if not r["ok"]]
        shown = term.portable_rows(results)     # 展示/机器面回 `{TMP}`（本机路径不回吐）
        if args.json:
            import json as _json
            print(_json.dumps({"kind": "shell-baseline",
                               "ok": not self_issues and not failed,
                               "self_issues": self_issues, "stats": stats,
                               "rows": shown}, ensure_ascii=False, indent=2))
            return 0 if (not self_issues and not failed) else 1
        print(term.render_baseline(shown, stats, width or None, color_on))
        for i in self_issues:
            print("  [FAIL] 基线自身不合规：%s" % i)
        for r in failed:
            why = ("耗时 %s ms > 预算 %s ms" % (r["ms"], r["max_ms"]) if r["content_ok"]
                   else "期望含 %r 且不含 %r" % (r["expect"], r["forbid"]))
            print("  [FAIL] %s：退出码 %s（证据：nf %s；%s）"
                  % (r["id"], r["exit"], " ".join(r["argv"]), why))
        return 0 if (not self_issues and not failed) else 1

    if args.verify:
        import shutil
        tree = _collect_cli_tree()
        if args.deep:
            import contextlib
            import io
            live_buf = io.StringIO()

            def _live(argv):
                """活体执行：**捕获**输出（机器面须纯 JSON）。逐条 `--help` 的扫描输出不留在
                `live_buf`——否则人读面会把最后一条 help 当成「活体输出」打印（实测踩过）。"""
                is_help_sweep = len(argv) >= 2 and str(argv[-1]) == "--help"
                buf = io.StringIO()
                with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
                    code = main(list(argv))
                if not is_help_sweep:
                    live_buf.truncate(0)
                    live_buf.seek(0)
                    live_buf.write(buf.getvalue())
                return code

            issues, stats = term.deep_check(
                index, tree["commands"], tree["root_flags"],
                live_runner=_live,
                history_path=history_path, session_path=args.session_path or None,
                stream=sys.stdout,
                pager_ok=bool(shutil.which("less") or shutil.which("more")))
            stats["live_output"] = term.clip(live_buf.getvalue().strip(), 300)
        else:
            issues, stats = term.self_check(index, tree["commands"], tree["root_flags"])
        # 投影对账（与 check39 同源判据）：真源改了却没重生成 ⇒ 当场红
        issues = list(issues) + term.surface_sync_issues(
            _surface_module_on_disk(), tree["commands"], tree["root_flags"])
        if args.json:
            import json as _json
            print(_json.dumps({"kind": "shell-verify", "ok": not issues,
                               "deep": bool(args.deep), "issues": issues,
                               "stats": stats}, ensure_ascii=False, indent=2))
            return 0 if not issues else 1
        print("== nf shell --verify（终端自检 · 与 verify check39 同源判据%s）=="
              % (" · 活体档" if args.deep else ""))
        for i in issues:
            print("  [FAIL] %s" % i)
        print("  命令 %d · 能力族 %d · 索引条目 %d · 菜单示例 %d · 动作 %d → %s"
              % (stats["commands"], stats["families"], stats["index_entries"],
                 stats["examples"], stats.get("actions", 0),
                 "通过" if not issues else "FAIL %d" % len(issues)))
        if args.deep:
            print("  活体：%s 退出码 %s · 历史落点 %s · 会话落点 %s"
                  % (stats.get("live_command", "-"), stats.get("live_code", "-"),
                     stats.get("历史落点", "-"), stats.get("会话落点", "-")))
            _failed = stats.get("help_sweep_failed") or []
            print("  全命令可调用：%d/%d（逐条 --help；失败：%s）"
                  % ((stats.get("help_sweep_total", 0) - len(_failed)),
                     stats.get("help_sweep_total", 0),
                     "、".join(_failed[:5]) if _failed else "无"))
            print("  环境：TTY %s · readline %s · 分页器 %s"
                  % ("是" if stats.get("tty") else "否",
                     "可用" if stats.get("readline") else "不可用",
                     stats.get("pager", "未探测")))
            for _ln in str(stats.get("live_output") or "").splitlines():
                print("  ── 活体输出：%s" % _ln)
        print("  补全：内建候选列表（/complete、行尾 Tab）+ %s"
              % ("readline 已接管" if term.readline_available()
                 else "readline 不可用（本平台无该模块，走零依赖回退）"))
        print("  历史：%s"
              % _portable_path(args.history or term.default_history_path()))
        return 0 if not issues else 1
    if args.complete_prefix:
        cands = term.complete(args.complete_prefix, index)
        print(term.render_completions(args.complete_prefix, cands))
        return 0 if cands else 2
    if args.script_file:
        # 形状闸门（2026-10-01）：`--file <目录>` 此前回 `[Errno 13] Permission denied: 'docs'`
        # 配「确认路径存在后重试」——对一个**确实存在**的目录说「不存在」，指引本身就错。
        _sf = args.script_file
        if not os.path.isfile(_sf):
            return _machine_fail(
                args, "脚本文件不是在场文件：%s（修复指引：`--file` 给**在场脚本文件**——每行一条 "
                      "nf 命令，`#` 注释与空行跳过；交互式逐条输入请用 `--exec \"a; b\"`）"
                      % _sf, 2)
        try:
            code, text, _records = _sw.run_file(args.script_file, runner, ROOT,
                                                 assume_yes=args.yes,
                                                 as_json=args.json, index=index)
        except OSError as exc:
            print("  ✗ 读不到脚本文件：%s（修复指引：确认路径存在后重试）" % exc,
                  file=sys.stderr)
            return 2
        print(text)
        return code
    if args.exec_script:
        code, text, _records = _sw.run_script(args.exec_script, runner, ROOT,
                                              assume_yes=args.yes,
                                              as_json=args.json, index=index)
        print(text)
        return code
    # 机器面防挂（2026-10-01）：`--json` 的帮助写明「配合 --exec」。若一路走到**交互兜底**还带着
    # `--json`，说明消费方期待 JSON，却会被送进交互会话——非 TTY（agent/CI/管道）下**永久阻塞**。
    # fail-closed 明确拒，并把可用的机读子模式列全。
    if args.json:
        return _machine_fail(
            args, "--json 需配合机读子模式（修复指引：`nf shell --exec \"<命令>\" --json`、"
                  "`--file <脚本> --json`、`--verify --json`、`--commands --json`、"
                  "`--map --json`、`--form [id] --json`、`--baseline --json`）；"
                  "裸 `nf shell` 是**交互终端**，非 TTY 下会阻塞，故不在此输出 JSON", 2)
    if term.install_readline(lambda text: [c["text"] for c in term.complete(text, index)],
                             history_path):
        pass                                  # readline 接管 Tab 与历史（POSIX）
    print_banner = not args.no_banner
    return _sw.run_session(runner, sys.stdin, sys.stdout, ROOT,
                           assume_yes=args.yes,
                            show_banner=print_banner,
                            baseline=_shell_baseline(), index=index,
                            history_path=history_path, color=color_on,
                            width=width or None, limit=limit,
                            color_mode=color_mode, session_path=args.session_path)


def _collect_cli_tree():
    """自省 argparse 命令面：命令 × 顶层 flags × 二级子命令（供 completion 生成）。"""
    global _TREE_CACHE
    if _TREE_CACHE is not None:
        return _TREE_CACHE
    root = _build_parser()

    def flags(parser):
        out = []
        for act in parser._actions:
            if isinstance(act, argparse._SubParsersAction):
                continue
            out += list(act.option_strings)
        return sorted(set(out))

    tree = {}
    for act in root._actions:
        if not isinstance(act, argparse._SubParsersAction):
            continue
        for name, sp in act.choices.items():
            nested = {}
            for act2 in sp._actions:
                if isinstance(act2, argparse._SubParsersAction):
                    for n2, sp2 in act2.choices.items():
                        nested[n2] = flags(sp2)
            tree[name] = {"flags": flags(sp), "nested": nested}
    _TREE_CACHE = {
        "commands": sorted(tree),
        "root_flags": flags(root),
        "tree": tree,
    }
    return _TREE_CACHE


def _cmd_completion(args):
    """nf completion <bash|zsh|fish>：从 argparse 命令面生成 shell 补全脚本。"""
    data = _collect_cli_tree()
    cmds = data["commands"]
    root_flags = data["root_flags"]
    tree = data["tree"]
    words = lambda xs: " ".join(xs)  # noqa: E731

    def var(cmd):
        return cmd.replace("-", "_")

    if args.shell == "bash":
        lines = [
            "# nf bash completion（自动生成 · 追加到 ~/.bashrc 后 source）",
            "_nf_cmds=\"%s\"" % words(cmds),
            "_nf_root_flags=\"%s\"" % words(root_flags),
        ]
        for c in cmds:
            lines.append("_nf_flags_%s=\"%s\"" % (var(c), words(tree[c]["flags"])))
            if tree[c]["nested"]:
                lines.append("_nf_nested_%s=\"%s\""
                             % (var(c), words(sorted(tree[c]["nested"]))))
        lines += [
            "_nf_completions(){",
            "  local cur cmd",
            "  cur=\"${COMP_WORDS[COMP_CWORD]}\"",
            "  if [ \"$COMP_CWORD\" -eq 1 ]; then",
            "    COMPREPLY=( $(compgen -W \"$_nf_cmds $_nf_root_flags\" -- \"$cur\") )",
            "    return",
            "  fi",
            "  cmd=\"${COMP_WORDS[1]}\"",
            "  case \"$cmd\" in",
        ]
        for c in cmds:
            if tree[c]["nested"]:
                lines.append(
                    "    %s) if [ \"$COMP_CWORD\" -eq 2 ]; then"
                    " eval nest=\"$_nf_nested_%s\";"
                    " COMPREPLY=( $(compgen -W \"$nest\" -- \"$cur\") ); return; fi ;;" % (c,
 var(c)))
        lines += [
            "  esac",
            "  eval fl=\"$_nf_flags_${cmd//-/_}\"; fl=\"${fl:-}\"",
            "  if [[ \"$cur\" == -* ]]; then COMPREPLY=( $(compgen -W \"$fl\" -- \"$cur\") ); retur"
                "n; fi",
            "  COMPREPLY=( $(compgen -W \"$fl\" -- \"$cur\") $(compgen -f -- \"$cur\") )",
            "}",
            "complete -F _nf_completions nf",
            "",
        ]
        print("\n".join(lines))
        return 0

    if args.shell == "zsh":
        all_flags = sorted(set(data["root_flags"]))
        for c in cmds:
            all_flags += tree[c]["flags"]
            for sub in tree[c]["nested"].values():
                all_flags += sub
        all_flags = sorted(set(all_flags))
        lines = [
            "#compdef nf",
            "# nf zsh completion（自动生成）",
            "_nf_cmds=(%s)" % " ".join(cmds),
            "_nf_all_flags=(%s)" % " ".join(all_flags),
            "_nf() {",
            "  local -a cmds",
            "  cmds=(%s)" % " ".join(cmds),
            "  if (( CURRENT == 2 )); then",
            "    _describe -t commands 'nf command' cmds",
            "  else",
            "    if [[ $PREFIX == -* ]]; then compadd -- $_nf_all_flags; else _files; fi",
            "  fi",
            "}",
            "compdef _nf nf",
            "",
        ]
        print("\n".join(lines))
        return 0

    # fish
    lines = [
        "# nf fish completion（自动生成 · nf completion fish | source）",
        "complete -c nf -f",
        "complete -c nf -n '__fish_use_subcommand' -a '%s'" % " ".join(cmds),
    ]
    for c in cmds:
        for f in tree[c]["flags"]:
            if f.startswith("--"):
                lines.append("complete -c nf -n '__fish_seen_subcommand_from %s' -l %s"
                             % (c, f[2:]))
            elif f.startswith("-") and len(f) == 2:
                lines.append("complete -c nf -n '__fish_seen_subcommand_from %s' -s %s"
                             % (c, f[1:]))
        for n2 in tree[c]["nested"]:
            lines.append("complete -c nf -n '__fish_seen_subcommand_from %s' -a '%s'"
                         % (c, n2))
            for f in tree[c]["nested"][n2]:
                cond = "__fish_seen_subcommand_from %s; and __fish_seen_subcommand_from %s" % (c,
 n2)
                if f.startswith("--"):
                    lines.append("complete -c nf -n '%s' -l %s" % (cond, f[2:]))
                elif f.startswith("-") and len(f) == 2:
                    lines.append("complete -c nf -n '%s' -s %s" % (cond, f[1:]))
    print("\n".join(lines))
    return 0










def _cmd_release(args):
    """nf release：发布前体检；--plan 出计划；--freeze [--apply] 按序走冻结链。"""
    from core import release_gate as rg

    if getattr(args, "plan", False):
        import json as _json
        if getattr(args, "json", False):
            print(_json.dumps({"schema": "nf-release-plan/1", "steps": rg.plan(ROOT)},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(rg.render_plan(ROOT))
        return 0
    if getattr(args, "freeze", False):
        return _release_freeze(args)
    if getattr(args, "json", False) and not getattr(args, "fast", False):
        # 机读发布面：确定性摘要（计划 + 前置 + golden 快照），供 CI/发布人留档；只读、不跑 verify。
        import json as _json
        man = rg.manifest(ROOT)
        print(_json.dumps(man, ensure_ascii=False, indent=2, sort_keys=True))
        return 1 if man["issues"] else 0
    import subprocess  # nosec B404/B603/B607 —— 调用 ssh-keygen/git/hf（argv 列表、无 shell、路径经 which 解析）
    from core import posix_shell as psh
    from core import quality_baseline as qb

    issues, stats = qb.scan(ROOT)
    print("== nf release check（发布前体检）==")
    print("  verify 版本 %s · check 数 %d（基线自描述一致：%s）"
          % (stats["verify_version"], stats["checks"],
             "OK" if not issues else "FAIL"))
    for i in issues:
        print("  [FAIL] %s" % i, file=sys.stderr)
    if args.fast:
        print("  --fast：跳过 verify.sh 全量（发布前请跑完整 nf release）")
        return 1 if issues else 0
    # P3（2026-10-18）：发布前必须走 **full 档**（默认档是 quick：静态 + 受影响测试，
    # 只给开发回路用）；--no-cache 保证发布体检是**真跑**而不是回放旧判定。
    argv = [psh.posix_shell(), "verify.sh", "--full", "--no-cache"]  # nosec B404/B603/B607
    rc = subprocess.run(argv, cwd=ROOT).returncode
    gate_fail = bool(issues) or rc != 0
    if not gate_fail:
        from core import asset_ledger_projection as alp
        from core import instruction_step_audit as isa
        from core import payload_registry as pr
        for name, fn in (("资产 ledger", alp.verify),
                         ("指令审计", isa.scan),
                         ("载荷注册表", pr.scan)):
            f_issues, _ = fn(ROOT)
            if f_issues:
                gate_fail = True
                print("  [FAIL] %s：%s" % (name, "；".join(f_issues[:3])),
                      file=sys.stderr)
            else:
                print("  ✓ %s 一致" % name)
        cov = subprocess.run([psh.posix_shell(), "scripts/per_module_coverage.sh", "30"],  # nosec B404/B603/B607 —— 调用 ssh-keygen/git/hf（argv 列表、无 shell、路径经 which 解析）
                             cwd=ROOT).returncode
        if cov != 0:
            gate_fail = True
            print("  [FAIL] 逐模块覆盖率 < min30", file=sys.stderr)
        else:
            print("  ✓ 逐模块覆盖率 ≥ min30")
        # 静态检查（软依赖）：lint 此前只在 GitHub CI 跑，本地 pre-push（本命令）不含它，
        # 于是「未定义名」一类硬错会在本地积压、只在推送后才红（实测：core/disk_cache.py
        # 曾带 4 处 F821 进树）。这里按仓库软依赖纪律接入：ruff 不在场就跳过并明示，
        # 在场则以**仓库 ruff.toml 同口径**判死。
        lint = subprocess.run([sys.executable, "-m", "ruff", "check",
                               "desktop/src", "scripts"], cwd=ROOT,
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
        lint_out = (lint.stdout or "") + (lint.stderr or "")
        if lint.returncode == 127 or "No module named" in lint_out:
            print("  [WARN] 缺 ruff（跳过静态检查；修复指引：pip install ruff）")
        elif lint.returncode != 0:
            gate_fail = True
            print("  [FAIL] ruff 静态检查未过（修复指引：python -m ruff check desktop/src scripts）",
                  file=sys.stderr)
        else:
            print("  ✓ ruff 静态检查零告警（仓库 ruff.toml 口径）")
        # 端到端（动态可执行面）：发布前体检必须覆盖「真链路跑通」，不能只看静态门禁。
        # 此前 e2e 只在 e2e-desktop.yml 独立跑，release-gate 不含它——发布前的绿灯
        # 因此不保证端到端可用（顶层化目标：e2e 纳入 release-gate）。
        e2e = subprocess.run([sys.executable, os.path.join("scripts", "e2e_desktop_headless.py")],
                             cwd=ROOT)
        if e2e.returncode != 0:
            gate_fail = True
            print("  [FAIL] 端到端冒烟未过（修复指引：python scripts/e2e_desktop_headless.py）",
                  file=sys.stderr)
        else:
            print("  ✓ 端到端冒烟通过（官方 13 件 + M91/M92 + P04 → 装配 → 生成 → 断言）")
        # 机器可读报告新鲜度（静态可核验面）：已提交的 protocol/verification_report.json
        # 必须等于实时重算——否则门禁的「机器面结论」是过期的。
        vrpt = subprocess.run([sys.executable,
 os.path.join("scripts",
 "verify_report.py"),
 "--fresh"],
                              cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                              errors="replace")
        if vrpt.returncode != 0:
            gate_fail = True
            tail = [l for l in ((vrpt.stderr or "") + (vrpt.stdout or "")).splitlines() if l.strip()][-2:]
            print("  [FAIL] 门禁机器可读报告过期或判据未过（修复指引：python scripts/verify_report."
                "py "
                  "--write）%s" % ("；" + " / ".join(tail) if tail else ""), file=sys.stderr)
        else:
            print("  ✓ 门禁机器可读报告新鲜（protocol/verification_report.json == 实时重算）")
    if gate_fail:
        print("  ✗ 发布体检未过（基线/verify）——禁止发布", file=sys.stderr)
        return 1
    print("  ✓ 发布体检通过：verify 全绿 + 基线自描述一致（可打 tag）")
    return 0












def _cmd_worldmodel(args):
    """nf worldmodel：浏览确定性抽象状态契约（machine_contract.world_model）。"""
    import json as _json
    from pathlib import Path

    from core import conformance_scan as csc
    from core import world_model as wm

    concrete = None
    if getattr(args, "state_path", None):
        # 形状 + 格式闸门（2026-10-01）：此前直接读盘 → 缺件时抛裸
        # `[Errno 2] No such file or directory: 'state.json'` 冒成「内部错误 + 机器路径」
        # （文档示例 `nf worldmodel --run --state state.json` 真跑即复现）。
        # 口径统一（2026-10-01）：相对路径按**仓库根**（与 `_rel_out` / `_rel_to_root` 同；此前
        # 直接 `Path(args.state_path)` ⇒ 按进程 cwd，而本命令的错误消息自己写着「相对仓库根或
        # 绝对皆可」——**消息与行为不一致**，从仓外 cwd 跑必然误判「状态件不存在」）。
        sp = Path(_rel_out(args.state_path))
        if not sp.is_file():
            return _machine_fail(
                args, "状态件不存在：%s（修复指引：`--state` 给**在场**具体状态 JSON 文件"
                      "（相对仓库根或绝对皆可）；只想看抽象状态契约就跑 `nf worldmodel --walk`，"
                      "不带 `--state` 即按契约内建初值重放）" % args.state_path, 1)
        try:
            concrete = _json.loads(sp.read_text(encoding="utf-8"))
        except ValueError as exc:
            return _machine_fail(
                args, "状态件不是合法 JSON：%s（修复指引：`--state` 收状态 JSON 对象，"
                      "键名须与该模型契约的 world_slots 对应；对照 `nf worldmodel --walk`）"
                      % exc, 1)

    def _load(model):
        text = Path(ROOT, model["source"]).read_text(encoding="utf-8")
        parsed = csc._fence_yaml(text, "machine_contract")
        return parsed.get("machine_contract", {}).get("world_model")

    def _run_one(model):
        contract = _load(model)
        if not isinstance(contract, dict):
            return None
        runtime = wm.WorldModelRuntime(contract)
        return runtime.replay_concrete(concrete) if concrete is not None else runtime.replay()

    issues, stats = wm.scan(ROOT)
    if args.json and args.run:
        runs = []
        for m in stats["models"]:
            result = _run_one(m)
            if result is not None:
                runs.append({
                    "module": m["module"],
                    "source": m["source"],
                    "result": result,
                })
        print(_json.dumps({"kind": "worldmodel-run", "issues": issues, "runs": runs},
                          ensure_ascii=False, indent=2, sort_keys=True))
    elif args.json:
        print(_json.dumps({"kind": "worldmodel", "issues": issues, "stats": stats},
                          ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print("== nf worldmodel（JEPA-inspired 确定性抽象状态契约 · check32 硬门）==")
        print("  模块 %d · 变量 %d · 相位 %d · 不变式 %d · checks %d · slots %d/%d"
              % (stats["modules"], stats["variables"],
                 stats["phases"], stats["invariants"],
                 stats.get("checks", 0), stats.get("slots", 0),
                 stats.get("slot_registry", 0)))
        for m in stats["models"]:
            print("  · %s（%s · initial=%s · %d phases · %d invariants · %d checks）"
                  % (m["module"], m["source"], m["initial_phase"],
                     m["phases"], m["invariants"], m.get("checks", 0)))
        if args.walk:
            for m in stats["models"]:
                contract = _load(m)
                if not isinstance(contract, dict):
                    continue
                seq, reason, repeat = wm.phase_sequence(contract)
                print("  → %s 重放：%s（终止=%s%s）"
                      % (m["module"], " → ".join(seq), reason,
                         " · 重复=" + str(repeat) if repeat else ""))
        if args.run:
            for m in stats["models"]:
                result = _run_one(m)
                if result is None:
                    continue
                print("  → %s 运行：%d steps（%s%s · digest=%s）"
                      % (m["module"], len(result["steps"]), result["reason"],
                         " · 重复=" + str(result["repeat"]) if result["repeat"] else "",
                         result.get("digest", "")[:12]))
                for step in result["steps"]:
                    print("    %d. %s → %s（guard=%s）"
                          % (step["step"], step["phase_from"], step["phase_to"],
                             step["guard"]))
        for i in issues:
            print("  [FAIL] %s" % i, file=sys.stderr)
    return 1 if issues else 0


def _cmd_verify(args) -> int:
    """nf verify：门禁单进程引擎入口（已迁入的 check 与 verify.sh 判据逐字等价）。

    **纪律**：本命令不重写任何判据——执行体是 `core.gate_engine`，它对已迁入的 check
    要么委托既有 `core.*`，要么在进程内跑 verify.sh 的 heredoc 原文；未迁入的如实报
    「未迁入」，**不假装绿**。全量门禁的权威入口仍是 `bash verify.sh`。
    """
    import json as _json
    import os as _os

    from core import gate_engine as ge
    from core import repo_trust as _rt

    # H1（2026-10-22 安全审计）：nf verify 的 inproc/script 面会把目标仓库 verify.sh 的
    # heredoc Python 当本机进程代码执行（CWE-94）。信任门在**执行之前**判：不可信仓库
    # （外部仓库默认不可信，伪造 origin 也不放行），需显式 --trust-repo 自担风险。
    if getattr(args, "trust_repo", False):
        print("WARN: --trust-repo 已启用：将执行目标仓库自带的门禁脚本（含内嵌 Python，"
              "CWE-94 面），风险自担", file=sys.stderr)
    _trusted, _why = ((True, "显式 --trust-repo") if getattr(args, "trust_repo", False)
                      else _rt.trust_status(str(ge.ROOT)))
    if not _trusted:
        _msg = _rt.refusal_message(str(ge.ROOT), _why)
        if args.json:
            print(_json.dumps({"kind": "nf-verify", "schema": "nf-verify/1", "ok": False,
                               "fails": 1, "checks": [], "pending": [], "complete": False,
                               "gate_of_record": "bash verify.sh",
                               "error": {"code": "untrusted_repo", "message": _why}},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("== nf verify（门禁单进程引擎 · 已因信任门拒绝执行）==")
        print(_msg, file=sys.stderr)
        return 2

    ge.build_registry()
    only = [int(x) for x in str(args.only).split(",") if x.strip()] if args.only else None
    if only:
        unknown = sorted(set(only) - set(ge.REGISTRY))
        if unknown:
            return _machine_fail(
                args,
                "check %s 尚未迁入引擎（现已迁入：%s）——请用 `bash verify.sh` 跑全量"
                % (",".join(str(u) for u in unknown),
                   ",".join(str(n) for n in sorted(ge.REGISTRY))), 2)

    # 确定性输出：耗时是**不确定性面**，默认不进输出。
    # 实测教训（test_daemon_parity）：直跑与守护的耗时必然不同，带上它两边就不逐字节一致。
    # 故本命令**自己**把开关置上（而不是依赖守护侧注入）——直跑与守护走同一条代码路径，
    # 判据只有一个，避免「两条路径各自设一次」再漂移（实测踩过：只设守护侧 ⇒ 仍差 28 字节）。
    _os.environ["NF_VERIFY_QUIET_TIME"] = "1"
    memo = ge.Memo() if args.memo else None
    _jobs = int(getattr(args, "jobs", 0) or 0)
    if _jobs > 1 and not only:
        # **并行**：每条 check 在独立子进程里跑 `nf verify --only N --json`（判据一字不改），
        # 再按 check 号排序合并。逐字节一致的守门判据见 `test_verify_parallel_checks`。
        from core import verify_checks as _vc
        nums = sorted(ge.REGISTRY)
        _saved_trust = _os.environ.get(_rt.ENV_TRUST)
        if getattr(args, "trust_repo", False):
            _os.environ[_rt.ENV_TRUST] = "1"
        try:
            payloads, broken = _vc.run_checks_parallel(ge.ROOT, nums, jobs=_jobs)
        finally:
            if _saved_trust is None:
                _os.environ.pop(_rt.ENV_TRUST, None)
            else:
                _os.environ[_rt.ENV_TRUST] = _saved_trust
        if broken:
            print("并行子 check 不可信：%s（修复指引：去掉 --jobs 用串行复现）"
                  % ",".join(str(b) for b in broken), file=sys.stderr)
            return 2
        fails = sum(1 for c in payloads
                    for s in (c.get("verdicts") or []) if s == "FAIL")
        pending = sorted(ge.PENDING)
        if args.json:
            print(_json.dumps({
                "kind": "nf-verify", "schema": "nf-verify/1",
                "ok": fails == 0, "fails": fails, "checks": payloads,
                "pending": [int(n) for n in pending],
                "complete": not pending, "gate_of_record": "bash verify.sh",
            }, ensure_ascii=False, indent=2, sort_keys=True))
            return 1 if fails else 0
        print("== nf verify（门禁单进程引擎 · 判据与 verify.sh 逐字等价）==")
        for c in payloads:
            for status, msg in zip(c.get("verdicts") or [], c.get("messages") or []):
                print("  [%s] %s" % (status, msg))
        print("  已迁入 %d 条 · FAIL %d" % (len(payloads), fails))
        if pending:
            print("  ⚠ 未迁入 %d 条（仍在 verify.sh 里，**未在本次结论内**）：%s"
                  % (len(pending), " ".join(str(n) for n in pending)))
            print("  ⚠ 本条结论**不等于全量门禁**——全量请跑：bash verify.sh")
        return 1 if fails else 0
    _saved_trust = _os.environ.get(_rt.ENV_TRUST)
    if getattr(args, "trust_repo", False):
        _os.environ[_rt.ENV_TRUST] = "1"
    try:
        verdicts = ge.run_checks(
            ge.ROOT, only, memo, use_cache=bool(getattr(args, "cached", False)))
    finally:
        if _saved_trust is None:
            _os.environ.pop(_rt.ENV_TRUST, None)
        else:
            _os.environ[_rt.ENV_TRUST] = _saved_trust

    fails = sum(v.fails for v in verdicts)
    pending = sorted(set(ge.PENDING) - (set(only) if only else set()))

    # 退出码**只看 FAIL**，与门禁（`verify.sh` 只按 FAIL 判死）同口径。
    # 「未迁入」是**覆盖面**问题，不是判据失败——把它算进退出码会有两个坏后果：
    #   ① 语义错位：引擎会把「还有 19 条没搬进来」报成「门禁红」；
    #   ② 实测连带故障：响应缓存只收退出码 0 的响应 ⇒ `nf verify` 永远不入缓存
    #      （实测 5 miss / 0 hit，热跑仍是 72 s）。
    # 故未迁入只在人读面**大声声明**（并在机器面给 pending 列表），不动退出码。

    if args.json:
        print(_json.dumps({
            "kind": "nf-verify",
            "schema": "nf-verify/1",
            "ok": fails == 0,
            "fails": fails,
            "checks": [{"check": int(v.name.replace("check", "")), "status": v.status,
                        "verdicts": [s for s, _ in v.verdicts],
                        # `messages` 让机器面**自足**：并行子进程跑 `--only N --json` 之后，
                        # 人读面能按同一批数据重放出**逐字相同**的文案（否则并行态只剩
                        # PASS/FAIL，文案无处可取）。顺序与 `verdicts` 一一对应。
                        "messages": [m for _, m in v.verdicts]}
                       for v in verdicts],
            "pending": [int(n) for n in pending],
            "complete": not pending,
            "gate_of_record": "bash verify.sh",
        }, ensure_ascii=False, indent=2, sort_keys=True))
        return 1 if fails else 0

    print("== nf verify（门禁单进程引擎 · 判据与 verify.sh 逐字等价）==")
    for v in verdicts:
        for status, msg in v.verdicts:
            print("  [%s] %s" % (status, msg))
    print("  已迁入 %d 条 · FAIL %d" % (len(verdicts), fails))
    if pending:
        print("  ⚠ 未迁入 %d 条（仍在 verify.sh 里，**未在本次结论内**）：%s"
              % (len(pending), " ".join(str(n) for n in pending)))
        print("  ⚠ 本条结论**不等于全量门禁**——全量请跑：bash verify.sh")
    return 1 if fails else 0


def _cmd_daemon(args) -> int:
    """nf daemon：执行层常驻守护（毫秒级响应）。

    动机（实测）：裸解释器启动 146 ms、`nf --version` 401 ms——每条命令有 ~400 ms 固定成本；
    热进程内同一命令只要 1–5 ms。故把命令执行搬进常驻进程，客户端只做一次往返。
    """
    import json as _json
    import time as _time
    from pathlib import Path
    from core import daemon as dm

    sub = args.daemon_cmd
    if sub == "start":
        ok, msg = dm.start(Path(ROOT), idle_timeout=args.idle,
                           watch=bool(getattr(args, "watch", False)))
        doc = dm.read_state() or {}
        print(("  ✓ " if ok else "  ✗ ") + msg)
        if ok:
            # 缓存/监听是**守护进程内**的状态，必须在守护侧取（客户端进程里看不到）。
            st = dm.query_stats(doc)
            if st is None:
                print("  响应缓存：无法查询（守护未响应 stats）")
            elif st.get("enabled"):
                print("  响应缓存：已启用（树没变即整条复用；代际 %s）" % st.get("generation"))
            else:
                print("  响应缓存：未启用（目录监听不可用——平台未实现或打开失败，已自动降级）")
        if ok:
            print("  端口 %s · 状态文件 %s"
                  % (doc.get("port"), _portable_path(dm.state_path())))
        return 0 if ok else 1
    if sub == "stop":
        ok, msg = dm.stop()
        print(("  ✓ " if ok else "  · ") + msg)
        return 0 if ok else 1
    if sub == "status":
        t0 = _time.perf_counter()
        alive = dm.ping()
        rtt = (_time.perf_counter() - t0) * 1000
        doc = dm.read_state() or {}
        if args.json:
            print(_json.dumps({"kind": "nf-daemon", "running": bool(alive),
                               "port": doc.get("port"), "pid": doc.get("pid"),
                               "proto": doc.get("proto"),
                               "root": _portable_path(doc.get("root")),
                               "rtt_ms": round(rtt, 2) if alive else None,
                               "cache": dm.query_stats(doc) if alive else None,
                               "state_file": _portable_path(dm.state_path())},
                              ensure_ascii=False, indent=2, sort_keys=True))
            return 0 if alive else 1
        print("== nf daemon（执行层常驻守护）==")
        print("  状态：%s" % ("在线" if alive else "未运行"))
        if doc:
            print("  端口 %s · pid %s · proto %s" % (doc.get("port"), doc.get("pid"),
                                                     doc.get("proto")))
            print("  仓库根：%s" % _portable_path(doc.get("root")))
        print("  状态文件：%s" % _portable_path(dm.state_path()))
        if alive:
            print("  往返时延：%.1f ms（同一进程内热跑；含协议解析与源码指纹比对）" % rtt)
            st = dm.query_stats(doc)
            if st is None:
                print("  响应缓存：无法查询（守护未响应 stats）")
            elif st["enabled"]:
                print("  响应缓存：已启用 · 代际 %s · 条目 %d · 命中 %d / 未命中 %d（树一变即整批作"
                    "废）"
                      % (st["generation"], st["entries"], st["hits"], st["misses"]))
            else:
                print("  响应缓存：未启用（未开 --watch，或目录监听不可用——行为与常规守护一致）")
        else:
            print("  → 拉起：nf daemon start（或用 scripts/nf 启动器，它会自动走守护）")
        return 0 if alive else 1
    if sub == "exec":
        argv = [str(a) for a in (args.argv or [])]
        if argv and argv[0] == "--":
            argv = argv[1:]
        if not argv:
            print("  ✗ 缺命令（用法：nf daemon exec stats --check）", file=sys.stderr)
            return 2
        doc = dm.read_state()
        if not (doc and dm.ping(doc)):
            if getattr(args, "no_start", False):
                print("  ✗ 守护不在运行（--no-start）", file=sys.stderr)
                return 1
            ok, msg = dm.start(Path(ROOT))
            if not ok:
                print("  ✗ " + msg, file=sys.stderr)
                return 1
            doc = dm.read_state()
        try:
            code, out, err = dm.run_request(doc, argv)
        except OSError as exc:
            return _machine_fail(
                args, "守护未响应：%s（修复指引：nf daemon start 后重试）" % exc, 1)
        sys.stdout.write(out.decode("utf-8", "replace"))
        sys.stderr.write(err.decode("utf-8", "replace"))
        return code
    if sub == "shell-init":
        # 零子进程客户端：当前 shell 内一次函数调用 + 一次套接字往返（真毫秒级）。
        # `--shell` 与位置参数是同一件事的两种拼法；**此前两者都没被读**（`--shell` 声明了
        # 却没人用 = 传了也没用的静默空转，2026-10-01 判据扫描抓到）——现统一读一处，
        # 声明面与执行面同源；目前只支持 bash（choices 已限，后端也只有 BASH 变体）。
        shell = str(getattr(args, "shell_opt", None) or getattr(args, "shell", None) or "bash")
        if shell != "bash":
            return _machine_fail(
                args, "--shell 目前只支持 bash（修复指引：`eval \"$(nf daemon shell-init "
                      "bash)\"`；其它 shell 需先落对应启动脚本后端）", 2)
        print(dm.SHELL_INIT_BASH.replace("{py}", sys.executable).replace("{root}", ROOT),
              end="")
        return 0
    if sub == "bench":
        import subprocess as _sp
        probes = (["--version"], ["stats", "--check"], ["layers", "--verify"], ["doctor"])
        doc = dm.read_state()
        if not (doc and dm.ping(doc)):
            ok, msg = dm.start(Path(ROOT))
            if not ok:
                return _machine_fail(args, msg, 1)
            doc = dm.read_state()
        if not (doc and dm.ping(doc)):
            # 守护拉起后仍不可达：机器面须是失败信封，不许冒内部错误（2026-10-10 CI 实测：
            # 无守护时 daemon bench --json 会抛 WinError 10061 连接被拒，stdout 非 JSON）。
            return _machine_fail(
                args, "守护未就绪（已尝试拉起但不可达）（修复指引：先 nf daemon stop 清掉"
                      "陈旧状态后重试，或稍后重跑）", 1)
        rows: List[Dict[str, Any]] = []
        for argv in probes:
            cold = []
            for _ in range(max(1, args.runs)):
                t0 = _time.perf_counter()
                _sp.run([sys.executable, os.path.join(ROOT, "scripts", "nf.py")] + argv,
                        cwd=ROOT, stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
                cold.append((_time.perf_counter() - t0) * 1000)
            warm = []
            for _ in range(max(1, args.runs)):
                t0 = _time.perf_counter()
                try:
                    dm.run_request(doc, argv)
                except OSError as exc:
                    return _machine_fail(
                        args, "守护未响应（%s）：%s（修复指引：nf daemon start 后重试）"
                              % (" ".join(argv), exc), 1)
                warm.append((_time.perf_counter() - t0) * 1000)
            rows.append({"argv": argv, "cold_ms": round(min(cold), 1),
                         "daemon_ms": round(min(warm), 1),
                         "speedup": round(min(cold) / max(min(warm), 0.001), 1)})
        if args.json:
            print(_json.dumps({"kind": "nf-daemon-bench", "runs": max(1, args.runs),
                               "probes": rows}, ensure_ascii=False, indent=2, sort_keys=True))
            return 0
        print("== nf daemon bench（直跑 vs 守护，取 %d 次最小）==" % max(1, args.runs))
        print("  %-22s %10s %10s %8s" % ("命令", "直跑 ms", "守护 ms", "加速"))
        for r in rows:
            print("  %-22s %10.1f %10.1f %7.1fx"
                  % (" ".join(r["argv"]), r["cold_ms"], r["daemon_ms"], r["speedup"]))
        return 0
    print("  ✗ 未知 daemon 子命令：%s" % sub, file=sys.stderr)
    return 2






def _cmd_nfal(args) -> int:
    """nf nfal：透传到 core.nfal_cli（guard 表达式的解析/检查/编译/求值）。"""
    from core import nfal_cli
    return nfal_cli.main(list(getattr(args, "nfal_args", []) or []))


def _rust_engine_argv(args) -> Optional[list]:
    """**已实测为净收益**的面才映射成 nf-rs argv；其余返回 None（走 Python 真源）。

    热进程内对照（2026-10-22，同机同语料，median of 6）：
      - layers 626ms → 229ms（2.73×）→ 接管；
      - stats 11.5ms → 49ms（0.23×）/ receipts 18ms → 30ms（0.60×）/
        conformance 2.0s → 3.2s（0.63×）/ purity 0.73× / schema 0.94× / depth 0.04×
        → **不接管**（Rust 快线仍可由 nf-rs 直接调用，但不得拖慢默认热路径）。
    写面（--write）与人类可读面永远留在 Python 真源。
    """
    if args.cmd == "layers":
        if (getattr(args, "write", False) or not getattr(args, "verify", False)
                or not getattr(args, "json", False)):
            return None
        return ["layers", "--root", ROOT, "--verify", "--json"]
    return None


def _try_rust_face(args) -> Optional[int]:
    """opt-in 只读快线：--engine rust|auto 时把已对账的 JSON 读面交给 nf-rs，失败回退 Python。

    返回 None = 未接管（调用方继续走 Python 真源）；返回 int = 已接管（作为 main 的退出码）。
    只读纪律：只加速 exit==0 且字节已对账的面；快线退出非零（有 issue/异常）时回退 Python
    以保留完整诊断面——绝不静默丢掉诊断。
    """
    engine = str(getattr(args, "engine", None) or os.environ.get("NF_ENGINE", "") or "").strip().lower()
    if engine not in ("rust", "auto"):
        return None
    argv = _rust_engine_argv(args)
    if argv is None:
        return None
    from core import rust_engine as re
    if re.disabled():
        return None
    res = re.run_face(argv, root=ROOT)
    if res is None:
        if engine == "rust":
            print("  [WARN] NF_ENGINE=rust 但 nf-rs 不可用（回退 Python 真源）", file=sys.stderr)
        return None
    code, out = res
    if code != 0:
        if engine == "rust":
            print("  [WARN] nf-rs 退出 %d（回退 Python 真源保留诊断面）" % code, file=sys.stderr)
        return None
    sys.stdout.buffer.write(out)
    sys.stdout.buffer.flush()
    return 0










def main(argv=None) -> int:
    # 效率：`--version` 是最常被调用的探测命令，而构建 argparse 面 ≈100 ms——
    # 它不需要命令面，直接短路（输出与 argparse 的 version 动作逐字一致）。
    if argv is not None and list(argv) == ["--version"]:
        print("nf %s" % NF_CLI_VERSION)
        return 0
    args = _build_parser().parse_args(argv)
    if args.cmd is None:
        _build_parser().print_help()
        return 0
    # `--root` 落点闸门（2026-09-30）：读类命令的 `--root` 语义是「对**另一棵树**做同一套
    # 体检」。落点不在场 / 是文件时，此前照样吐**肯定结论**（实测：`nf asset verify --root
    # README.md` → 「✓ 台账闭合」、`nf module verify --root <不存在>` → 「✓ 引用门禁全绿」）——
    # 对**没有载体**的树下结论是错的事实（同 `drill_fidelity`「标准不得无载体」）。
    _root_arg = str(getattr(args, "root", "") or "")
    if _root_arg and _root_pair(args) in _ROOT_READERS:
        _rp = _root_arg if os.path.isabs(_root_arg) else os.path.join(ROOT, _root_arg)
        if not os.path.isdir(_rp):
            return _machine_fail(
                args, "--root 落点不是在场目录：%s（修复指引：`--root` 给**在场目录**"
                      "（相对仓库根或绝对皆可）——本命令按它扫树，落点不在场或为文件时"
                      "没有载体可体检；只想跑本仓库就别传 `--root`，空树体检请先建空目录）"
                      % _root_arg, 2)
    # 同族形状闸门（2026-09-30）：`--registry` / `--key-file` 是**输入文件**，落点不在场
    # 或是目录时，此前照样一路走到读盘 ⇒ 冒成「内部错误 + Errno」（实测 who-refers /
    # impact / library verify / attest 等 7 处）。集中判一次，覆盖全部声明点。
    _key_issue = _file_shape_issue(
        getattr(args, "key_file", ""), "--key-file",
        "修复指引：给 HMAC 密钥**文件**路径（`~` 会展开到家目录；不给就按 digest_only 级走）")
    if _key_issue:
        return _machine_fail(args, _key_issue, 1)
    # `--registry` 有 7 个声明点（market / spec / register / who-refers / impact / related /
    # release）：在**入口**判一次「在场 + 是文件 + 是合法 JSON」，覆盖全部声明点——此前
    # 目录落点报「内部错误 + Errno」，非 JSON 件报「内部错误：Expecting value…」（零指引）。
    _reg_arg = getattr(args, "registry", None)
    _reg_guide = ("修复指引：给 registry.json 的**文件**路径（缺省 = "
                  "desktop/src/core/registry.json；`nf doctor` 可体检）")
    if _reg_arg:
        _reg_issue = _file_shape_issue(_reg_arg, "--registry", _reg_guide)
        if _reg_issue:
            return _machine_fail(args, _reg_issue, 1)
        _reg_path = next((c for c in (_reg_arg, os.path.join(ROOT, _reg_arg))
                          if os.path.isfile(c)), "")
        try:
            import json as _json_probe
            with open(_reg_path, encoding="utf-8") as _fh:
                _json_probe.loads(_fh.read())
        except (OSError, ValueError) as exc:
            return _machine_fail(args, "--registry 不是合法 JSON：%s（%s）"
                                 % (exc, _reg_guide), 1)
    # 收路径旗标的**写法闸门**（2026-10-01）：相对路径的语义是「相对**仓库根**」，而 `..` 写法
    # 会让它静默逃出仓库（实测 `nf interop --kind openapi --out ../x.json` 写到了仓外，且报成
    # 「内部错误」）。口径与 `core.paths.validate_path` 同源：相对写法拒 `..` / 盘符，
    # **绝对路径按原样**（落地到 CI 产物目录、临时导出是设计面，写清楚即可）。
    _escape = _path_writing_issue(args)
    if _escape:
        return _machine_fail(args, _escape, 1)
    # 输入件编码闸门（2026-10-01）：非 UTF-8 文本件此前在 5 条命令上冒「内部错误」或裸解码错。
    _coding = _utf8_text_issue(args)
    if _coding:
        return _machine_fail(args, _coding, 2)
    _rust_rc = _try_rust_face(args)
    if _rust_rc is not None:
        return _rust_rc
    if args.cmd == "agent":
        return _cmd_agent(args)
    if args.cmd == "cli":
        return _cmd_cli(args)
    if args.cmd in ("shell", "terminal"):
        return _cmd_shell(args)
    if args.cmd == "layers":
        return _cmd_layers(args)
    if args.cmd == "verify":
        return _cmd_verify(args)
    if args.cmd == "daemon":
        return _cmd_daemon(args)
    if args.cmd == "help":
        return _cmd_help(args)
    if args.cmd == "stats":
        return _cmd_stats(args)
    if args.cmd == "facts":
        return _cmd_facts(args)
    if args.cmd == "doctor":
        return _cmd_doctor(args)
    if args.cmd == "completion":
        return _cmd_completion(args)
    if args.cmd == "assemble":
        return _cmd_assemble(args)
    if args.cmd == "preset":
        return _cmd_preset(args)
    if args.cmd == "release":
        return _cmd_release(args)
    if args.cmd == "changelog":
        return _cmd_changelog(args)
    if args.cmd == "locales":
        return _cmd_locales(args)
    if args.cmd == "toolface":
        return _cmd_toolface(args)
    if args.cmd == "worldmodel":
        return _cmd_worldmodel(args)
    if args.cmd == "register":
        return _cmd_register(args)
    if args.cmd == "registry":
        return _cmd_registry(args)
    if args.cmd == "asset":
        return _cmd_asset(args)
    if args.cmd == "pipeline":
        return _cmd_pipeline(args)
    if args.cmd == "module":
        return _cmd_module(args)
    if args.cmd == "sig":
        return _cmd_sig(args)
    if args.cmd == "attest":
        return _cmd_attest(args)
    if args.cmd == "score":
        return _cmd_score(args)
    if args.cmd == "lint":
        return _cmd_lint(args)
    if args.cmd == "lsp":
        return _cmd_lsp(args)
    if args.cmd == "license":
        return _cmd_license(args)
    if args.cmd == "telemetry":
        return _cmd_telemetry(args)
    if args.cmd == "library":
        return _cmd_library(args)
    if args.cmd == "conformance":
        return _cmd_conformance(args)
    if args.cmd == "glossary":
        return _cmd_glossary(args)
    if args.cmd == "approve":
        return _cmd_approve(args)
    if args.cmd == "events":
        return _cmd_events(args)
    if args.cmd == "receipts":
        return _cmd_receipts(args)
    if args.cmd == "driver":
        return _cmd_driver(args)
    if args.cmd == "rfc":
        return _cmd_rfc(args)
    if args.cmd == "patterns":
        return _cmd_patterns(args)
    if args.cmd == "bench":
        return _cmd_bench(args)
    if args.cmd == "runtime":
        return _cmd_runtime(args)
    if args.cmd == "endpoint":
        return _cmd_endpoint(args)
    if args.cmd == "interop":
        return _cmd_interop(args)
    if args.cmd == "transparency":
        return _cmd_transparency(args)
    if args.cmd == "output":
        return _cmd_output(args)
    if args.cmd == "security":
        return _cmd_security(args)
    if args.cmd == "ops":
        return _cmd_ops(args)
    if args.cmd == "privacy":
        return _cmd_privacy(args)
    if args.cmd == "domain":
        return _cmd_domain(args)
    if args.cmd == "combine":
        return _cmd_combine(args)
    if args.cmd == "decide":
        return _cmd_decide(args)
    if args.cmd == "workloop":
        return _cmd_workloop(args)
    if args.cmd == "review":
        return _cmd_review(args)
    if args.cmd == "knowledge":
        return _cmd_knowledge(args)
    if args.cmd == "assertions":
        return _cmd_assertions(args)
    if args.cmd == "model":
        return _cmd_model(args)
    if args.cmd == "decisions":
        return _cmd_decisions(args)
    if args.cmd == "handover":
        return _cmd_handover(args)
    if args.cmd == "postmortem":
        return _cmd_postmortem(args)
    if args.cmd == "audit":
        return _cmd_audit(args)
    if args.cmd == "cognition":
        return _cmd_cognition(args)
    if args.cmd == "st-validate":
        return _cmd_st_validate(args)
    if args.cmd == "state-front":
        return _cmd_state_front(args)
    if args.cmd == "ir":
        return _cmd_ir(args)
    if args.cmd == "diff":
        return _cmd_diff(args)
    if args.cmd == "related":
        return _cmd_related(args)
    if args.cmd == "explain":
        return _cmd_explain(args)
    if args.cmd == "demo":
        return _cmd_demo(args)
    if args.cmd == "market":
        return _cmd_market(args)
    if args.cmd == "who-refers":
        return _cmd_who_refers(args)
    if args.cmd == "impact":
        return _cmd_impact(args)
    if args.cmd == "rename":
        return _cmd_rename(args)
    if args.cmd == "import":
        return _cmd_import(args)
    if args.cmd == "spec":
        return _cmd_spec(args)
    if args.cmd == "render":
        return _cmd_render(args)
    if args.cmd == "serve":
        return _cmd_serve(args)
    if args.cmd == "design":
        if args.design_cmd == "audit":
            # 注意：这里必须指向 **design audit** 实现（1226 段）——此前与 `nf audit`
            # 的同名函数冲突（flake8 F811），`nf design audit ls` 实际打到 nf audit 那套
            # （实测输出「== nf audit（26 件）==」），已重命名为 _cmd_design_audit 修正。
            return _cmd_design_audit(args)
        return _cmd_design(args)
    if args.cmd == "nfal":
        return _cmd_nfal(args)
    if args.cmd != "run":
        _build_parser().print_help()
        return 2

    from core.pipeline import pipe
    from core.pipeline_loader import load_pipeline_file

    # --pipeline 收「管线 md 路径」**或**「在场管线编号」（极端渗透 D8 实证：此前只当路径，
    # 传最自然的编号 `--pipeline P01` 会报「管线解析失败：P01」——P01 明明是合法管线，
    # 属**错误归因**且无修复指引；`nf pipeline dryrun` 的同类参数则明写「管线 md 路径」）。
    import glob as _glob
    _pl_arg = str(args.pipeline)
    _pl_path = _pl_arg if os.path.isfile(_pl_arg) else ""
    _dirs = [os.path.join(ROOT, "03_管线库")] + sorted(
        _glob.glob(os.path.join(ROOT, "community", "*", "pipelines")))
    _avail = [os.path.basename(p)[:-3] for d in _dirs
              for p in sorted(_glob.glob(os.path.join(d, "*.md")))]
    if not _pl_path:
        for _d in _dirs:
            for _p in sorted(_glob.glob(os.path.join(_d, "*.md"))):
                _base = os.path.basename(_p)[:-3]
                if _base.split("_", 1)[0] == _pl_arg or _base == _pl_arg:
                    _pl_path = _p
                    break
            if _pl_path:
                break
    pipeline = load_pipeline_file(_pl_path or _pl_arg)
    if pipeline is None:
        print("✗ 管线解析失败：%s" % _pl_arg, file=sys.stderr)
        print("  修复指引：--pipeline 收**管线 md 路径**（如 03_管线库/P01_标准管线.md）"
              "或在场的管线编号；当前可用：%s"
              % ("（文件在场但解析失败：检查 frontmatter 与结构）" if _pl_path and not _avail
                 else "、".join(_avail) or "（未发现任何管线）"), file=sys.stderr)
        return 1

    store, err = _open_store(args, args.store)   # 落点不可用 ⇒ 干净拒绝（含 OSError：盘/权限）
    if err is not None:
        return err
    if args.seed:
        stats = _seed_store(store)
        print(f"  seed 装载：官方核心 {stats['core']} 件"
              f" + 轻混组合包 {stats['combo']} 件 → {_portable_path(store.home)}")
    else:
        print(f"  store：{_portable_path(store.home)}")

    selected = [m.strip() for m in args.modules.split(",") if m.strip()]
    # B2 变体：--variant-add/--variant-remove 经 apply_variant 变换 selected
    if args.variant_add or args.variant_remove:
        from core.variants import apply_variant
        v = apply_variant(selected, {
            "add": [x.strip() for x in args.variant_add.split(",") if x.strip()],
            "remove": [x.strip() for x in args.variant_remove.split(",") if x.strip()],
        })
        selected = v.selected
        print(f"  [变体] selected {args.modules.split(',')} → {selected}"
              + (f"（移除 {args.variant_remove}）" if args.variant_remove else ""))
    dest = args.dest
    r = pipe(store, pipeline, selected,
             include_references=not args.no_include_refs,
             fmt=args.fmt, dest_dir=dest,
             fail_on_gate=not args.force_export,
             doc_semantics=args.doc_semantics)

    print(f"\n== 质量门 ==\n  PASS {r.gate.n_pass} · WARN {r.gate.n_warn}"
          f" · FAIL {r.gate.n_fail}" + ("（可产出）" if r.ok else "（存在 FAIL）"))
    # B1 可解释化：逐条含修复建议（quality_gate 报告样式，warn/fail 都 actionable）
    for issue in r.gate.issues:
        if issue.level in ("fail", "warn"):
            print(f"  [{issue.level.upper()}] {issue.message}")
            if issue.suggestion:
                print(f"      建议：{issue.suggestion}")
    for w in r.warnings:
        print(f"  [INFO] {w}")
    if r.export is not None:
        print("\n== 导出 ==")
        if r.export.files:
            for f in r.export.files:
                print(f"  ✓ {f}")
        if r.export.warnings:
            for w in r.export.warnings:
                print(f"  [导出] {w}")
    if not r.ok:
        print("\n✗ 质量门 FAIL（可信任度不变量）"
              + ("；已按 --force-export 导出诊断产物" if args.force_export
                 else "——修复装配后重跑或加 --force-export 看坏产物"), file=sys.stderr)
        return 1
    print("\n★ 全链管道 PASSED ✓")
    return 0






def _cmd_cli(args) -> int:
    """nf cli：CLI 信息架构机读层（T11.3；只读消费 argparse + terminal.FAMILIES）。"""
    import json as _json
    from core import cli_catalog as cc

    sub = str(getattr(args, "cli_cmd", "") or "")
    if sub != "map":
        print("  ✗ 需要子命令：`nf cli map [--write|--check] [--json]`"
              "（修复指引：见 nf cli --help）", file=sys.stderr)
        return 2
    try:
        parser = _build_parser()
    except Exception as exc:  # noqa: BLE001 - 命令面坏件 → 可修正的用户问题
        print("  ✗ 构建命令面失败：%s（修复指引：修复 argparse 面后重跑）" % exc,
              file=sys.stderr)
        return 2
    want_json = bool(getattr(args, "json", False))
    if getattr(args, "write", False):
        paths, doc = cc.write(ROOT, parser)
        issues = cc.coverage_issues(doc)
        if want_json:
            print(_json.dumps({"kind": "cli-map-check", "schema": "nf-cli-map-check/1",
                               "ok": not issues, "issues": issues, "written": paths,
                               "coverage": doc["coverage"]},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            for rel in paths:
                print("  ✓ 已生成 %s" % rel)
            print("  命令 %d · 族 %d · 已归族 %d"
                  % (doc["coverage"]["commands"], doc["coverage"]["families"],
                     doc["coverage"]["covered"]))
        return 0 if not issues else 1
    if getattr(args, "check", False):
        issues, diffs, doc = cc.check(ROOT, parser)
        if want_json:
            print(_json.dumps({"kind": "cli-map-check", "schema": "nf-cli-map-check/1",
                               "ok": not issues, "issues": issues, "diffs": diffs,
                               "coverage": doc["coverage"]},
                              ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print("== nf cli map --check（生成件 vs 实时重算）==")
            for issue in issues:
                print("  [FAIL] %s" % issue)
            print("  → %s" % ("PASS" if not issues else "FAIL"))
        return 0 if not issues else 1
    doc = cc.build(parser, root=ROOT)
    issues = cc.coverage_issues(doc)
    if want_json:
        print(_json.dumps(doc, ensure_ascii=False, indent=2, sort_keys=True))
        return 0 if not issues else 1
    cov = doc["coverage"]
    print("== nf cli map（命令面 IA · 只读）==")
    print("  顶层命令 %d · 能力族 %d · 已归族 %d · JSON 面 %d"
          % (cov["commands"], cov["families"], cov["covered"],
             sum(1 for c in doc["commands"] if c["has_json"])))
    for fam in doc["families"]:
        print("  %-10s %s（%d 条）"
              % (fam["id"], fam["name"], len(fam["commands"])))
    for issue in issues:
        print("  [FAIL] %s" % issue)
    print("  → %s" % ("PASS" if not issues else "FAIL"))
    return 0 if not issues else 1


def guarded_main(argv=None) -> int:
    """`main()` 的异常兜底 —— **CLI 与常驻守护共用的同一条错误面**。

    为什么单独抽出来（2026-10-10 全仓审计 X0，P0）：守护 `core.daemon.execute()` 此前直接调
    `main()`、只兜 `SystemExit`，于是任何未捕获异常都穿透守护循环、**杀死常驻进程**——实测
    `nf receipts` 在 `protocol/RECEIPTS.json` 被截断时必抛 `json.JSONDecodeError`，18/18
    条 protocol JSON 都如此；客户端拿 rc=1 + 零输出。兜底是仓库既有的正确实现，只是**写在了
    `cli()` 里而没有到守护那条路径上**。抽到这里 ⇒ 同一语义只有一份实现，两条执行路径
    （终端直跑 / 守护内跑）的 (退出码, stderr 文本) 逐字一致。

    纪律：只兜 `Exception`（`SystemExit` 照旧上抛，由调用方按 argparse 语义归一；`KeyboardInterrupt`
    与 `BrokenPipeError` 各自归一为 130 / 0）；`NF_DEBUG` 在场时透出原始堆栈（排障用）。
    """
    try:
        code = main(argv)
    except BrokenPipeError:
        try:
            devnull = os.open(os.devnull, os.O_WRONLY)
            os.dup2(devnull, sys.stdout.fileno())
        except Exception:  # nosec B110 —— 尽力而为：终端重定向失败即沿用默认（见 AUD-0016）
            pass
        code = 0
    except KeyboardInterrupt:
        code = 130
    except Exception as exc:
        if os.environ.get("NF_DEBUG"):
            raise
        print("  ✗ 内部错误：%s（重跑 NF_DEBUG=1 nf ... 看堆栈）" % exc,
              file=sys.stderr)
        code = 1
    return code if isinstance(code, int) else 0


def cli(argv=None) -> int:
    """CLI 运行时封装：SIGPIPE 语义 + 断管/中断兜底 + 退出码归一。

    - POSIX：恢复 SIGPIPE 默认动作（`nf ... | head` 静默截断，无 traceback）；
    - 断管兜底（Windows 无 SIGPIPE 场景）；
    - Ctrl-C → 130；返回非 int（如 None）按 0 处理。
    - 未预期异常：默认一句错误 + 提示（NF_DEBUG=1 时透出堆栈），不裸刷 traceback。

    兜底实现只在 `guarded_main()`（上）一处：本函数只做「进程级」准备（SIGPIPE 动作），
    其余转交共用实现——**别在这里再写一份 try/except**（两处实现就会分叉，历史教训见审计 §0.3）。
    """
    try:
        import signal
        # Windows 无 SIGPIPE：取不到即跳过（原写法在该平台靠 except 兜住，行为等价）。
        _sigpipe = getattr(signal, "SIGPIPE", None)
        if _sigpipe is not None:
            signal.signal(_sigpipe, signal.SIG_DFL)
    except Exception:  # 尽力而为：跳过不可读/不可解析项（该类缺口由对应门禁与 AUD-0016 静默跳过清单另行报出）  # nosec B110 —— 尽力而为：跳过不可读/不可解析项（对应门禁另报；见 AUD-0016）
        pass
    return guarded_main(argv)


if __name__ == "__main__":
    # 必须**把 argv 显式递进去**：`main()` 的 `--version` 短路判据是「argv 就是 ['--version']」，
    # 而 `cli()` 原样转 `main(None)` 时该判据永远为假 ⇒ 为打印一行版本号白建整个 argparse 命令面
    # （实测 **99 ms**，65 条子命令）。传 argv 与 `parse_args(None)` 取的是同一份 sys.argv[1:]。
    sys.exit(cli(sys.argv[1:]))
