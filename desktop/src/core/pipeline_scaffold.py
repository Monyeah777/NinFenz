"""v2.8.0 波B S4：管线脚手架（`nf pipeline new` 库实现）。

从 03_管线库/P00_通用文档生成管线.md 骨架派生新管线文档——按 01 §2 / 06 §10
「复制 P00 派生，改 id/name/层名/挂载/flow/tags」的最小脚手架。
只做派生文本；登记 02 / 填层名挂载由作者按 README「新领域接入三步」补齐（I5 引擎不改）。
"""
from __future__ import annotations

import re
from typing import List, Tuple


def normalize_pipeline_id(raw: str) -> str:
    pid = (raw or "").strip().upper()
    if not re.fullmatch(r"P\d{2,4}", pid):
        raise ValueError("管线 id 应为 P 开头两位以上数字（如 P07/P90）")
    return pid


def default_filename(pid: str, name: str) -> str:
    """`<id>_<安全名>.md`——**id 先过校验**，任何情况下都不许把路径分隔符带进文件名。

    实测（本轮 CLI 注入审计）：修复前本函数原样拼 `pid`，`default_filename("../../x", …)`
    会返回 `../../x_名字.md`——安全性完全依赖调用方「先 `scaffold_pipeline` 校验、后取名」
    的**顺序**；任何新调用方只要先取名，就能拼出可逃逸的相对路径。这里把校验前移，让
    不安全的文件名**根本构造不出来**（分隔符一律不可能出现）。
    """
    pid = normalize_pipeline_id(pid)
    safe = re.sub(r"[^\w\u4e00-\u9fff]+", "_", name.strip()).strip("_")
    return "%s_%s.md" % (pid, safe or "派生管线")


def _domain_tags(domain: str) -> List[str]:
    d = (domain or "").strip().rstrip("包").rstrip("领域")
    return ["%s领域" % d] if d else []


def _yaml_line(ln: str, pid: str, name: str, tags_extra: List[str]) -> Tuple[str, str]:
    """yaml 块内单行替换 → (新行, 命中的键名或空串)。"""
    if re.fullmatch(r"  id: P\d{2,4}\s*", ln):
        return "  id: %s" % pid, "id"
    if ln.startswith("  name: "):
        return "  name: %s" % name, "name"
    if ln.strip().startswith("tags: "):
        inner = ln.split(":", 1)[1].strip()
        items = [x.strip().strip("[]") for x in inner.split(",") if x.strip()]
        for t in tags_extra:
            if t not in items:
                items.append(t)
        return "  tags: [%s]" % ", ".join(items), "tags"
    return ln, ""


def _rewrite_yaml_block(new: str, pid: str, name: str,
                        tags_extra: List[str]) -> Tuple[str, bool, bool, bool]:
    out: List[str] = []
    in_block = False
    done = {"id": False, "name": False, "tags": False}
    for ln in new.split("\n"):
        if not in_block:
            if ln.strip().startswith("```"):
                in_block = True
            out.append(ln)
            continue
        if ln.strip().startswith("```"):
            in_block = False
            out.append(ln)
            continue
        replaced_line, kind = _yaml_line(ln, pid, name, tags_extra)
        if kind and not done[kind]:
            done[kind] = True
            out.append(replaced_line)
            continue
        out.append(ln)
    return "\n".join(out), done["id"], done["name"], done["tags"]


def _source_note(note: str, domain: str) -> str:
    src = note or "由 `nf pipeline new` 自 P00 通用骨架派生"
    if domain:
        src = "由 `nf pipeline new --from P00 --domain %s` 派生" % domain.strip()
    return src


def scaffold_pipeline(template_text: str, pipeline_id: str, name: str,
                      domain: str = "", note: str = "") -> str:
    """把模板管线文本派生为新管线文本。

    替换：标题行 / 顶层 yaml id / name / tags（追加领域标签）——层位 id P00-P80
    与层名保持不变，交作者按领域装配。校验失败抛 ValueError（不静默产坏档）。
    """
    pid = normalize_pipeline_id(pipeline_id)
    name = (name or "").strip()
    if not name:
        raise ValueError("name 必填（管线显示名）")

    # 1) 标题行：# 管线 P00 · 通用文档生成管线
    new, n = re.subn(r"(?m)^#\s*管线\s+P\d+\s*[·.、\-]?\s*.*$",
                     "# 管线 %s · %s" % (pid, name), template_text, count=1)
    if n != 1:
        raise ValueError("模板缺少管线标题行（期望 `# 管线 Pxx · 名称`）")

    # 2) yaml 顶层 id/name/tags（层位 id 行带 `- id:` 前缀，不受影响）
    text, replaced_id, replaced_name, replaced_tags = _rewrite_yaml_block(
        new, pid, name, _domain_tags(domain))
    if not (replaced_id and replaced_name and replaced_tags):
        raise ValueError("模板 yaml 块缺少顶层 id / name / tags 键（模板结构变更？）")

    # 3) 派生来源注记（标题下插一行）
    src = _source_note(note, domain)
    header = "# 管线 %s · %s" % (pid, name)
    idx = text.index(header) + len(header)
    return text[:idx] + "\n> %s（v2.8.0 波B S4 脚手架：按 01 §2 填层名/挂载 → 02 登记即调度，I5）" % src + text[idx:]
