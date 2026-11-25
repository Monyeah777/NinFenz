#!/usr/bin/env python3
"""Build the NF hard-tech governance registry and human-readable ladders.

This is a planning/governance artifact generator, not a runtime feature.
It keeps the 112-node coverage baseline and overlays 24 hard-tech capabilities
plus 10 frontier trials.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MAP = ROOT / "results/app/FEATURE_CAPABILITY_MAP.md"
OUT = ROOT / "results/app/governance"
OUT.mkdir(parents=True, exist_ok=True)
TODAY = "2026-11-24"

NEW_NODES = {
    "C0-08": ("证据信封与 claim ledger", "C0"),
    "C0-09": ("性能与资源预算", "C0"),
    "C0-10": ("数据/格式迁移", "C0"),
    "C1-10": ("格式保真度报告", "C1"),
    "C2-09": ("纠错语料与评估", "C2"),
    "C5-12": ("内容可访问性审计", "C5"),
    "C6-10": ("可访问导出", "C6"),
    "C7-14": ("Pack 签名与信任根", "C7"),
    "C7-15": ("审计/溯源日志", "C7"),
    "C8-14": ("辅助输入与读屏遍历", "C8"),
    "C8-15": ("搜索质量与排序", "C8"),
    "C8-16": ("本地化/RTL/pseudolocale", "C8"),
    "C9-01": ("覆盖矩阵", "C9"),
    "C9-02": ("扩展点/SPI", "C9"),
    "C9-03": ("声明式扩展", "C9"),
    "C9-04": ("开放格式/互操作桥", "C9"),
    "C9-05": ("数据可携带/退出", "C9"),
    "C9-06": ("用户控制/可逆/可解释", "C9"),
    "C9-07": ("自定义/预设", "C9"),
    "C9-08": ("扩展治理/信任", "C9"),
}

H = [
    dict(id="H1.1", layer="H1", name="版式感知通用接入", hardness="H3",
         moat="需要版式分析、阅读顺序、表格拓扑、脚注锚点和流式处理；格式转换器只能给扁平文本，做完后所有下游都受益。",
         current_stage="not-started", benchmark="30 份多栏/扫描/旋转/侧栏/图注 PDF 真值集",
         threshold="阅读顺序 ≥98%，表格 F1 ≥95%，脚注 ≥95%，0 OOM，500 页 <60s",
         corpus="30 份版式真值文档 + 页/框/单元格标注", node_ids=["C1-04","C1-05","C9-04"],
         risks=["多栏/侧栏阅读顺序","合并单元格","旋转页","CJK 标点"], next="先做 10 页原型，直接产出 nf-sdir/1。", priority="P0"),
    dict(id="H1.2", layer="H1", name="保真账本", hardness="H2",
         moat="需要块级源坐标与 preserved/degraded/lost 账本；普通导入只报成功/失败，账本让所有降级可见、可追。",
         current_stage="not-started", benchmark="30 份真值文档的特征账本",
         threshold="100% 特征有账；0 静默丢失；差异可定位到页/框",
         corpus="30 份文档 × 12 类特征（标题/列表/表格/图/脚注/引用/代码/公式/alt/语言/顺序/元数据）",
         node_ids=["C1-08","C1-10","C9-01"], risks=["特征分类争议","坐标精度","跨页表格"], next="定义 feature ledger schema，再接入 H1.1。", priority="P0"),
    dict(id="H1.3", layer="H1", name="多源融合", hardness="H3",
         moat="需要跨版本/译本/批注的章节对齐、冲突检测和来源保留；普通导入一次只处理一个源。",
         current_stage="not-started", benchmark="10 组三版本/译本/批注",
         threshold="章节对齐 ≥95%，冲突 100% 标记，0 静默覆盖",
         corpus="10 组同文多版本（原稿/修订/译本/批注）", node_ids=["C1-04","C2-04","C7-07"],
         risks=["章节顺序变化","译文不等长","批注锚点漂移"], next="先做两版本对齐，再扩三版本。", priority="P1"),
    dict(id="H1.4", layer="H1", name="可恢复流式接入", hardness="H2",
         moat="需要流式解析、检查点、断点续传和内存上限；普通导入一次性读入，500 页就崩。",
         current_stage="not-started", benchmark="500 页导入 + 杀进程恢复",
         threshold="25/50/75% 杀进程后 100% 恢复；0 丢失；峰值 ≤300MB",
         corpus="500 页 PDF/DOCX/EPUB + 3 个杀进程点", node_ids=["C1-01","C0-09"],
         risks=["检查点一致性","临时文件清理","内存峰值"], next="先做 PDF 分页检查点，再扩格式。", priority="P1"),

    dict(id="H2.1", layer="H2", name="语义文档 IR", hardness="H3",
         moat="需要类型化块、关系、布局、可访问性、溯源五合一；Markdown/HTML 只有扁平文本，无法支撑合并/复用/可访问导出。",
         current_stage="not-started", benchmark="100% P0 文档入 IR + 往返",
         threshold="100% P0 文档入 IR；往返语义等价 ≥98%",
         corpus="30 份真值文档 + 5 组往返", node_ids=["C2-01","C4-02","C4-11"],
         risks=["IR 过度设计","旧 nf-doc 迁移","关系闭包"], next="先冻结最小 SDIR，不做大而全。", priority="P0"),
    dict(id="H2.2", layer="H2", name="约束感知 schema 归纳", hardness="H3",
         moat="需要从语料推断章节/槽位/约束，并校准置信度；普通模板只能人工建。",
         current_stage="not-started", benchmark="20 组语料 + 人工标注",
         threshold="槽位 P≥0.9/R≥0.85，ECE≤0.1",
         corpus="20 组协议/规格/样例文档", node_ids=["C2-04","C2-09"],
         risks=["过拟合","置信度虚高","长尾章节"], next="先做槽位候选，不自动写项目。", priority="P1"),
    dict(id="H2.3", layer="H2", name="语义修复", hardness="H2",
         moat="需要识别层级断裂、孤儿图注、表头缺失、alt 缺失、阅读顺序错误，并给出可逆修复；普通校验只报错。",
         current_stage="not-started", benchmark="50 份坏文档",
         threshold="修复成功 ≥90%，0 不可恢复，所有修复可撤销",
         corpus="50 份人工破坏文档（层级/图注/表头/alt/顺序）", node_ids=["C1-10","C2-03"],
         risks=["误修","不可逆","跨块依赖"], next="先做检测，再做建议，不自动改写。", priority="P1"),
    dict(id="H2.4", layer="H2", name="块级溯源图", hardness="H2",
         moat="需要块→源页/框/变换的不可篡改链路；普通导出只给文件名，无法回答“这块从哪来”。",
         current_stage="prototype", benchmark="100% 块可追 + 篡改检测",
         threshold="100% 块可追；篡改 100% 检出；离线可验",
         corpus="30 份文档 + 10 组篡改", node_ids=["C0-08","C7-15"],
         risks=["坐标漂移","摘要链性能","旧数据无溯源"], next="接 C0-08 证据信封，先覆盖新导入。", priority="P1"),

    dict(id="H3.1", layer="H3", name="类型化管线演算", hardness="H3",
         moat="需要端口/类型/权重/约束的可编译图；普通 DAG 只查环，不查类型/契约。",
         current_stage="prototype", benchmark="100 张图 + 50 个类型错误",
         threshold="100% 图可校验；0 类型错误漏报；同输入同 plan hash",
         corpus="100 张管线图（合法/环/端口错/类型错）", node_ids=["C3-03","C3-04"],
         risks=["类型系统膨胀","兼容旧图","权重语义"], next="在现有 graph-validate 上加类型层，不重写。", priority="P1"),
    dict(id="H3.2", layer="H3", name="约束求解/规划", hardness="H3",
         moat="需要由 spec+模块+资产合成合法 plan，并给 unsat core；普通管线只能人工搭。",
         current_stage="not-started", benchmark="50 个规划任务",
         threshold="合法 plan ≥95%，unsat 解释 100%，<2s",
         corpus="50 个 spec/模块/资产组合（含 unsat）", node_ids=["C3-04","C4-01"],
         risks=["NP-hard","解不唯一","解释可读性"], next="先做有界搜索+unsat core，不追求全局最优。", priority="P1"),
    dict(id="H3.3", layer="H3", name="增量重规划", hardness="H2",
         moat="需要改一个节点/槽位只重算受影响子图；普通实现全量重建。",
         current_stage="not-started", benchmark="100 次节点/槽位变更",
         threshold="重建集最小；0 过期输出；<300ms",
         corpus="100 次变更（节点/边/槽位/权重）", node_ids=["C4-01","C4-12"],
         risks=["依赖漏算","缓存失效","顺序不确定性"], next="先做 plan diff，再做最小重建。", priority="P1"),
    dict(id="H3.4", layer="H3", name="组合编排", hardness="H2",
         moat="需要多项目依赖、共享资产、失败隔离；普通批处理一错全停。",
         current_stage="not-started", benchmark="50 项目组合",
         threshold="0 交叉污染；失败隔离 100%；可恢复",
         corpus="50 项目（共享 Pack/资产/模板）", node_ids=["C4-12","C8-02"],
         risks=["共享状态","依赖环","部分失败"], next="先做只读依赖图，再做并行调度。", priority="P2"),

    dict(id="H4.1", layer="H4", name="确定性内容构建", hardness="H3",
         moat="需要内容寻址、Merkle DAG、缓存和字节可复现；普通导出每次重跑，无法增量/验证。",
         current_stage="prototype", benchmark="100 次构建 + 缓存/增量",
         threshold="100 次构建同 sha；缓存命中 ≥80%；增量 <300ms",
         corpus="30 份文档 × 3 次构建", node_ids=["C4-01","C4-05","C0-08"],
         risks=["字体/时间戳","缓存污染","哈希碰撞"], next="先把现有导出纳入 build graph，不改输出格式。", priority="P0"),
    dict(id="H4.2", layer="H4", name="语义合并/装配", hardness="H3",
         moat="需要章节/表格/交叉引用/引文的语义合并；普通合并按标题或文本去重。",
         current_stage="prototype", benchmark="30 组语义合并",
         threshold="0 静默丢失；交叉引用 100% 有效；表格单元格正确",
         corpus="30 组章节/表格/交叉引用合并", node_ids=["C4-11","C6-01"],
         risks=["编号冲突","引用漂移","表格合并"], next="先把 NfDocMerger 升级为块/单元格级，不动 UI。", priority="P1"),
    dict(id="H4.3", layer="H4", name="块级增量重算", hardness="H2",
         moat="需要块依赖图和精确重算；普通编辑器全量重渲染。",
         current_stage="not-started", benchmark="100 次块编辑",
         threshold="parity 100%；p95 <300ms；0 过期块",
         corpus="100 次编辑（文本/表格/引用/图片）", node_ids=["C4-07","C4-08"],
         risks=["依赖漏算","渲染缓存","撤销栈"], next="先做块 hash/依赖，再接预览。", priority="P1"),
    dict(id="H4.4", layer="H4", name="单 IR 多 Profile", hardness="H2",
         moat="需要同一 IR 生成 web/print/EPUB/PDF/DOCX/accessible，而不是每个格式一套转换。",
         current_stage="prototype", benchmark="10 文档 × 5 Profile",
         threshold="语义 parity ≥98%；验证器 0 error",
         corpus="10 份文档 × 5 Profile", node_ids=["C6-01","C6-02","C6-04"],
         risks=["格式差异","字体嵌入","分页"], next="先统一 HTML/EPUB/PDF 的 IR 渲染，再接 DOCX。", priority="P1"),

    dict(id="H5.1", layer="H5", name="可访问即构造", hardness="H3",
         moat="需要从 IR 直接生成 PDF/UA、EPUB A11y、DOCX 可访问结构；普通导出后补标签，阅读顺序/alt/表头经常错。",
         current_stage="prototype", benchmark="20 文档三种格式",
         threshold="EPUBCheck/veraPDF/Open XML 0 error；WCAG AA 0 blocker",
         corpus="20 份含表格/图/脚注/多语言文档", node_ids=["C5-12","C6-10"],
         risks=["PDF/UA 标签","EPUB nav","DOCX 表头"], next="先做 EPUB 验证器门禁，再做 PDF/UA。", priority="P0"),
    dict(id="H5.2", layer="H5", name="证据随包", hardness="H3",
         moat="需要产物+manifest+provenance+validation+signature 一体，离线可验；普通导出只给文件。",
         current_stage="prototype", benchmark="100 个交付包",
         threshold="100% 可验；篡改 100% 检出；0 网络",
         corpus="100 包（正常/篡改/缺件/错摘要）", node_ids=["C5-08","C6-03","C7-15"],
         risks=["签名性能","旧包兼容","证据膨胀"], next="先冻结 nf-evidence/1，再接 preserve。", priority="P0"),
    dict(id="H5.3", layer="H5", name="跨端首次打开", hardness="H2",
         moat="需要字体/CJK/RTL/结构兼容，在多个阅读器/办公应用首次打开；普通导出只测自家。",
         current_stage="prototype", benchmark="EPUB/PDF/DOCX 各 3 应用",
         threshold="100% 首次打开；0 修复；0 缺字",
         corpus="10 文档 × 3 应用 × 3 格式", node_ids=["C6-01","C6-04","C9-04"],
         risks=["字体缺字","RTL 镜像","阅读器差异"], next="先建 3 应用矩阵，再补字体。", priority="P1"),
    dict(id="H5.4", layer="H5", name="签名可复现包", hardness="H3",
         moat="需要确定性 zip + TUF/Sigstore 元数据 + 回滚/冻结；普通 Pack 是无签名 zip。",
         current_stage="prototype", benchmark="20 Pack 更新 + 签名",
         threshold="两次构建同 sha；签名 100%；回滚/冻结 100%",
         corpus="20 Pack（正常/冲突/降级/篡改）", node_ids=["C7-14","C6-03","C9-08"],
         risks=["密钥轮换","离线根","旧包升级"], next="先做 TUF 元数据模型，不改现有 Pack 格式。", priority="P0"),

    dict(id="H6.1", layer="H6", name="语义三方合并", hardness="H3",
         moat="需要块/表格单元格/移动检测和冲突裁决；普通 diff 按行比较，移动就全红。",
         current_stage="prototype", benchmark="50 组三方合并",
         threshold="0 静默丢失；冲突 precision ≥95%；引用 100% 有效",
         corpus="50 组（移动/表格/改写/删除）", node_ids=["C4-11","C4-10"],
         risks=["移动检测","表格冲突","引用重编号"], next="先在 nf-doc 上做三方，不动 SDIR。", priority="P1"),
    dict(id="H6.2", layer="H6", name="Pack 更新演算", hardness="H3",
         moat="需要 base+overlay、签名元数据、依赖、回滚/冻结；普通更新只覆盖文件。",
         current_stage="prototype", benchmark="20 个更新场景",
         threshold="0 项目损坏；回滚/冻结 100%；未签名严格拒绝",
         corpus="20 场景（冲突/删除/降级/篡改）", node_ids=["C7-04","C7-05","C7-06","C9-08"],
         risks=["overlay 合并","依赖顺序","旧项目迁移"], next="先接 H5.4 签名，再做依赖图。", priority="P0"),
    dict(id="H6.3", layer="H6", name="内容复用图", hardness="H3",
         moat="需要跨 100 项目找可复用块、更新传播、冲突检测；普通复用是复制粘贴。",
         current_stage="not-started", benchmark="100 项目复用图",
         threshold="recall ≥90%；传播 100%；0 过期",
         corpus="100 项目（共享片段/模板/资产）", node_ids=["C7-07","C2-07","C9-01","C9-05"],
         risks=["重复检测","传播风暴","所有权"], next="先做只读索引，再做传播。", priority="P1"),
    dict(id="H6.4", layer="H6", name="模板归纳 + 迁移", hardness="H3",
         moat="需要从样例归纳模板/spec，并支持 N-2 迁移/lineage；普通模板靠人工写。",
         current_stage="not-started", benchmark="20 组模板归纳 + N-2 迁移",
         threshold="模板 F1 ≥0.85；N-2 迁移 100%；0 丢失",
         corpus="20 组样例 + 3 个旧版本项目", node_ids=["C2-07","C7-11","C0-10","C9-03"],
         risks=["归纳过拟合","迁移丢字段","旧格式"], next="先做模板候选，再做 migration runner。", priority="P1"),
]

T = [
    dict(id="T01", title="500 页多栏 PDF → 可访问 EPUB/PDF/DOCX",
         hard_ids=["H1.1","H1.2","H2.1","H2.3","H5.1"],
         pass_conditions="阅读顺序 ≥98%，表格 F1 ≥95%，脚注 ≥95%，0 OOM，<60s，EPUBCheck/veraPDF/Open XML 0 error",
         corpus="500 页多栏 PDF + 30 页真值子集", status="planned"),
    dict(id="T02", title="两版 DOCX 语义三方合并 + 多源融合",
         hard_ids=["H1.3","H4.2","H6.1"],
         pass_conditions="0 静默丢失；冲突 precision ≥95%；交叉引用 100% 有效；表格单元格正确",
         corpus="两份修订 DOCX + 三版本组", status="planned"),
    dict(id="T03", title="spec+模块+资产求解合法管线 + unsat 解释",
         hard_ids=["H2.2","H3.1","H3.2"],
         pass_conditions="50 任务合法 plan ≥95%；unsat 解释 100%；<2s",
         corpus="50 个规划任务（含 unsat）", status="planned"),
    dict(id="T04", title="改一块增量构建，输出完全一致",
         hard_ids=["H3.3","H4.1","H4.3"],
         pass_conditions="parity 100%；p95 <300ms；两次构建字节一致；0 过期块",
         corpus="100 次块编辑", status="planned"),
    dict(id="T05", title="DOCX→IR→EPUB/PDF→IR→DOCX 往返",
         hard_ids=["H1.2","H4.4","H5.3"],
         pass_conditions="语义等价 ≥98%；EPUB/PDF/DOCX 各 3 应用首次打开 100%；0 缺字",
         corpus="10 份文档 × 3 格式", status="planned"),
    dict(id="T06", title="20 文档可访问交付",
         hard_ids=["H2.1","H5.1"],
         pass_conditions="EPUBCheck/veraPDF/Open XML 0 error；WCAG AA 0 blocker",
         corpus="20 份含表格/图/脚注/多语言文档", status="planned"),
    dict(id="T07", title="证据随包 + 离线验证 + 篡改检出",
         hard_ids=["H2.4","H5.2","H5.4"],
         pass_conditions="100 包可验；篡改 100% 检出；0 网络；签名/冻结 100%",
         corpus="100 包（正常/篡改/缺件/错摘要）", status="planned"),
    dict(id="T08", title="签名 Pack 更新：冲突/应用/回滚/冻结",
         hard_ids=["H5.4","H6.2"],
         pass_conditions="20 场景 0 项目损坏；回滚/冻结 100%；未签名严格拒绝",
         corpus="20 个 Pack 更新场景", status="planned"),
    dict(id="T09", title="100 项目复用图 + 组合编排",
         hard_ids=["H3.4","H6.3","H6.4"],
         pass_conditions="复用 recall ≥90%；传播 100%；0 过期；失败隔离 100%",
         corpus="100 项目 + 20 组模板", status="planned"),
    dict(id="T10", title="500 页导入在 25/50/75% 杀进程后续传",
         hard_ids=["H1.4","H4.1"],
         pass_conditions="100% 恢复；0 丢失；峰值 ≤300MB；构建可复现",
         corpus="500 页 PDF/DOCX/EPUB", status="planned"),
]

# Fill target stage and trial_ids from trials.
for h in H:
    h.setdefault("target_stage", "proven")
    h["trial_ids"] = [t["id"] for t in T if h["id"] in t["hard_ids"]]

# Parse baseline nodes from the current map.
text = MAP.read_text(encoding="utf-8")
baseline = []
for m in re.finditer(r"^- \*\*(C[0-8]-\d{2}) ([^*]+)\*\*：", text, re.M):
    baseline.append((m.group(1), m.group(2).strip()))
if len(baseline) != 92:
    raise SystemExit(f"expected 92 baseline nodes, got {len(baseline)}")

coverage = []
for nid, name in baseline:
    layer = nid.split("-")[0]
    hard_ids = [h["id"] for h in H if nid in h["node_ids"]]
    prio = "P0" if nid in {"C0-05","C7-14","C7-15"} else ("P1" if hard_ids else "P2")
    coverage.append(dict(id=nid, layer=layer, name=name, source="baseline",
                         current_state="partial", priority=prio, hard_ids=hard_ids,
                         owner="security" if prio == "P0" else ("core" if layer in {"C0","C3","C4","C5"} else "kotlin-ui"),
                         next="按 H/T 验收执行并回填证据" if hard_ids else "table stakes，季度回归"))
for nid, (name, layer) in NEW_NODES.items():
    hard_ids = [h["id"] for h in H if nid in h["node_ids"]]
    prio = "P0" if nid in {"C0-05","C7-14","C7-15"} else ("P1" if hard_ids or layer in {"C7","C8","C9"} else "P2")
    if nid == "C9-07":
        prio = "P2"
    coverage.append(dict(id=nid, layer=layer, name=name, source=("open" if layer == "C9" else "gap"),
                         current_state="absent", priority=prio, hard_ids=hard_ids,
                         owner="lead" if layer == "C9" else ("security" if nid == "C7-14" else "core"),
                         next="进入 Wave 0–3；先补契约再实现"))

coverage.sort(key=lambda x: (x["layer"], x["id"]))
if len(coverage) != 112:
    raise SystemExit(f"expected 112 coverage nodes, got {len(coverage)}")

# Preserve already-proven evidence across regeneration (never invent it).
registry_path = OUT / "registry.json"
if registry_path.exists():
    try:
        old = json.loads(registry_path.read_text(encoding="utf-8"))
    except Exception:
        old = {}
    old_h = {h.get("id"): h for h in old.get("hard_capabilities", [])}
    for h in H:
        prev = old_h.get(h["id"], {})
        if prev.get("current_stage") == "proven" and prev.get("evidence"):
            h["current_stage"] = "proven"
            h["evidence"] = prev["evidence"]
    old_t = {t.get("id"): t for t in old.get("trials", [])}
    for t in T:
        prev = old_t.get(t["id"], {})
        for key in ("status", "result_path", "result_sha256", "run_at"):
            if key in prev:
                t[key] = prev[key]

summary = {
    "coverage_total": 112,
    "baseline": 92,
    "gap": 12,
    "open": 8,
    "hard_capabilities": 24,
    "trials": 10,
    "proven_hard": sum(1 for h in H if h["current_stage"] == "proven"),
    "p0_hard": sum(1 for h in H if h.get("priority") == "P0"),
    "p1_hard": sum(1 for h in H if h.get("priority") == "P1"),
    "p2_hard": sum(1 for h in H if h.get("priority") == "P2"),
    "by_layer": {f"H{i}": sum(1 for h in H if h["layer"] == f"H{i}") for i in range(1, 7)},
    "status": "executing" if any(h["current_stage"] == "proven" for h in H) else "seeded",
    "notes": "Wave 0 运行时已落地：SDIR/构建图/证据包；proven 状态仅来自 trials/ 下的可复算结果。"
}
registry = {
    "schema": "nf-hardtech-governance/1",
    "generated_at": TODAY,
    "mode": "hardtech",
    "coverage": {
        "baseline_nodes": 92, "gap_nodes": 12, "open_nodes": 8, "total_nodes": 112,
        "baseline_ids": [nid for nid, _ in baseline],
        "new_ids": list(NEW_NODES.keys()),
        "nodes": coverage,
    },
    "hard_capabilities": H,
    "trials": T,
    "summary": summary,
}
(OUT / "registry.json").write_text(json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

# HARD_TECH_LADDER.md
lines = ["# NF 硬技术能力阶梯（24 项）", "",
         f"> 这 24 项才算技术力；基本项只算 table stakes。状态：not-started / research / prototype / product / proven。当前 {sum(1 for h in H if h['current_stage'] == 'proven')} 项 proven。", "",
         "| ID | 层 | 能力 | 难度 | 当前 | 目标 | 验收 |", "|---|---|---|---|---|---|---|"]
for h in H:
    lines.append(f"| {h['id']} | {h['layer']} | {h['name']} | {h['hardness']} | {h['current_stage']} | {h['target_stage']} | {h['threshold']} |")
lines += ["", "## 护城河与下一步", ""]
for h in H:
    lines.append(f"### {h['id']} {h['name']}")
    lines.append("")
    lines.append(f"- 护城河：{h['moat']}")
    lines.append(f"- 基准：{h['benchmark']}；语料：{h['corpus']}")
    lines.append(f"- 风险：{'；'.join(h['risks'])}")
    lines.append(f"- 下一步：{h['next']}")
    lines.append(f"- 映射节点：{', '.join(h['node_ids'])}；Trial：{', '.join(h['trial_ids'])}")
    lines.append("")
(OUT / "HARD_TECH_LADDER.md").write_text("\n".join(lines), encoding="utf-8")

# FRONTIER_TRIALS.md
lines = ["# NF Frontier Trials（10 条硬挑战）", "",
         "> 这些不是基本旅程；每条都要求 SDIR/构建图/求解/合并/可访问/证据之一。", "",
         "| ID | 挑战 | 关联 H | 通过条件 | 状态 |", "|---|---|---|---|---|"]
for t in T:
    lines.append(f"| {t['id']} | {t['title']} | {', '.join(t['hard_ids'])} | {t['pass_conditions']} | {t['status']} |")
lines += ["", "## 语料", ""]
for t in T:
    lines.append(f"- {t['id']}：{t['corpus']}")
(OUT / "FRONTIER_TRIALS.md").write_text("\n".join(lines), encoding="utf-8")

# SCORECARDS.md
proven_n = sum(1 for h in H if h["current_stage"] == "proven")
unrun_n = sum(1 for t in T if t["status"] == "planned")
lines = ["# 硬技术记分卡", "",
         f"> 当前 proven {proven_n}/24；未跑 Trials {unrun_n}/10。proven 只来自 trials/ 下可复算结果。", "",
         "## 六层 × 四项", ""]
for i in range(1, 7):
    lines.append(f"### H{i}")
    lines.append("")
    lines.append("| ID | 能力 | 当前 | 目标 | 关键阈值 |")
    lines.append("|---|---|---|---|---|")
    for h in [x for x in H if x["layer"] == f"H{i}"]:
        lines.append(f"| {h['id']} | {h['name']} | {h['current_stage']} | {h['target_stage']} | {h['threshold']} |")
    lines.append("")
lines += ["## 10 Trials", "", "| ID | 挑战 | 状态 |", "|---|---|---|"]
for t in T:
    lines.append(f"| {t['id']} | {t['title']} | {t['status']} |")
lines += ["", "## 结论", "",
          f"- 当前 proven：{proven_n}（" + ", ".join(h["id"] for h in H if h["current_stage"] == "proven") + "）",
          "- 当前 prototype：" + "/".join(h["id"] for h in H if h["current_stage"] == "prototype"),
          "- 当前 not-started：" + "/".join(h["id"] for h in H if h["current_stage"] == "not-started"),
          f"- 未跑 Trials：{unrun_n}/10"]
(OUT / "SCORECARDS.md").write_text("\n".join(lines), encoding="utf-8")

# GAP_BACKLOG.md
p0 = [h for h in H if h.get("priority") == "P0"]
p1 = [h for h in H if h.get("priority") == "P1"]
lines = ["# 硬技术缺口 Backlog", "",
         "> 只列 H 梯子；基本项（导入/导出/主题/搜索/备份）降为 P2 回归，不作为技术力验收。", "",
         "## P0（先做，失败阻断 Wave）", "",
         "| H | 能力 | 为什么现在 | 下一步 | 验收 |", "|---|---|---|---|---|"]
for h in p0:
    lines.append(f"| {h['id']} | {h['name']} | {h['moat']} | {h['next']} | {h['threshold']} |")
lines += ["", "## P1（紧随其后）", "", "| H | 能力 | 下一步 | 验收 |", "|---|---|---|---|"]
for h in p1:
    lines.append(f"| {h['id']} | {h['name']} | {h['next']} | {h['threshold']} |")
lines += ["", f"- P0：{len(p0)} 项；P1：{len(p1)} 项；P2：{sum(1 for h in H if h.get('priority')=='P2')} 项。",
          "- 基本项（C0–C8 中未映射 H 的节点）只做回归，不计入硬技术力。"]
(OUT / "GAP_BACKLOG.md").write_text("\n".join(lines), encoding="utf-8")

# README
readme = f"""# NF 硬技术治理包

> 状态：{TODAY}；proven {sum(1 for h in H if h["current_stage"] == "proven")}/24；未跑 Trials {sum(1 for t in T if t["status"] == "planned")}/10。
> 目标：用 24 个硬能力 + 10 条 Frontier Trials 证明“别人很难或做不到”的技术力；112 节点只做覆盖基线。

## 文件

- registry.json：112 覆盖节点 + 24 H + 10 Trials（机读）
- HARD_TECH_LADDER.md：24 项硬能力、护城河、阈值
- FRONTIER_TRIALS.md：10 条端到端硬挑战
- SCORECARDS.md：六层 × 四项 + Trials 状态
- GAP_BACKLOG.md：P0/P1 硬缺口
- ARCHITECTURE_TARGET.md：SDIR、构建图、证据、扩展、op
- HARD_TECH_REPORT.md：结论、现状、顺序、风险
- EXECUTION_STATUS.md：Wave 0 运行时落地与 Trials 证据
- trials/：T04/T07 等可复算结果 JSON
- benchmarks/：H4.4 等独立基准 JSON
- REVIEWS.md：标准/安全/可访问/对抗复核记录
- REFERENCES.md：硬技术对标锚点

## 口径

- 基本项（导入/导出/主题/搜索/备份/分享）是 table stakes，不作为技术力验收。
- H 能力必须满足：SDIR、求解、构建图、语义合并、可访问构造、证据、跨格式等价、复用图中的至少两项。
- 只有 proven 才算技术力；未 proven 不得写“已实现”。

## 校验

~~~bash
python app/scripts/hardtech_governance.py validate --strict
python app/scripts/hardtech_governance.py coverage
python -m pytest app/tests/test_hardtech_governance.py -q
~~~
"""
(OUT / "README.md").write_text(readme, encoding="utf-8")

print(json.dumps(summary, ensure_ascii=False, indent=2))
print("baseline", len(baseline), "coverage", len(coverage), "H", len(H), "T", len(T))
