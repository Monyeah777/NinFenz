"""core.decision_layer 私有实现分片 1/2（对外只经 core.decision_layer 门面导入）：DECL_REL 等"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List

from core import json_doc

DECL_REL = "protocol/decision_layer.json"


SCHEMA = "nf-decision-layer/1"


RESPONSE_SCHEMA = "nf-decision-response/1"


PRIMITIVES = ("choice", "noul", "score")


#: 概率求和容差（schema 级判据）。实证来源（2026-09-22，真模型）：Laya 系服务把概率
#: **四舍五入到 4 位小数**回传（三次问题实测和 = 0.9999），而残差 1e-4 属**舍入**而非错误——
#: 若坚持 1e-6，等于把每一个真实校准模型都拒在门外。故取 1e-3（4 位小数的量化误差上界），
#: 且适配器侧**先归一化再入档**、把原始和记进 meta（判据放松，证据不放松）。
PROB_TOL = 1e-3


# ---------------------------------------------------------------- 声明面

def load_decl(root: str = ".") -> Dict[str, Any]:
    p = os.path.join(root, DECL_REL)
    if not os.path.isfile(p):
        return {}
    return json_doc.load(p, dict, what=p)


def adapter_ids(root: str = ".") -> List[str]:
    return [str(a.get("id")) for a in (load_decl(root).get("adapters") or [])]


def adapter_spec(root: str, adapter: str) -> Dict[str, Any]:
    for a in load_decl(root).get("adapters") or []:
        if str(a.get("id")) == adapter:
            return a
    return {}


# ---------------------------------------------------------------- 形状校验

def request_issue(req: Any) -> str:
    """请求体检 → 违规说明（空串 = 合规）。"""
    if not isinstance(req, dict):
        return "请求须为对象"
    if not isinstance(req.get("state"), str) or not req["state"].strip():
        return "缺 state（决策层只对给定的状态做判断）"
    qs = req.get("questions")
    if not isinstance(qs, dict) or not qs:
        return "缺 questions（须至少一个问题）"
    for name, q in qs.items():
        if not isinstance(q, dict):
            return "问题 %s 须为对象" % name
        ptype = q.get("type")
        if ptype not in PRIMITIVES:
            return "问题 %s 的 type 越词表：%r（允许 %s）" % (name, ptype, "/".join(PRIMITIVES))
        if ptype == "choice":
            opts = q.get("options")
            if not isinstance(opts, list) or len(opts) < 2:
                return "choice 问题 %s 须给 ≥2 个候选（候选集由调用方提供）" % name
            if not all(isinstance(o, str) and o for o in opts):
                return "choice 问题 %s 的候选须为非空字符串" % name
            if len(set(opts)) != len(opts):
                return "choice 问题 %s 的候选取值重复" % name
        if ptype == "score":
            levels = q.get("levels")
            if not isinstance(levels, list) or len(levels) < 2:
                return "score 问题 %s 须给 ≥2 个有序等级" % name
    return ""


def response_issue(out: Any, req: Dict[str, Any]) -> str:
    """应答体检 → 违规说明（空串 = 合规）。"""
    if not isinstance(out, dict):
        return "应答须为对象"
    for k in ("schema", "status", "answers", "meta"):
        if k not in out:
            return "缺字段 %s" % k
    if out.get("schema") != RESPONSE_SCHEMA:
        return "schema 不匹配（期望 %s）" % RESPONSE_SCHEMA
    status = out.get("status")
    if status == "abstained":
        return "" if str(out.get("reason") or "").strip() else "abstained 须给 reason"
    if status != "ok":
        return "status 越词表：%r（允许 ok/abstained）" % status
    answers = out.get("answers")
    questions = (req or {}).get("questions") or {}
    if not isinstance(answers, dict):
        return "answers 须为对象"
    missing = [n for n in questions if n not in answers]
    if missing:
        return "answers 缺问题：%s（不得静默漏答）" % "、".join(missing)
    for name, ans in answers.items():
        if not isinstance(ans, dict):
            return "答案 %s 须为对象" % name
        ptype = (questions.get(name) or {}).get("type")
        if ans.get("type") != ptype:
            return "答案 %s 的 type 与提问不一致：%r ≠ %r" % (name, ans.get("type"), ptype)
        if ptype in ("choice", "score"):
            opts = (questions[name].get("options") or questions[name].get("levels") or [])
            probs = ans.get("probs")
            if not isinstance(probs, list) or len(probs) != len(opts):
                return "答案 %s 的 probs 长度须等于候选/等级数（%d）" % (name, len(opts))
            if any(not isinstance(p, (int, float)) or p < 0 for p in probs):
                return "答案 %s 的概率须为非负数" % name
            if abs(sum(probs) - 1.0) > PROB_TOL:
                return "答案 %s 的概率和须 ≈1（实得 %.6f）" % (name, sum(probs))
            if ptype == "choice":
                if ans.get("argmax") not in opts:
                    return "答案 %s 的 argmax 须落在候选集内：%r" % (name, ans.get("argmax"))
            else:
                if not isinstance(ans.get("value"), (int, float)):
                    return "答案 %s 须给期望值 value（score 原语）" % name
        else:  # noul
            p = ans.get("p")
            if not isinstance(p, (int, float)) or not (0.0 <= float(p) <= 1.0):
                return "答案 %s 的 p 须为 [0,1] 内的数" % name
    meta = out.get("meta") or {}
    if meta.get("non_gate") is not True:
        return "meta.non_gate 须为 true（决策层不出现在门禁路径）"
    if "calibrated" not in meta:
        return "meta 缺 calibrated（是否校准概率必须自述）"
    return ""


# ---------------------------------------------------------------- 适配器

def _normalize(scores: List[float]) -> List[float]:
    total = float(sum(scores))
    if total <= 0:
        return [1.0 / len(scores)] * len(scores)
    return [float(s) / total for s in scores]


def normalize_probs(probs: List[float]) -> List[float]:
    """把外部模型的（可能被舍入的）概率归一化到和为 1（消费者需要真分布）。"""
    return _normalize([float(p) for p in probs])


def _hits(state: str, needles: List[str]) -> int:
    low = state.lower()
    return sum(1 for n in needles if n and str(n).lower() in low)


def stub_decide(req: Dict[str, Any]) -> Dict[str, Any]:
    """离线确定性决策（门禁/CI/演练用）。

    规则（全部可复现，无随机源）：choice/score 按「候选串/等级串在 state 中出现的次数」打分，
    同分按**声明顺序**打破平局；noul 命中 `true_hints` 关键词即 1.0，否则 0.0。
    **calibrated=false**：这是排序信号，不是校准概率（不要当概率消费）。
    """
    state = str(req.get("state") or "")
    answers: Dict[str, Any] = {}
    for name, q in (req.get("questions") or {}).items():
        ptype = q.get("type")
        if ptype == "choice":
            opts = [str(o) for o in q.get("options") or []]
            scores = [float(_hits(state, [o])) for o in opts]
            probs = _normalize(scores)
            answers[name] = {"type": "choice", "options": opts, "probs": probs,
                             "argmax": opts[probs.index(max(probs))]}
        elif ptype == "score":
            levels = [str(l) for l in q.get("levels") or []]
            scores = [float(_hits(state, [l])) for l in levels]
            probs = _normalize(scores)
            value = sum((i + 1) * p for i, p in enumerate(probs))
            answers[name] = {"type": "score", "levels": levels, "probs": probs,
                             "value": value}
        else:  # noul
            hits = _hits(state, [str(h) for h in (q.get("true_hints") or [])])
            answers[name] = {"type": "noul", "p": 1.0 if hits else 0.0}
    return {"schema": RESPONSE_SCHEMA, "status": "ok", "answers": answers,
            "meta": {"adapter": "stub", "calibrated": False, "non_gate": True,
                     "note": "规则式确定性输出：排序信号，非校准概率"}}


@dataclass(frozen=True)
class DecideOptions:
    """参数对象（审计 C-007：把成组参数收成不可变对象）。"""
    adapter: str = 'stub'
    endpoint: str = ''
    model: str = ''
    api_key: str = ''
    timeout: float = 30.0
    root: str = '.'


def fingerprint(req: Dict[str, Any]) -> str:
    """请求指纹（可回放：同 state+questions 得同指纹）。"""
    payload = json.dumps(req, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def decision_view(out: Dict[str, Any]) -> Dict[str, Any]:
    """应答的**决策内容视图**：去掉 `meta.latency_ms`（墙钟观测，不属于决策本身）。

    2026-09-29 实测假红：门禁原来直接比 `a1 != a2`，而 `decide()` 会把 `latency_ms`（整数毫秒）
    写进应答——机器一忙（当时确有并发进程）两次调用的差值就 ≥1 ms，`scan()` 当场报
    「stub 非确定性（同输入两次结果不一致）」，把一次正常验收判成协议事故。
    判据要钉的是「同输入 ⇒ 同决策」，墙钟不是决策；`meta` 的**其余**字段
    （`adapter` / `calibrated` / `non_gate`）照旧参与比较——不许用「整个 meta 都不比」绕过去。
    """
    view = dict(out)
    meta = dict(view.get("meta") or {})
    meta.pop("latency_ms", None)
    view["meta"] = meta
    return view
