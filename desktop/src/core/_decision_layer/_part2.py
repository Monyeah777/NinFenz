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


def _prob_dist(name: str, node: Any) -> List[float]:
    """服务返回的单问题概率列表（两种键形状）；缺失即抛 ValueError。"""
    if isinstance(node, dict) and "probs" in node:
        return [float(p) for p in node["probs"]]
    if isinstance(node, dict) and isinstance(node.get("probabilities"), dict):
        return list(node["probabilities"].values())
    raise ValueError("服务未返回问题 %s 的概率分布" % name)


def _answer_entry(name: str, q: dict, probs: List[float],
                  raw_sums: Dict[str, float]) -> dict:
    """单问题 → 应答条目（choice/score 先校验长度并按容差归一，原始和记 meta）。"""
    ptype = q.get("type")
    if ptype in ("choice", "score"):
        raw_sums[name] = sum(probs)
        probs = normalize_probs(probs)      # 舍入容差内的归一（原始和见 meta）
    if ptype == "choice" and len(probs) != len(q.get("options") or []):
        raise ValueError("问题 %s 概率长度与候选数不符（%d ≠ %d）"
                         % (name, len(probs), len(q.get("options") or [])))
    if ptype == "score" and len(probs) != len(q.get("levels") or []):
        raise ValueError("问题 %s 概率长度与等级数不符" % name)
    return _answer_for(q, probs)


def _systemone_meta(raw: Any, endpoint: str,
                    raw_sums: Dict[str, float]) -> Dict[str, Any]:
    """应答元数据（模型名 / 原始概率和 / 逐项 confidence / 用量）。"""
    return {"adapter": "systemone-http", "calibrated": True, "non_gate": True,
            "endpoint": endpoint,
            "model": str((raw or {}).get("_meta", {}).get("model")
                         or (raw or {}).get("model") or "unknown"),
            "raw_prob_sums": raw_sums,
            "confidence": {k: v.get("confidence")
                           for k, v in (raw or {}).items()
                           if isinstance(v, dict) and "confidence" in v},
            "usage": (raw or {}).get("_meta", {}).get("usage")}


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
        answers[name] = _answer_entry(name, q, _prob_dist(name, node), raw_sums)
    return {"schema": RESPONSE_SCHEMA, "status": "ok", "answers": answers,
            "meta": _systemone_meta(raw, endpoint, raw_sums)}


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

def _decl_head_issues(decl: Dict[str, Any]) -> List[str]:
    """声明头判据：schema / 三原语齐全 / 必须有离线 stub 适配器。"""
    out: List[str] = []
    if decl.get("schema") != SCHEMA:
        out.append("%s schema 不匹配（期望 %s）" % (DECL_REL, SCHEMA))
    prims = decl.get("primitives") or {}
    for p in PRIMITIVES:
        if p not in prims:
            out.append("声明缺原语 %s（三原语齐全才谈得上类型化决策）" % p)
    adapters = decl.get("adapters") or []
    if not any(a.get("id") == "stub" for a in adapters):
        out.append("缺 stub 适配器（门禁必须有一条离线确定性路径）")
    return out


def _adapter_issues(a: Dict[str, Any]) -> List[str]:
    """单适配器判据（必填字段 / note 自述 / 非 stub 不得 in_gate_path）。"""
    aid = str(a.get("id") or "")
    out: List[str] = []
    for k in ("id", "kind", "in_gate_path", "calibrated"):
        if k not in a:
            out.append("适配器 %s 缺字段 %s" % (aid or "?", k))
    if not str(a.get("note") or "").strip():
        out.append("适配器 %s 缺 note（能力与边界须自述）" % aid)
    if a.get("in_gate_path") and aid != "stub":
        out.append("适配器 %s 声明 in_gate_path 却非 stub"
                   "（门禁只许离线确定性路径）" % aid)
    return out


def _adapters_issues(adapters: List[Any]) -> List[str]:
    """逐适配器判据。"""
    out: List[str] = []
    for a in adapters:
        out.extend(_adapter_issues(a))
    return out


def _local_issues(cid: str, local: Dict[str, Any]) -> List[str]:
    """pulled=true 的本地证据判据（怎么拉/什么运行时/由谁服务）。"""
    out: List[str] = []
    for k in ("how", "runtime", "served_by"):
        if not str(local.get(k) or "").strip():
            out.append("候选 %s 声明 pulled=true 却缺 local.%s"
                       "（修复指引：写明怎么拉的、什么运行时、由谁服务）" % (cid, k))
    return out


def _candidate_issues(c: Dict[str, Any]) -> List[str]:
    """单候选模型判据（必填字段 / pulled 布尔 / 已拉取须带本地证据）。"""
    cid = str(c.get("id") or "")
    out: List[str] = []
    for k in ("id", "source", "license", "evidence", "pulled"):
        if k not in c:
            out.append("候选 %s 缺字段 %s（来源/许可/实证/是否已拉取都要写）" % (cid or "?",
                                                                              k))
    if not isinstance(c.get("pulled"), bool):
        out.append("候选 %s 的 pulled 须为布尔（状态不许含糊）" % cid)
    elif c.get("pulled") is True:
        # 拉取是**显式动作**：一旦声明已拉取，必须自带可追溯的本地证据
        out.extend(_local_issues(cid, c.get("local") or {}))
    return out


def _candidates_issues(cands: List[Any]) -> List[str]:
    """候选清单判据（非空 / 逐条）。"""
    out: List[str] = []
    if not cands:
        out.append("候选模型清单为空（决策层没有可拉取的模型就只是空壳）")
    for c in cands:
        out.extend(_candidate_issues(c))
    return out


def _boundary_issues(decl: Dict[str, Any]) -> List[str]:
    """边界成文判据。"""
    if not (decl.get("boundaries") or []):
        return ["声明缺 boundaries（不执行动作/不生成正文/不入门禁 等边界须成文）"]
    return []


def _sample_request() -> Dict[str, Any]:
    """内部样例请求（stub 确定性/合 schema/fail-closed 三面共用）。"""
    return {"state": "雨天走廊 与 校园情感 场景；候选：P02 校园情感流 / P03 西幻生存流",
            "questions": {
                "pipeline": {"type": "choice",
                             "options": ["P02 校园情感流", "P03 西幻生存流"]},
                "multilingual": {"type": "noul", "true_hints": ["中文", "多语"]},
                "risk": {"type": "score", "levels": ["低", "中", "高"]}}}


def _stub_repeat_issues(req: Dict[str, Any],
                        root: str) -> Tuple[List[str], Dict[str, Any]]:
    """stub 离线路径判据（确定性 / ok / 合 schema / 自称未校准）→ (issues, 首跑应答)。"""
    a1 = decide(req, opts=DecideOptions(adapter='stub', root=root))
    a2 = decide(req, opts=DecideOptions(adapter='stub', root=root))
    # 比「决策内容视图」而非整份应答：`meta.latency_ms` 是墙钟观测，差值 ≥1 ms 就判死人
    # （2026-09-29 实测假红，见 decision_view 的说明）。
    out: List[str] = []
    if decision_view(a1) != decision_view(a2):
        out.append("stub 非确定性（同输入两次结果不一致）")
    if a1.get("status") != "ok":
        out.append("stub 样例未产出 ok：%s" % a1.get("reason"))
    issue = response_issue(a1, req)
    if issue:
        out.append("stub 应答不合 schema：%s" % issue)
    if (a1.get("meta") or {}).get("calibrated") is not False:
        out.append("stub 应答须自称 calibrated=false（排序信号不是概率）")
    return out, a1


def _fail_closed_issues(req: Dict[str, Any], root: str) -> List[str]:
    """fail-closed 判据（未登记适配器 / 缺 endpoint / 不合规请求 → abstained）。"""
    out: List[str] = []
    cases: List[Tuple[str, Dict[str, Any]]] = [("未登记适配器", {"adapter": "ghost"}),
                                              ("缺 endpoint", {"adapter": "systemone-http"})]
    for label, kwargs in cases:
        got = decide(req, opts=DecideOptions(root=root, **kwargs))
        if got.get("status") != "abstained" or not got.get("reason"):
            out.append("%s 未 fail-closed（应 abstained + reason）" % label)
    bad = decide({'questions': {}}, opts=DecideOptions(adapter='stub', root=root))
    if bad.get("status") != "abstained":
        out.append("不合规请求未 fail-closed")
    return out


def _probability_guard_issues(req: Dict[str, Any]) -> List[str]:
    """判据自检：概率和不等于 1 的应答必须被拒。"""
    if response_issue({"schema": RESPONSE_SCHEMA, "status": "ok",
                       "answers": {"risk": {"type": "score", "probs": [0.2, 0.2],
                                            "value": 1.5}},
                       "meta": {"calibrated": True, "non_gate": True}}, req) == "":
        return ["概率和不等于 1 的应答竟通过校验（判据失效）"]
    return []


def scan(root: str = ".") -> Tuple[List[str], Dict[str, Any]]:
    """决策层面体检（离线）：声明完整 + 适配器诚实标注 + stub 确定性 + fail-closed。"""
    issues: List[str] = []
    decl = load_decl(root)
    if not decl:
        return ["缺决策层声明 %s（修复指引：补声明件再跑门禁）" % DECL_REL], {}
    prims = decl.get("primitives") or {}
    adapters = decl.get("adapters") or []
    cands = decl.get("candidates") or []
    issues.extend(_decl_head_issues(decl))
    issues.extend(_adapters_issues(adapters))
    issues.extend(_candidates_issues(cands))
    issues.extend(_boundary_issues(decl))
    req = _sample_request()
    if request_issue(req):
        issues.append("内部样例请求不合规：%s" % request_issue(req))
    stub_issues, a1 = _stub_repeat_issues(req, root)
    issues.extend(stub_issues)
    issues.extend(_fail_closed_issues(req, root))
    issues.extend(_probability_guard_issues(req))
    stats = {"primitives": len(prims), "adapters": len(adapters),
             "candidates": len(cands), "issueless_stub": a1.get("status") == "ok",
             "issues": len(issues)}
    return issues, stats


def summary(stats: Dict[str, Any]) -> str:
    return ("原语 %(primitives)d · 适配器 %(adapters)d · 候选模型 %(candidates)d · "
            "stub %(issueless_stub)s" % stats)
