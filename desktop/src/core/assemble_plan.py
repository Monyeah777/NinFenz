"""44 · 需求 → 自组装编排（内部闭环）：需求文本 → 装配计划 → 成品机器验收。

战略口径（STRATEGY §一/§三）：用户提需求自组装是 AI 通道的最终价值；本模块把
「需求→选包→取件→成品自检」做成可复现的内部编排：
1. plan(requirement)  需求关键词 → 预设包/管线 + 取件清单（模块/管线/资产）
2. check(output_md, plan) 对成品做机器验收：八段骨架在场、编号在装配允许集、
   决策句带引用、无编造编号、需求域=产物域（对齐 execution_drill R1/R3/R4 口径）。

身份口径（T3.1 身份整改）：预设表**非叙事交付物在前**（技术文档/合规/隐私/量化/AI系统/通用核心），
叙事域包（校园/西幻/轻混）是并列的一类；澄清问句按「交付物类型/受众/验收判据」问，
不再默认问「题材/玩法/世界」。

封闭期内不引外部 AI 实测；成品验收用仓库内真实战例（完整版样本）做回归样本。
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from core import json_doc

_ROOT = Path(__file__).resolve().parents[3]

#: 需求关键词 → 官方预设（包 id / 管线 id）。
#: 顺序即匹配优先级：**非叙事交付物预设在前**（身份整改 T3.1——NF 的首屏默认路径是交付物，
#: 叙事域包是并列的一类而非默认入口）；叙事三条保留在后，关键词相互独立不影响命中。
DOMAIN_MAP = [
    (["技术文档", "techdoc", "文档工厂", "说明书", "术语表"],
     ("技术文档域包", "P06")),
    (["合规", "监管", "合规审查"], ("合规与监管域包", "P98")),
    (["隐私", "数据治理", "个人信息"], ("隐私与数据治理域包", "P99")),
    (["量化", "因子", "回测", "绩效"], ("量化金融域包", "P08")),
    (["AI系统", "ai系统", "概念闭包", "前置依赖"], ("AI系统域包", "P07")),
    (["通用核心", "核心基础"], ("通用核心基础包", "P05")),
    (["西幻", "生存", "生存流"], ("西幻生存领域包", "P03")),
    (["校园", "情感", "恋爱", "毕业"], ("校园情感领域包", "P02")),
    (["轻混", "组合", "混搭"], ("校园西幻轻混组合包", "P04")),
]

#: 未命中官方预设但足以判定“用户有具体自定义题材”的内容线索
CUSTOM_CUES = [
    "自定义", "权谋", "宫廷", "科幻", "都市", "悬疑", "恐怖",
    "修仙", "机甲", "冒险", "武侠", "末日", "星际", "盗墓", "权斗",
]

_SEG = re.compile(r"^##\s*([0-7])\s*\.", re.M)
_MODULE = re.compile(r"(?:[\u4e00-\u9fff]+:)?M\d{2,3}")
_DECISION = re.compile(r"(应|应该|必须|禁止|不得|下一步|输出|结论)")
#: 引文形态（§N / 第N节 / LN / 前缀:MN / N行）。与 round_drill._CITE 同源，由
#: desktop/tests/test_redos_patterns.py 的夹具判据钉住两者逐字相同（同一语义两处实现的老病）。
#: 那条 [0-9A-Za-z_]+: 分支必须带 \b 前缀（2026-10-10 审计 Y3，P1）：长串字母数字无冒号时
#: 引擎会对每个起点各回溯一遍 ⇒ O(n²)（实测 4k/16k/64k = 11/178/2832 ms）；\b 让起点只落在
#: 词首 ⇒ 线性。
_CITATION = re.compile(r"(§\s*\d+(?:[.-]\d+)*|第\s*\d+\s*(?:节|步|章)|L\d+|"
                       r"\b[0-9A-Za-z_]+:[MTP]\d{2,3}|\b\d{1,3}\b\s*行)")

#: 管线 id → 包 id（T1.2 W2 跨域门的声明面归一；DOMAIN_MAP 的逆向索引）。
PIPELINE_TO_PACKAGE = {pipe: pkg for _keys, (pkg, pipe) in DOMAIN_MAP}

#: 装配产物「声明域」的锚定证据（只认结构化锚点，不做 P\d{2} 全文扫描——
#: 层位 id P00–P80 与管线 id 同形，全文扫描必然误报）。
_DECLARED_PIPELINE = (
    re.compile(r"^#\s*叙事世界完整版：[^\n]*?[（(]\s*(P\d{2})\s*[)）]", re.M),
    re.compile(r"active_pipeline\s*[=:：]\s*\**\s*(P\d{2})", re.I),
    re.compile(r"命中预设[^\n]{0,100}?管线\s*\**\s*(P\d{2})"),
    re.compile(r"pipelines/(P\d{2})[_-]"),
    re.compile(r"^domain\s*[：:]\s*[\"']?(P\d{2})\b", re.M),
)
_DECLARED_PACKAGE = re.compile(r"^#\s*叙事世界完整版：\s*([^\n（(]+)", re.M)
_PRESET_PACKAGE = re.compile(r"命中预设\s*\**\s*([A-Za-z0-9\u4e00-\u9fff_]+)")


def expected_domain(plan_: Dict[str, Any]) -> Dict[str, str]:
    """需求侧域：命中预设时 = (包, 管线)；自定义/未命中 = 空（不做跨域判定）。"""
    if not plan_.get("matched"):
        return {"package": "", "pipeline": ""}
    return {"package": str(plan_.get("package") or ""),
            "pipeline": str(plan_.get("pipeline") or "")}


def declared_domain(output_md: str) -> Dict[str, Any]:
    """产物侧声明域：从八段骨架的标题/§0 装配记录/管线路径取锚定证据。

    `pipelines` 为**集**：同一产物可引用官方线（如「P01 不参与本世界装配」）而不命中
    标题锚点，故判定用「需求域 ∈ 声明集」，不用单选。
    """
    pipes = set()
    for pat in _DECLARED_PIPELINE:
        pipes.update(m.group(1) for m in pat.finditer(output_md))
    pkg = ""
    m = _DECLARED_PACKAGE.search(output_md)
    if m:
        pkg = m.group(1).strip()
    if not pkg:
        m = _PRESET_PACKAGE.search(output_md)
        if m:
            pkg = m.group(1).strip()
    if not pkg and len(pipes) == 1:
        pkg = PIPELINE_TO_PACKAGE.get(next(iter(pipes)), "")
    return {"package": pkg, "pipelines": sorted(pipes)}


def domain_issues(output_md: str, plan_: Dict[str, Any],
                  expected_pipeline: Optional[str] = None) -> Tuple[List[str], Dict[str, Any]]:
    """T1.2 W2 跨域门：需求域 vs 产物声明域 → (issues, info)。

    判定口径（fail-closed 仅对**已声明的冲突**）：
    - 需求命中预设且产物声明了域，需求管线 ∉ 声明集 → FAIL；
    - 产物未声明域 → 不判死（记账 `checked=False`，修复指引见 info.reason）；
    - 需求为自定义（无预设域）→ 不判（域未声明，不做域比较）。
    """
    exp = expected_domain(plan_)
    if expected_pipeline:
        exp = {"package": exp["package"], "pipeline": str(expected_pipeline).strip()}
    declared = declared_domain(output_md)
    info: Dict[str, Any] = {"expected": exp, "declared": declared,
                            "checked": False, "ok": None}
    if not exp["pipeline"]:
        info["reason"] = "需求未命中既有域（custom），不做跨域判定"
        return [], info
    if not declared["pipelines"] and not declared["package"]:
        info["reason"] = ("产物未声明域（标题无「（Pxx）」、§0 无 active_pipeline/管线 Pxx）"
                          "——不判死；修复指引：让产物在标题或 §0 写明 active_pipeline")
        return [], info
    info["checked"] = True
    if declared["pipelines"]:
        if exp["pipeline"] in declared["pipelines"]:
            info["ok"] = True
            return [], info
        msg = ("跨域装配：需求域 %s（管线 %s）≠ 产物声明域（%s）"
               "（修复指引：按需求域重跑 `nf assemble \"<需求>\" --build --dest <目录>`；"
               "确要跨域混装须走组合包 references 白名单（01 §6 R1），不得直接混装）"
               % (exp["package"] or exp["pipeline"], exp["pipeline"],
                  "、".join(declared["pipelines"])))
        info["ok"] = False
        return [msg], info
    ok_pkgs = {exp["package"], PIPELINE_TO_PACKAGE.get(exp["pipeline"], "")}
    ok_pkgs.discard("")
    if declared["package"] in ok_pkgs:
        info["ok"] = True
        return [], info
    info["ok"] = False
    return [("跨域装配：需求域 %s（管线 %s）≠ 产物声明的包 %s"
             "（修复指引：按需求域重跑 `nf assemble \"<需求>\" --build`；"
             "跨域混装须走组合包 references 白名单，01 §6 R1）"
             % (exp["package"] or exp["pipeline"], exp["pipeline"], declared["package"]))], info


def _official_core_ids() -> List[str]:
    reg = json_doc.load(_ROOT / "desktop/src/core/registry.json", dict, what="desktop/src/core/regi"
        "stry.json")
    return [str(m["id"]) for m in reg.get("modules", [])]


def _yaml_module():
    """PyYAML 模块（**惰性**入口，见 core.lazy_yaml）；缺依赖 → None。

    审计 Y6（P1）：本模块此前在函数里裸写 import yaml，缺 PyYAML 时直接抛 ModuleNotFoundError，
    一路冒成「内部错误：[blocked] yaml」——绕过了仓库为这件事专门做的 lazy_yaml 降级约定
    （出声一次 + 回退子集口径）。
    """
    from core import lazy_yaml
    return lazy_yaml.module()


def _package_module_sets() -> Dict[str, List[str]]:
    yaml = _yaml_module()
    if yaml is None:                     # 缺依赖：按降级约定返回空集（lazy_yaml 已出声并给指引）
        return {}
    sets: Dict[str, List[str]] = {}
    for proto in sorted((_ROOT / "community").glob("*/protocol.yaml")):
        try:
            data = yaml.safe_load(proto.read_text(encoding="utf-8"))
            pkg = (data.get("package") or {}).get("id")
            mids = [(data.get("package") or {}).get("module_id_range") or []]
            if pkg:
                sets[str(pkg)] = [str(x) for x in mids[0]]
        except Exception:  # nosec B110/B112 —— 尽力而为：跳过不可读/不可解析项；该类缺口由对应门禁与 AUD-0016 静默跳过清单另行报出
            continue
    return sets


def clarify(requirement: str) -> Dict[str, Any]:
    """需求收敛漏斗：信息不足 → 澄清问句；足够 → 直接进 plan。"""
    req = requirement.strip()
    if not req:
        return {"status": "clarify", "requirement": req,
                "questions": ["请描述交付物：类型（技术文档/合规清单/研究报告/规格说明…）、"
                              "受众与验收判据各是什么？"]}
    p = plan(req)
    if p["matched"] or any(cue in req for cue in CUSTOM_CUES):
        return {"status": "ready", "requirement": req, "plan": p,
                "questions": []}
    return {
        "status": "clarify",
        "requirement": req,
        "questions": [
            "① 交付物类型：技术文档/合规清单/研究报告/规格说明/量化口径/叙事世界，还是自定义？",
            "② 受众：谁消费这份交付物、谁验收（人/团队/外部客户/agent）？",
            "③ 验收判据：必须成立哪些机检条款（结构八段/编号在册/决策句带引用/字段 schema）？",
        ],
    }


def dossier(requirement: str, plan_: Dict[str, Any],
            questions: Sequence[str] = (), answers: Sequence[str] = ()) -> str:
    """漏斗产出 → 需求档案（对齐 docs/需求收敛模板.md 八字段回填稿）。"""
    req = requirement.strip()
    status = "澄清中（nf assemble 已抛问句，待回填）" if questions else (
        "custom 用户自定义流" if not plan_.get("matched") else "preset 预设匹配")
    lines = [
        "需求澄清稿",
        "1. 一句话需求：%s" % req,
        "2. 背景与痛点：（待回填——为什么现在做 / 现有哪一环断了）",
        "3. 谁消费（决策人 / 外部方）：（待确认——作者 / agent 用户）",
        "4. 范围边界（做 / 不做）：%s" % status,
        "   领域判定：%s" % (
            "%s/%s" % (plan_.get("package"), plan_.get("pipeline"))
            if plan_.get("matched") else
            "未命中官方预设 → 用户自定义（可借用包：%s）"
            % ("、".join(plan_.get("known_packages") or []) or "—")),
        "   取件模块：%s" % "、".join(plan_.get("fetch_modules") or []),
        "5. 验收标准（可测断言）：nf assemble \"%s\" --check <out.md> 期望 PASS"
        "（八段骨架 / 编号在装配允许集 / 决策句带引用）" % req,
        "6. 风险与未知：关键词识别有界（未命中 ≠ 不适配，需回填确认）；"
        "用户自定义件须先落库登记（M91-M99 或 <独占类别>:Mxx 类内段 / 资产 900+ / 新 Pxx 避让层位 i"
            "d）验收才认；"
        "外部实证按 STRATEGY 封闭期冻结（NF-FIELD-001 素材缺位）",
        "7. 涉及协议 / 文件：docs/agent/agent_组装指令包_v0.2.md；%s 管线件；"
        "装配计划允许集 %d 模块；community/模板制作指令包.md（如需建自定义件）"
        % ("、".join(plan_.get("pipeline_files") or []) or "（待定）",
           len(plan_.get("allowed_module_ids") or [])),
        "8. 素材引用：仓库内完整版样本 / 资产键表；外部素材无则如实声明",
    ]
    if questions:
        lines.append("待澄清（nf assemble 问句）：")
        lines += ["  · %s" % q for q in questions]
    if answers:
        lines.append("澄清回填（--answer，已并入需求与档案）：")
        lines += ["  · %s" % a for a in answers]
    return "\n".join(lines) + "\n"


def plan(requirement: str) -> Dict[str, Any]:
    """需求 → 装配计划（预设包 + 取件清单）。"""
    req = requirement.strip()
    pkg: Optional[str] = None
    pipeline: Optional[str] = None
    for keys, hit in DOMAIN_MAP:
        if any(k in req for k in keys):
            pkg, pipeline = hit
            break
    modules: List[str] = []
    matched = bool(pkg)
    if pkg:
        proto = _ROOT / "community" / pkg / "protocol.yaml"
        if proto.is_file():
            try:
                _y = _yaml_module()
                data = _y.safe_load(proto.read_text(encoding="utf-8")) if _y else {}
                modules = [str(x) for x in (data.get("package") or {}).get("module_id_range") or []]
            except Exception:
                modules = []
    packages = _package_module_sets()
    if pkg is None or not matched:
        # 用户自定义/未命中：允许全域已登记模块（官方核心 + 各社区包），
        # 并给出自定义预留槽位；自定义件须先按模板落库登记，验收才认。
        for mids in packages.values():
            modules += mids
        modules = sorted(set(modules))
        known = sorted(packages)
    else:
        known = [pkg]
    all_registered = _official_core_ids()
    for mids in packages.values():
        all_registered += mids
    allowed = sorted(set(all_registered))
    if pipeline and pkg:
        pipeline_path = (_ROOT / "community" / pkg / "pipelines").glob("%s*.md" % pipeline)
        pipe_files = [p.relative_to(_ROOT).as_posix() for p in pipeline_path]
    else:
        pipe_files = []
    return {
        "requirement": req,
        "matched": matched,
        "package": pkg,
        "pipeline": pipeline,
        "pipeline_files": pipe_files,
        "fetch_modules": modules or [str(x) for x in _official_core_ids()],
        "allowed_module_ids": allowed,
        "known_packages": known,
        "status": "preset" if matched else "custom",
    }


def check(output_md: str, plan_: Dict[str, Any],
          expected_pipeline: Optional[str] = None) -> Tuple[List[str], Dict[str, int]]:
    """成品机器验收：跨域门 / 八段骨架 / 编号在允许集 / 决策句带引用 / 无编造编号。"""
    issues: List[str] = []
    dom_issues, dom_info = domain_issues(output_md, plan_, expected_pipeline)
    issues.extend(dom_issues)
    segs = {int(m.group(1)) for m in _SEG.finditer(output_md)}
    missing = [i for i in range(8) if i not in segs]
    if missing:
        issues.append("八段骨架缺段：##%s" % ", ".join(str(i) for i in missing))
    allowed = set(plan_.get("allowed_module_ids") or [])
    mentioned = set()
    _EXPL = ("残留", "不命中", "源编号", "未装配", "说明")
    narrative = {0, 1, 2}
    cur_seg = None
    in_code = False
    for line in output_md.splitlines():
        s = line.strip()
        if s.startswith("```"):
            in_code = not in_code
            continue
        if in_code:
            continue
        m = _SEG.match(line)
        if m:
            cur_seg = int(m.group(1))
            continue
        for tok in _MODULE.findall(line):
            mentioned.add(tok)
            if tok in allowed or tok.split(":", 1)[-1] in {
                    a.split(":", 1)[-1] for a in allowed}:
                continue
            if any(k in line for k in _EXPL):
                continue
            issues.append("编造/越界编号：%s（全库允许集外，且非残留/不命中说明）" % tok)
        if cur_seg not in narrative or s.startswith(("-", "*", "|")):
            continue
        for clause in re.split(r"[。！？；\n]+", line):
            clause = clause.strip()
            if not clause:
                continue
            if _DECISION.search(clause) and not _CITATION.search(clause) \
                    and not _MODULE.search(clause):
                issues.append("无引用决策句：%s" % clause[:60])
    stats = {
        "segments": len(segs),
        "modules_mentioned": len(mentioned),
        "allowed": len(allowed),
        "domain": dom_info,
    }
    return issues, stats
