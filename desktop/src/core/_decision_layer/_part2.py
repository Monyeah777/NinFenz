"""core.decision_layer 私有实现分片 2/2（对外只经 core.decision_layer 门面导入）： 等"""

from __future__ import annotations

import json
import time
import urllib.request
from typing import Any, Dict, List, Tuple

from core import json_doc

from ._part1 import (
    DECL_REL,
    PRIMITIVES,
    RESPONSE_SCHEMA,
    SCHEMA,
    DecideOptions,
    adapter_spec,
    decision_view,
    load_decl,
    normalize_probs,
    request_issue,
    response_issue,
    stub_decide,
)

#: 远端 JSON 响应上限（8 MiB）：端点由调用方给出，不能把无界响应读进内存。
MAX_REMOTE_JSON_BYTES = 8 * 1024 * 1024


def _read_json_response(resp) -> dict[str, Any]:
    raw = resp.read(MAX_REMOTE_JSON_BYTES + 1)
    if len(raw) > MAX_REMOTE_JSON_BYTES:
        raise ValueError(f"决策端点响应超过上限 {MAX_REMOTE_JSON_BYTES} 字节"
                         "（修复指引：端点须返回有界 JSON）")
    return json_doc.loads(raw.decode("utf-8"), dict, what="决策端点响应")


def _post_json(url: str, payload: Dict[str, Any], timeout: float) -> Dict[str, Any]:
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST",
                                headers={"Content-Type": "application/json"})
    if not str(url).startswith(("http://", "https://")):
        raise ValueError("只允许 http/https 端点（修复指引：端点须显式给 scheme）："
                         + repr(url))
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # nosec B310 —— 已在上方校验 scheme ∈ {http,https}；端点由调用方显式给出
        return _read_json_response(resp)


def systemone_decide(req: Dict[str, Any], endpoint: str,
                     timeout: float = 30.0) -> Dict[str, Any]:
    """本地 typed-decision 服务适配器（Jev / Laya 系：POST {state, questions}）。

    服务返回「声明键 + 概率」；本函数把它翻成 NF 应答形状（补 argmax/期望值），
    任何异常都向上抛给 `decide()` 做 fail-closed（本层不吞错、不猜测）。
    """
    raw = _post_json(endpoint, {"state": req.get("state"),
                                "questions": req.get("questions") or {}}, timeout)
    answers: Dict[str, Any] = {}
    raw_sums: Dict[str, float] = {}
    for name, q in (req.get("questions") or {}).items():
        node = raw.get(name) if isinstance(raw, dict) else None
        if isinstance(node, dict) and "probs" in node:
            probs = [float(p) for p in node["probs"]]
        elif isinstance(node, dict) and isinstance(node.get("probabilities"), dict):
            probs = list(node["probabilities"].values())
        else:
            raise ValueError("服务未返回问题 %s 的概率分布" % name)
        ptype = q.get("type")
        if ptype in ("choice", "score"):
            raw_sums[name] = sum(probs)
            probs = normalize_probs(probs)      # 舍入容差内的归一（原始和见 meta）
        if ptype == "choice":
            opts = [str(o) for o in q.get("options") or []]
            if len(probs) != len(opts):
                raise ValueError("问题 %s 概率长度与候选数不符（%d ≠ %d）"
                                 % (name, len(probs), len(opts)))
            answers[name] = {"type": "choice", "options": opts, "probs": probs,
                             "argmax": opts[probs.index(max(probs))]}
        elif ptype == "score":
            levels = [str(l) for l in q.get("levels") or []]
            if len(probs) != len(levels):
                raise ValueError("问题 %s 概率长度与等级数不符" % name)
            answers[name] = {"type": "score", "levels": levels, "probs": probs,
                             "value": sum((i + 1) * p for i, p in enumerate(probs))}
        else:
            answers[name] = {"type": "noul", "p": float(probs[-1])}
    return {"schema": RESPONSE_SCHEMA, "status": "ok", "answers": answers,
            "meta": {"adapter": "systemone-http", "calibrated": True, "non_gate": True,
                     "endpoint": endpoint,
                     "model": str((raw or {}).get("_meta", {}).get("model")
                                  or (raw or {}).get("model") or "unknown"),
                     "raw_prob_sums": raw_sums,
                     "confidence": {k: v.get("confidence")
                                    for k, v in (raw or {}).items()
                                    if isinstance(v, dict) and "confidence" in v},
                     "usage": (raw or {}).get("_meta", {}).get("usage")}}


def _choice_answer(q: dict, probs: list[float]) -> dict:
    opts = [str(o) for o in q.get("options") or []]
    return {"type": "choice", "options": opts, "probs": probs,
            "argmax": opts[probs.index(max(probs))]}


def _score_answer(q: dict, probs: list[float]) -> dict:
    levels = [str(l) for l in q.get("levels") or []]
    return {"type": "score", "levels": levels, "probs": probs,
            "value": sum((i + 1) * p for i, p in enumerate(probs))}


def _answer_for(q: dict, probs: list[float]) -> dict:
    """问题类型 → 应答条目（choice / score / noul 三型封闭集）。"""
    ptype = q.get("type")
    if ptype == "choice":
        return _choice_answer(q, probs)
    if ptype == "score":
        return _score_answer(q, probs)
    return {"type": "noul", "p": probs[-1]}


def openai_json_decide(req: Dict[str, Any], endpoint: str, model: str,
                       api_key: str = "", timeout: float = 60.0) -> Dict[str, Any]:
    """任一聊天模型 + 受限 JSON 作答（calibrated=false：自报概率不可当校准概率）。"""
    prompt = ("你是决策层：只回答给定问题，不得自造候选。state:\n%s\n\nquestions:\n%s\n\n"
              "只输出 JSON：{问题名: {\"probs\": [...]}}（概率和为 1）"
              % (req.get("state"), json.dumps(req.get("questions") or {}, ensure_ascii=False)))
    payload = {"model": model, "messages": [{"role": "user", "content": prompt}],
               "temperature": 0}
    headers = {"Content-Type": "application/json"}
    if not str(endpoint).startswith(("http://", "https://")):
        raise ValueError("只允许 http/https 端点（修复指引：端点须显式给 scheme）："
                         + repr(endpoint))
    if api_key:
        headers["Authorization"] = "Bearer %s" % api_key
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    r = urllib.request.Request(endpoint, data=data, method="POST", headers=headers)
    with urllib.request.urlopen(r, timeout=timeout) as resp:  # nosec B310 —— 已在上方校验 scheme ∈ {http,https}；端点由调用方显式给出
        body = _read_json_response(resp)
    text = body["choices"][0]["message"]["content"]
    raw = json_doc.loads(text, dict, what="决策模型 JSON 文本")
    answers: Dict[str, Any] = {}
    for name, q in (req.get("questions") or {}).items():
        answers[name] = _answer_for(q, [float(p) for p in raw[name]["probs"]])
    return {"schema": RESPONSE_SCHEMA, "status": "ok", "answers": answers,
            "meta": {"adapter": "openai-json", "calibrated": False, "non_gate": True,
                     "model": model}}


def _run_adapter(adapter: str, req: dict, endpoint: str, model: str,
                 api_key: str, timeout: float) -> dict:
    """按适配器名路由；未实现/缺参 → ValueError（由 decide 统一 fail-closed）。"""
    if adapter == "stub":
        return stub_decide(req)
    if adapter == "systemone-http":
        if not endpoint:
            raise ValueError("systemone-http 需 --endpoint（本地 typed-decision 服务地址）")
        return systemone_decide(req, endpoint, timeout)
    if adapter == "openai-json":
        if not endpoint or not model:
            raise ValueError("openai-json 需 --endpoint 与 --model")
        return openai_json_decide(req, endpoint, model, api_key, timeout)
    raise ValueError("适配器 %s 未实现（登记面已声明：%s）" % (adapter, DECL_REL))


def decide(req: Dict[str, Any], opts: DecideOptions | None = None) -> Dict[str, Any]:
    """统一入口：形状校验 → 适配器 → 应答校验；任一环节失败 → abstained（fail-closed）。"""

    opts = opts if opts is not None else DecideOptions()
    adapter = opts.adapter
    endpoint = opts.endpoint
    model = opts.model
    api_key = opts.api_key
    timeout = opts.timeout
    root = opts.root
    bad = request_issue(req)
    if bad:
        return {"schema": RESPONSE_SCHEMA, "status": "abstained",
                "answers": {}, "reason": "请求不合规：%s" % bad,
                "meta": {"adapter": adapter, "calibrated": False, "non_gate": True}}
    spec = adapter_spec(root, adapter)
    if not spec:
        return {"schema": RESPONSE_SCHEMA, "status": "abstained", "answers": {},
                "reason": "未登记的适配器：%s（登记面 %s）" % (adapter, DECL_REL),
                "meta": {"adapter": adapter, "calibrated": False, "non_gate": True}}
    started = time.monotonic()
    try:
        out = _run_adapter(adapter, req, endpoint, model, api_key, timeout)
    except Exception as exc:  # 网络/解析/服务异常一律 fail-closed
        return {"schema": RESPONSE_SCHEMA, "status": "abstained", "answers": {},
                "reason": "adapter %s 不可用：%s: %s" % (adapter, type(exc).__name__,
                                                         str(exc)[:140]),
                "meta": {"adapter": adapter, "calibrated": bool(spec.get("calibrated")),
                         "non_gate": True}}
    out.setdefault("meta", {})
    out["meta"]["latency_ms"] = int((time.monotonic() - started) * 1000)
    issue = response_issue(out, req)
    if issue:
        return {"schema": RESPONSE_SCHEMA, "status": "abstained", "answers": {},
                "reason": "adapter %s 输出不合 schema：%s" % (adapter, issue),
                "meta": {"adapter": adapter, "calibrated": bool(spec.get("calibrated")),
                         "non_gate": True}}
    return out


# ---------------------------------------------------------------- 面体检

def scan(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """决策层面体检（离线）：声明完整 + 适配器诚实标注 + stub 确定性 + fail-closed。"""
    issues: List[str] = []
    decl = load_decl(root)
    if not decl:
        return ["缺决策层声明 %s（修复指引：补声明件再跑门禁）" % DECL_REL], {}
    if decl.get("schema") != SCHEMA:
        issues.append("%s schema 不匹配（期望 %s）" % (DECL_REL, SCHEMA))
    prims = decl.get("primitives") or {}
    for p in PRIMITIVES:
        if p not in prims:
            issues.append("声明缺原语 %s（三原语齐全才谈得上类型化决策）" % p)
    adapters = decl.get("adapters") or []
    if not any(a.get("id") == "stub" for a in adapters):
        issues.append("缺 stub 适配器（门禁必须有一条离线确定性路径）")
    for a in adapters:
        aid = str(a.get("id") or "")
        for k in ("id", "kind", "in_gate_path", "calibrated"):
            if k not in a:
                issues.append("适配器 %s 缺字段 %s" % (aid or "?", k))
        if not str(a.get("note") or "").strip():
            issues.append("适配器 %s 缺 note（能力与边界须自述）" % aid)
        if a.get("in_gate_path") and aid != "stub":
            issues.append("适配器 %s 声明 in_gate_path 却非 stub"
                          "（门禁只许离线确定性路径）" % aid)
    cands = decl.get("candidates") or []
    if not cands:
        issues.append("候选模型清单为空（决策层没有可拉取的模型就只是空壳）")
    for c in cands:
        cid = str(c.get("id") or "")
        for k in ("id", "source", "license", "evidence", "pulled"):
            if k not in c:
                issues.append("候选 %s 缺字段 %s（来源/许可/实证/是否已拉取都要写）" % (cid or "?",
 k))
        if not isinstance(c.get("pulled"), bool):
            issues.append("候选 %s 的 pulled 须为布尔（状态不许含糊）" % cid)
        elif c.get("pulled") is True:
            # 拉取是**显式动作**：一旦声明已拉取，必须自带可追溯的本地证据
            local = c.get("local") or {}
            for k in ("how", "runtime", "served_by"):
                if not str(local.get(k) or "").strip():
                    issues.append("候选 %s 声明 pulled=true 却缺 local.%s"
                                  "（修复指引：写明怎么拉的、什么运行时、由谁服务）" % (cid, k))
    if not (decl.get("boundaries") or []):
        issues.append("声明缺 boundaries（不执行动作/不生成正文/不入门禁 等边界须成文）")

    req = {"state": "雨天走廊 与 校园情感 场景；候选：P02 校园情感流 / P03 西幻生存流",
           "questions": {
               "pipeline": {"type": "choice",
                            "options": ["P02 校园情感流", "P03 西幻生存流"]},
               "multilingual": {"type": "noul", "true_hints": ["中文", "多语"]},
               "risk": {"type": "score", "levels": ["低", "中", "高"]}}}
    if request_issue(req):
        issues.append("内部样例请求不合规：%s" % request_issue(req))
    a1 = decide(req, opts=DecideOptions(adapter='stub', root=root))
    a2 = decide(req, opts=DecideOptions(adapter='stub', root=root))
    # 比「决策内容视图」而非整份应答：`meta.latency_ms` 是墙钟观测，差值 ≥1 ms 就判死人
    # （2026-09-29 实测假红，见 decision_view 的说明）。
    if decision_view(a1) != decision_view(a2):
        issues.append("stub 非确定性（同输入两次结果不一致）")
    if a1.get("status") != "ok":
        issues.append("stub 样例未产出 ok：%s" % a1.get("reason"))
    issue = response_issue(a1, req)
    if issue:
        issues.append("stub 应答不合 schema：%s" % issue)
    if (a1.get("meta") or {}).get("calibrated") is not False:
        issues.append("stub 应答须自称 calibrated=false（排序信号不是概率）")
    # fail-closed：未登记适配器 / 缺 endpoint / 请求不合规 → abstained
    cases: List[Tuple[str, Dict[str, Any]]] = [("未登记适配器", {"adapter": "ghost"}),
                                             ("缺 endpoint", {"adapter": "systemone-http"})]
    for label, kwargs in cases:
        out = decide(req, opts=DecideOptions(root=root, **kwargs))
        if out.get("status") != "abstained" or not out.get("reason"):
            issues.append("%s 未 fail-closed（应 abstained + reason）" % label)
    bad = decide({'questions': {}}, opts=DecideOptions(adapter='stub', root=root))
    if bad.get("status") != "abstained":
        issues.append("不合规请求未 fail-closed")
    if response_issue({"schema": RESPONSE_SCHEMA, "status": "ok",
                       "answers": {"risk": {"type": "score", "probs": [0.2, 0.2],
                                            "value": 1.5}},
                       "meta": {"calibrated": True, "non_gate": True}}, req) == "":
        issues.append("概率和不等于 1 的应答竟通过校验（判据失效）")
    stats = {"primitives": len(prims), "adapters": len(adapters),
             "candidates": len(cands), "issueless_stub": a1.get("status") == "ok",
             "issues": len(issues)}
    return issues, stats


def summary(stats: Dict[str, Any]) -> str:
    return ("原语 %(primitives)d · 适配器 %(adapters)d · 候选模型 %(candidates)d · "
            "stub %(issueless_stub)s" % stats)
