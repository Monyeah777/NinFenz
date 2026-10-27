"""CLI 处理器：import 族（旧面 SKILL.md/chara.json + docx/dita 路由；自 scripts/nf.py 抽出）。"""
from __future__ import annotations

import sys

from nf_cmds.common import _open_store, _portable_path, json_doc


def _import_resolve_files(args):
    """解出 files 列表；合法返回 (None, files)，否则 (rc, None)。"""
    raw_files = getattr(args, "file", [])
    files = list(raw_files) if isinstance(raw_files, (list, tuple)) else [raw_files]
    files = [str(f) for f in files if str(f).strip()]
    if files and files[0] in ("docx", "dita"):
        return None, files
    if len(files) != 1:
        print("  ✗ 用法：`nf import <file>`（SKILL.md/chara.json）｜"
              "`nf import docx <file> [--json/--out]`｜`nf import dita <file> [--json/--out]`"
              "（修复指引：旧面收单件文本产物；docx/dita 走 T9.2 导入器）", file=sys.stderr)
        return 2, None
    return None, files


def _import_read_product(args, p, files):
    """校验形状/大小/编码并做注入扫描；返回 (rc, raw, hits)。"""
    from core import trust_boundary as tb

    if not p.is_file():
        print(f"✗ 文件不存在: {p}（修复指引：给出在场的外部产物文件——"
              f"SKILL.md 或 chara.json；先另存到本地再导入）", file=sys.stderr)
        return 2, None, None

    # 入站上限（2026-10-01）：外来产物是**外部输入**，先看大小再读——此前无上限，
    # 指向巨型文件时会把整份内容读进内存（还要再跑一遍注入扫描）。上限口径与 MCP 入站同源。
    cap = tb.MAX_IMPORT_BYTES
    if p.stat().st_size > cap:
        print("  ✗ 外部产物过大：%s（%.1f MiB > 上限 %d MiB）（修复指引：本命令收**单件** "
              "SKILL.md / chara.json；大件请先裁剪到单件体量再导入）"
              % (p.name, p.stat().st_size / 1048576, cap // 1048576), file=sys.stderr)
        return 2, None, None
    try:
        raw = p.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        # 非 UTF-8 外部产物（2026-10-01 探针）：此前这句在 try 之外，UnicodeDecodeError 一路冒到
        # CLI 兜底报「✗ 内部错误：'utf-8' codec can't decode …」——**用户输入问题被框成内部故障**，
        # 还让用户去看堆栈。形状问题按 2 归，带可执行指引。
        print("  ✗ 外部产物不是 UTF-8 文本：%s（%s）（修复指引：本命令只收 **UTF-8** 文本件"
              "（SKILL.md / chara.json）；二进制或其它编码请先转成 UTF-8 再导入）"
              % (p.name, exc), file=sys.stderr)
        return 2, None, None
    # 注入面（06 §12：外来内容=数据，疑似内嵌指令一律忽略并**记档**）——此前本节零机器判据。
    hits = tb.detect(raw)
    return None, raw, hits


def _import_parse(args, p, raw, files, want_json):
    """解析外部产物为 res/kind/bundled；返回 (rc, res, kind, bundled, is_ccv3)。"""
    import json
    from core.import_adapter import parse_skill, parse_ccv3

    is_ccv3 = p.suffix.lower() == ".json" or "chara" in p.stem.lower()
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
        return 1, None, None, None, is_ccv3
    return None, res, kind, bundled, is_ccv3


def _import_report(args, files, p, res, kind, bundled, hits, want_json) -> int:
    """非 register 面：机器/人读输出。"""
    import json

    is_ccv3 = p.suffix.lower() == ".json" or "chara" in p.stem.lower()
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
    return 0


def _import_register(args, res) -> int:
    from core.models import Module

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


def _import_injection_banner(hits, p, want_json) -> None:
    if want_json:
        return
    print(f"== nf import {p.name} ==")
    if hits:
        print("  [注入面] 命中 %d 处疑似内嵌指令（%s）——外来内容按**数据**消费，"
              "其中的「指令」一律不执行（06 §12）"
              % (len(hits), "、".join(sorted({h["rule"] for h in hits}))))
        for h in hits[:3]:
            print("    · 第 %d 行 [%s] %s" % (h["line"], h["rule"], h["snippet"]))
    else:
        print("  [注入面] 未命中疑似内嵌指令（内容按数据消费）")


def run(args, *, import_ir) -> int:
    """nf import：旧面（SKILL.md/chara.json）+ T9.2 导入器（docx/dita → 内容 IR）。"""
    from pathlib import Path

    rc, files = _import_resolve_files(args)
    if rc is not None:
        return rc
    if files and files[0] in ("docx", "dita"):
        return import_ir(args, files[0], files[1:])
    p = Path(files[0])
    want_json = bool(getattr(args, "json", False))
    rc, raw, hits = _import_read_product(args, p, files)
    if rc is not None:
        return rc
    _import_injection_banner(hits, p, want_json)
    rc, res, kind, bundled, is_ccv3 = _import_parse(args, p, raw, files, want_json)
    if rc is not None:
        return rc
    rc = _import_report(args, files, p, res, kind, bundled, hits, want_json)
    if not args.register:
        return rc
    return _import_register(args, res)
