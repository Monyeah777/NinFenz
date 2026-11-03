"""多平台 AI 内容标识规则包与 fail-closed 评估（纯标准库）。

定位
----
`checker.check_file()` 产出的是**文件级**五段报告（A 显式标识 / B 隐式字段 /
C 安全防护 / D 内容绑定 / E 备案材料）。本模块把抖音、微信视频号、小红书、
Apple App Store、欧盟 AI Act 的公开规则整理成**平台规则包**，再把同一份报告
映射成平台维度的逐条判定，回答「这份内容放到某平台，规则层面还差什么」。

纪律
----
- 纯标准库，无网络请求、无第三方 import；规则数据是静态常量，审计时逐条可追。
- **不编造**：没有一手来源（官方规则页 / 平台公告 / 法规原文）的条目必须
  ``verified=False``，requirement 里写明「待核实」，评估时一律 ``UNKNOWN``。
  未核实规则**绝不能**因为目标分段是 PASS 就被判成 PASS。
- 判定 fail-closed：有 FAIL → FAIL；否则有 UNKNOWN → UNKNOWN；否则有 WARN →
  WARN；全 PASS 才 PASS。空规则集 / 空报告分段也按 UNKNOWN 处理，不默认放行。
- 本模块不修改输入报告；``evaluate()`` 只读取 ``report["sections"]`` 的
  ``status`` 字段，返回新字典。

规则来源（2026-11-02 核对）
--------------------------
- 抖音规则中心公告： ``https://www.douyin.com/rule/billboard?id=1242800000049``
  与 ``...?id=1242800000050``（页面可访问；正文为图片，按公告标题与平台规则
  中心入口归纳，未逐字引用）。
- 《微信视频号运营规范》6.4：
  ``http://short.weixin.qq.com/cgi-bin/readtemplate?lang=zh_CN&t=weixin_agreement&s=video``
- 小红书社区规则页： ``https://www.xiaohongshu.com/crown/community/rules``
  （入口可访问，但正文动态渲染；条款文本未取得，故相关条目 verified=False）。
- Apple App Review Guidelines：
  ``https://developer.apple.com/app-store/review/guidelines/``
  （1.2 / 2.3 / 5.1.2(i)，2026-10-16 版）。
- 欧盟 AI Act 第 50 条：
  ``https://eur-lex.europa.eu/eli/reg/2024/1689/oj``
  （EUR-Lex 官方合并文本；条文经公开镜像交叉核对，未逐字引用）。
"""

from __future__ import annotations

__all__ = ["PLATFORMS", "SCHEMA", "platforms", "evaluate", "selfcheck"]

SCHEMA = "nf-label-platform-eval/1"
SECTIONS = ("A", "B", "C", "D", "E")
SECTION_TITLES = {
    "A": "显式标识",
    "B": "隐式标识字段",
    "C": "安全防护信息",
    "D": "内容绑定",
    "E": "备案材料",
}
VALID_MAPS = frozenset(SECTIONS + ("ALL",))
VERDICTS = ("PASS", "WARN", "FAIL", "UNKNOWN")

_REQUIRED_PLATFORM_KEYS = ("name", "summary", "checks", "sources")
_REQUIRED_CHECK_KEYS = ("id", "requirement", "maps_to", "source", "verified",
                        "checked_at")


def _check(cid, requirement, maps_to, source, verified,
           checked_at="2026-11-02"):
    """构造一条规则；字段固定，避免后续随手加字段破坏可审计结构。"""
    return {
        "id": cid,
        "requirement": requirement,
        "maps_to": maps_to,
        "source": source,
        "verified": verified,
        "checked_at": checked_at,
    }


#: 平台规则包。id 是稳定键（供 API/CLI 使用），name 是展示名。
PLATFORMS = {
    "douyin": {
        "name": "抖音",
        "summary": (
            "抖音规则中心公开的《人工智能生成内容的平台规范暨行业倡议》与"
            "《人工智能生成内容标识的水印与元数据规范》（2023-05-09）要求对"
            "AI 生成内容显著标识，并规范标识水印与元数据；平台提供统一标识能力。"
        ),
        "checks": [
            _check(
                "douyin.explicit_label",
                "发布由 AI 生成或合成的视频、图文时，应以显著方式添加“由 AI 生成”"
                "等标识，帮助其他用户区分虚拟与现实，避免误导。",
                "A",
                "https://www.douyin.com/rule/billboard?id=1242800000049",
                True,
            ),
            _check(
                "douyin.metadata",
                "平台对 AI 生成内容的标识水印与元数据提出规范；创作者与上传工具"
                "应按规范保留可读、可核验的标识元数据，不得让标识在转存中丢失。",
                "B",
                "https://www.douyin.com/rule/billboard?id=1242800000050",
                True,
            ),
        ],
        "sources": [
            "https://www.douyin.com/rule/billboard?id=1242800000049",
            "https://www.douyin.com/rule/billboard?id=1242800000050",
        ],
    },
    "wechat_channels": {
        "name": "微信视频号",
        "summary": (
            "《微信视频号运营规范》6.4：用户发布利用深度学习、虚拟现实、生成式"
            "人工智能等新技术生成或合成的非真实音视频，应以显著方式标识；平台"
            "有权按法律法规要求添加显式标识和隐式标识。"
        ),
        "checks": [
            _check(
                "wechat_channels.explicit_label",
                "发布生成或合成的非真实音视频、或剧情演绎的虚构内容时，应以显著"
                "方式标识，避免其他用户误认或混淆。",
                "A",
                "http://short.weixin.qq.com/cgi-bin/readtemplate?lang=zh_CN&t=weixin_agreement&s=video",
                True,
            ),
            _check(
                "wechat_channels.implicit_label",
                "平台有权按法律法规要求对相应内容添加显式标识和隐式标识，并以"
                "显著提示帮助用户清晰辨识；创作者应保留平台标识，不得隐匿。",
                "B",
                "http://short.weixin.qq.com/cgi-bin/readtemplate?lang=zh_CN&t=weixin_agreement&s=video",
                True,
            ),
        ],
        "sources": [
            "http://short.weixin.qq.com/cgi-bin/readtemplate?lang=zh_CN&t=weixin_agreement&s=video",
        ],
    },
    "xiaohongshu": {
        "name": "小红书",
        "summary": (
            "未核实：小红书社区规则页入口可访问，但正文为动态渲染，本次未取得可"
            "静态复核的 AI 标识条款文本。下列条目均标为待核实，评估时按 UNKNOWN"
            "处理，不得据此判定 PASS。"
        ),
        "checks": [
            _check(
                "xiaohongshu.active_label",
                "待核实：发布由 AI 生成或经 AI 润色的图文、视频时，应主动声明或"
                "添加 AI 标识；未主动标识的内容，平台识别后可能统一添加标识。",
                "A",
                "",
                False,
            ),
            _check(
                "xiaohongshu.no_remove",
                "待核实：不得删除、篡改、伪造或隐匿平台添加的 AI 标识；具体条款"
                "与处置方式以小红书官方规则页/公告为准。",
                "B",
                "",
                False,
            ),
        ],
        "sources": [
            "https://www.xiaohongshu.com/crown/community/rules",
        ],
    },
    "apple_app_store": {
        "name": "Apple App Store",
        "summary": (
            "《App Review Guidelines》（2026-10-16 版）：1.2 要求含用户生成内容"
            "或 AI 内容创作能力的 App 具备过滤、举报、拉黑与公开联系方式；2.3 要求"
            "元数据与审核备注准确描述核心体验；5.1.2(i) 要求向第三方 AI 共享个人"
            "数据前明确披露并取得明示同意。"
        ),
        "checks": [
            _check(
                "apple_app_store.ugc_safety",
                "Guideline 1.2：允许用户创建、生成、上传、分享内容的 App（含 AI"
                "内容创作类）必须具备不良内容过滤、举报响应、拉黑滥用用户、公开"
                "联系方式四项机制。",
                "C",
                "https://developer.apple.com/app-store/review/guidelines/",
                True,
            ),
            _check(
                "apple_app_store.accurate_metadata",
                "Guideline 2.3 / 2.3.1(a)：App 元数据、截屏、预览与审核备注须准确、"
                "具体地描述 AI 功能与内容，不得用笼统描述或误导性宣传。",
                "E",
                "https://developer.apple.com/app-store/review/guidelines/",
                True,
            ),
            _check(
                "apple_app_store.third_party_ai",
                "Guideline 5.1.2(i)：向第三方（包括第三方 AI）共享个人数据前，须"
                "明确披露共享对象与用途并取得用户明示同意。",
                "C",
                "https://developer.apple.com/app-store/review/guidelines/",
                True,
            ),
        ],
        "sources": [
            "https://developer.apple.com/app-store/review/guidelines/",
        ],
    },
    "eu_ai_act": {
        "name": "欧盟 AI Act",
        "summary": (
            "欧盟《人工智能法案》（Regulation (EU) 2024/1689）第 50 条透明度义务："
            "生成合成内容的提供者须以机器可读方式标记输出；深度伪造部署者须披露；"
            "用于向公众告知公共议题的生成文本须披露；信息应在首次交互或接触时以"
            "清晰、可区分的方式提供。"
        ),
        "checks": [
            _check(
                "eu_ai_act.machine_readable",
                "第 50(2) 条：生成合成音频、图像、视频或文本的 AI 系统提供者，应"
                "确保输出以机器可读格式标记，并可被检测为人工生成或操纵。",
                "B",
                "https://eur-lex.europa.eu/eli/reg/2024/1689/oj",
                True,
            ),
            _check(
                "eu_ai_act.deepfake",
                "第 50(4) 条：部署生成或操纵图像、音频、视频且构成深度伪造的，应"
                "披露内容系人工生成或操纵；艺术、创作、讽刺、虚构类作品可在不妨碍"
                "欣赏的前提下适当披露。",
                "A",
                "https://eur-lex.europa.eu/eli/reg/2024/1689/oj",
                True,
            ),
            _check(
                "eu_ai_act.public_interest_text",
                "第 50(4) 条：部署生成或操纵文本并用于向公众告知公共议题的，应披露"
                "文本系人工生成或操纵；经人工审核、编辑并承担编辑责任的情形除外。",
                "A",
                "https://eur-lex.europa.eu/eli/reg/2024/1689/oj",
                True,
            ),
            _check(
                "eu_ai_act.clear_and_timely",
                "第 50(5) 条：第 50(1)–(4) 条要求的信息应在首次交互或接触时，以清晰、"
                "可区分的方式提供，并符合适用的无障碍要求。",
                "ALL",
                "https://eur-lex.europa.eu/eli/reg/2024/1689/oj",
                True,
            ),
        ],
        "sources": [
            "https://eur-lex.europa.eu/eli/reg/2024/1689/oj",
        ],
    },
}


def platforms():
    """返回平台 id 列表（稳定顺序；调用方不得依赖可变内部对象）。"""
    return list(PLATFORMS.keys())


def _resolve_platform(platform):
    """把 id 或展示名解析为 id；未知平台抛 ValueError（带修复指引）。"""
    if not isinstance(platform, str) or not platform.strip():
        raise ValueError(
            "platform 必须是非空字符串（修复指引：先调用 platforms() 查看可用 id；"
            "示例：evaluate(report, 'apple_app_store')）"
        )
    key = platform.strip()
    if key in PLATFORMS:
        return key
    for pid, pack in PLATFORMS.items():
        if pack.get("name") == key:
            return pid
    raise ValueError(
        "未知平台 %r（修复指引：先调用 platforms() 查看可用 id，再按返回的 id "
        "重试；示例：platforms() -> %s）" % (platform, platforms())
    )


def _section_status(report, key):
    """读取报告分段状态；缺失/类型不符返回 None（调用方按 UNKNOWN 处理）。"""
    sections = report.get("sections")
    if not isinstance(sections, dict):
        return None
    sec = sections.get(key)
    if not isinstance(sec, dict):
        return None
    status = sec.get("status")
    if not isinstance(status, str):
        return None
    return status.strip().upper()


def _combine_statuses(statuses):
    """把若干分段状态合并为一个逐条判定；空集合/未知状态按 UNKNOWN。"""
    if not statuses:
        return "UNKNOWN"
    if "FAIL" in statuses:
        return "FAIL"
    if any(s not in ("PASS", "WARN") for s in statuses):
        return "UNKNOWN"
    if "WARN" in statuses:
        return "WARN"
    return "PASS"


def _verdict_for_check(check, report):
    """返回 (verdict, reason, target_statuses)。

    未核实/无来源的规则**先于**报告判定，确保不会被 PASS 分段“洗白”。
    """
    if not check.get("verified"):
        return (
            "UNKNOWN",
            "规则未核实（verified=False），按 fail-closed 记 UNKNOWN；"
            "修复指引：补一手来源、核对条款后把 verified 改为 True 再评估。",
            {},
        )
    if not str(check.get("source") or "").strip():
        return (
            "UNKNOWN",
            "规则缺少 source URL，按未核实处理；修复指引：补官方/平台规则页 URL "
            "并重跑 selfcheck()。",
            {},
        )
    maps_to = check.get("maps_to")
    targets = SECTIONS if maps_to == "ALL" else (maps_to,)
    statuses = {}
    for key in targets:
        statuses[key] = _section_status(report, key)
    verdict = _combine_statuses(list(statuses.values()))
    detail = "、".join("%s=%s" % (k, v if v is not None else "MISSING")
                       for k, v in statuses.items())
    missing = [k for k, v in statuses.items() if v is None]
    if verdict == "FAIL":
        # 已有分段 FAIL 时优先判 FAIL：缺失其它分段不能把已观察到的失败洗成 UNKNOWN。
        return "FAIL", "分段状态 %s → FAIL。" % detail, statuses
    if missing:
        return (
            "UNKNOWN",
            "报告缺少分段 %s，无法映射；修复指引：先跑 checker.check_file() 生成"
            "完整五段报告（A–E）再评估。" % "、".join(missing),
            statuses,
        )
    if verdict == "UNKNOWN":
        reason = "分段状态 %s 无法给出 PASS/WARN/FAIL（NA/未知），按 UNKNOWN 处理。" % detail
    else:
        reason = "分段状态 %s → %s。" % (detail, verdict)
    return verdict, reason, statuses


def evaluate(report, platform):
    """评估一份标识报告在指定平台规则下的逐条判定与总体结论。

    schema = ``nf-label-platform-eval/1``；总体 fail-closed：
    任一 FAIL → FAIL；否则任一 UNKNOWN → UNKNOWN；否则任一 WARN → WARN；
    全部 PASS 才 PASS。
    """
    pid = _resolve_platform(platform)
    if not isinstance(report, dict):
        raise ValueError(
            "report 必须是字典（修复指引：先调用 checker.check_file() 生成报告；"
            "示例：evaluate({'sections': {'A': {'status': 'PASS'}}}, 'apple_app_store')）"
        )
    if not isinstance(report.get("sections"), dict):
        raise ValueError(
            "report 缺少 sections 字典（修复指引：先跑 checker.check_file()；"
            "示例：report['sections']['A']['status'] == 'PASS'）"
        )
    pack = PLATFORMS[pid]
    rows = []
    counts = {name: 0 for name in VERDICTS}
    for check in pack.get("checks", []):
        verdict, reason, statuses = _verdict_for_check(check, report)
        counts[verdict] += 1
        rows.append({
            "id": check.get("id", ""),
            "requirement": check.get("requirement", ""),
            "maps_to": check.get("maps_to", ""),
            "verdict": verdict,
            "reason": reason,
            "target_statuses": statuses,
            "source": check.get("source", ""),
            "verified": bool(check.get("verified")),
            "checked_at": check.get("checked_at", ""),
        })
    if not rows:
        overall = "UNKNOWN"
    elif counts["FAIL"]:
        overall = "FAIL"
    elif counts["UNKNOWN"]:
        overall = "UNKNOWN"
    elif counts["WARN"]:
        overall = "WARN"
    else:
        overall = "PASS"
    notes = []
    if any(not row["verified"] for row in rows):
        notes.append("含未核实规则：已按 UNKNOWN 处理，未计入 PASS。")
    if not rows:
        notes.append("规则包为空：按 fail-closed 记 UNKNOWN。")
    return {
        "schema": SCHEMA,
        "platform": pid,
        "platform_name": pack.get("name", ""),
        "report_sections": {key: _section_status(report, key) or "MISSING"
                            for key in SECTIONS},
        "checks": rows,
        "summary": counts,
        "overall": overall,
        "notes": notes,
    }


def _is_url(value):
    return isinstance(value, str) and (
        value.startswith("https://") or value.startswith("http://")
    )


def _rule_issues(where, check, sources, seen):
    """单条规则的结构体检；拆出后每条判据都在 25 圈复杂度以内。"""
    issues = []
    if not isinstance(check, dict):
        return ["%s：规则不是字典" % where]
    lack = [key for key in _REQUIRED_CHECK_KEYS if key not in check]
    if lack:
        return ["%s：缺字段 %s" % (where, "、".join(lack))]
    cid = check.get("id")
    if not isinstance(cid, str) or not cid.strip():
        issues.append("%s：id 必须是非空字符串" % where)
    elif cid in seen:
        issues.append("%s：id 重复 %r" % (where, cid))
    else:
        seen.add(cid)
    requirement = check.get("requirement")
    if not isinstance(requirement, str) or not requirement.strip():
        issues.append("%s：requirement 必须是非空字符串" % where)
    maps_to = check.get("maps_to")
    if maps_to not in VALID_MAPS:
        issues.append("%s：maps_to=%r 非法（应为 A/B/C/D/E/ALL）" % (where, maps_to))
    source = check.get("source")
    if not isinstance(source, str):
        issues.append("%s：source 必须是字符串（可为空）" % where)
    verified = check.get("verified")
    if not isinstance(verified, bool):
        issues.append("%s：verified 必须是 bool" % where)
    elif verified:
        if not _is_url(source):
            issues.append("%s：verified=True 但 source 不是 http(s) URL" % where)
        elif sources and source not in sources:
            issues.append("%s：verified=True 但 source 未登记在平台 sources" % where)
        if "待核实" in str(requirement or ""):
            issues.append("%s：verified=True 的 requirement 不应再写“待核实”" % where)
    elif "待核实" not in str(requirement or ""):
        issues.append("%s：verified=False 的 requirement 必须标注“待核实”" % where)
    checked_at = check.get("checked_at")
    if not isinstance(checked_at, str) or not checked_at.strip():
        issues.append("%s：checked_at 必须是非空字符串" % where)
    return issues


def _platform_issues(pid, pack):
    """结构体检：返回中文问题列表；空列表 = 该平台规则包合格。"""
    issues = []
    if not isinstance(pack, dict):
        return ["%s：规则包不是字典（应为 name/summary/checks/sources）" % pid]
    missing = [key for key in _REQUIRED_PLATFORM_KEYS if key not in pack]
    if missing:
        issues.append("%s：缺字段 %s" % (pid, "、".join(missing)))
    name = pack.get("name")
    if not isinstance(name, str) or not name.strip():
        issues.append("%s：name 必须是非空字符串" % pid)
    summary = pack.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        issues.append("%s：summary 必须是非空字符串" % pid)
    sources = pack.get("sources")
    if not isinstance(sources, list):
        issues.append("%s：sources 必须是 URL 列表" % pid)
        sources = []
    else:
        for url in sources:
            if not _is_url(url):
                issues.append("%s：sources 含非 http(s) URL %r" % (pid, url))
    checks = pack.get("checks")
    if not isinstance(checks, list) or not checks:
        issues.append("%s：checks 必须是非空列表" % pid)
        return issues
    seen = set()
    for index, check in enumerate(checks):
        issues.extend(_rule_issues("%s.checks[%d]" % (pid, index),
                                   check, sources, seen))
    return issues


def selfcheck():
    """规则包自检 → [(检查项, 是否通过, 中文说明), ...]。

    覆盖：结构字段、五平台在场、maps_to 合法、verified 与 source 一致性，
    以及「有非空 source 的规则条数 / 平台 sources 非空数」两项统计。
    """
    rows = []
    if not isinstance(PLATFORMS, dict):
        return [("platforms-present", False, "PLATFORMS 不是字典")]
    expected = ["douyin", "wechat_channels", "xiaohongshu",
                "apple_app_store", "eu_ai_act"]
    present = list(PLATFORMS.keys())
    ok = len(present) == 5 and set(present) == set(expected)
    rows.append((
        "platforms-present",
        ok,
        "平台 id：%s（应为 %s）" % ("、".join(present), "、".join(expected)),
    ))

    per_issues = {}
    all_issues = []
    for pid, pack in PLATFORMS.items():
        issues = _platform_issues(pid, pack)
        per_issues[pid] = issues
        all_issues.extend(issues)
    rows.append((
        "structure",
        not all_issues,
        "结构合格：5 个平台、字段/类型/maps_to 均合法" if not all_issues
        else "；".join(all_issues),
    ))

    total = 0
    with_source = 0
    platforms_with_sources = 0
    inconsistent = []
    for pid, pack in PLATFORMS.items():
        checks = pack.get("checks") if isinstance(pack, dict) else []
        checks = checks if isinstance(checks, list) else []
        total += len(checks)
        local_with_source = 0
        for check in checks:
            if not isinstance(check, dict):
                continue
            source = check.get("source")
            if isinstance(source, str) and source.strip():
                local_with_source += 1
            verified = check.get("verified")
            requirement = str(check.get("requirement") or "")
            if verified is True and not _is_url(source):
                inconsistent.append("%s/%s" % (pid, check.get("id", "?")))
            if verified is False and "待核实" not in requirement:
                inconsistent.append("%s/%s" % (pid, check.get("id", "?")))
        with_source += local_with_source
        sources = pack.get("sources") if isinstance(pack, dict) else []
        if isinstance(sources, list) and sources:
            platforms_with_sources += 1
        rows.append((
            "platform:%s" % pid,
            not per_issues.get(pid),
            "%s：规则 %d 条，带来源 %d 条，平台 sources %d 个"
            % (pack.get("name", pid) if isinstance(pack, dict) else pid,
               len(checks), local_with_source,
               len(sources) if isinstance(sources, list) else 0),
        ))
    rows.append((
        "source-coverage",
        total > 0,
        "规则带非空 source %d/%d；平台 sources 非空 %d/%d"
        % (with_source, total, platforms_with_sources, len(PLATFORMS)),
    ))
    rows.append((
        "verified-source-consistency",
        not inconsistent,
        "verified=True 均有 source；verified=False 均标注“待核实”"
        if not inconsistent else "以下条目不一致：%s" % "、".join(inconsistent),
    ))
    return rows
