"""CCOS Tool Manifest（nf-tool-manifest/1）：给 MCP 的 tools/list 加契约与证据，不破坏兼容。

主张（连接器文档 L3）：**对外说 MCP，对内走 CCOS**。纯 MCP 客户端只认 name/description/inputSchema，
所以所有增强字段一律放 _meta（MCP 保留区）——顶层 schema 一个字节不改。

补 MCP 的十个缺口里，本模块负责能静态判定的那部分：
- side_effect：none | local | network（调用会不会写盘/出网，默认按工具名保守判定）；
- idempotent：重试会不会重复写入（配合 idempotency_key 要求）；
- requires_consent：是否需要用户显式同意（写盘/出网/模型调用）；
- resource：max_bytes / timeout_ms；
- outputSchema：输出形状（没有就显式写 null，不许「没写等于随便」）；
- evidence：每次调用产出什么证据（emit + schema）；
- deprecated_at / replacement：弃用与迁移。

签名与吊销：清单自身 digest + 可选 ed25519 签名；验签失败或工具被吊销 → 拒用
（工具清单是「可下架」的，坏工具必须能被下线）。
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA = "nf-tool-manifest/1"
RECEIPT_SCHEMA = "nf-call-receipt/1"
SIDE_EFFECTS = ("none", "local", "network")
GUIDE = "修复指引："
TOP_LEVEL_ALLOWED = ("name", "description", "inputSchema")

#: 工具名 → 默认副作用（保守：写类 local、网络类 network，其余 none）
LOCAL_PREFIXES = ("label", "check", "assemble", "release", "output", "render", "sig",
                  "attest", "asset", "module", "register", "approve", "receipts",
                  "conformance", "evidence", "cog", "layers", "pipeline")
NETWORK_PREFIXES = ("serve", "interop", "market", "domain", "transparency")


def digest_of(obj: Any) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _from_annotations(raw: dict[str, Any]) -> dict[str, Any]:
    """真 MCP 工具自带的 annotations 优先于「按名字猜」——真实数据比启发式可靠。

    readOnlyHint → side_effect=none；destructiveHint → local；openWorldHint → network。
    没有 annotations 时才回落到名字推断。
    """
    ann = raw.get("annotations") or {}
    if not isinstance(ann, dict) or not ann:
        return {}
    out: dict[str, Any] = {}
    if ann.get("readOnlyHint"):
        out["side_effect"] = "none"
        out["requires_consent"] = False
    elif ann.get("destructiveHint"):
        out["side_effect"] = "local"
        out["requires_consent"] = True
    elif ann.get("openWorldHint"):
        out["side_effect"] = "network"
        out["requires_consent"] = True
    if isinstance(ann.get("idempotentHint"), bool):
        out["idempotent"] = ann["idempotentHint"]
    return out


def _infer_side_effect(name: str, declared: str = "") -> str:
    if declared in SIDE_EFFECTS:
        return declared
    lower = str(name).lower()
    if lower.startswith(NETWORK_PREFIXES):
        return "network"
    if lower.startswith(LOCAL_PREFIXES):
        return "local"
    return "none"


def build(tool_defs: list[dict[str, Any]],
          declarations: dict[str, dict[str, Any]] | None = None) -> dict[str, Any]:
    """从 tools/list 的原始工具定义派生增强清单（不改原定义）。"""
    decl = declarations or {}
    tools: list[dict[str, Any]] = []
    for raw in tool_defs:
        name = str(raw.get("name") or "")
        if not name:
            raise ValueError("工具缺 name（" + GUIDE + "tools/list 里每个工具必须有 name）")
        item = {key: raw[key] for key in TOP_LEVEL_ALLOWED if key in raw}
        conf = dict(_from_annotations(raw))
        conf.update(decl.get(name) or {})   # 显式声明可覆盖推断
        if raw.get("outputSchema") and not conf.get("outputSchema"):
            conf["outputSchema"] = raw["outputSchema"]
        side_effect = _infer_side_effect(name, str(conf.get("side_effect") or ""))
        item["_meta"] = {
            "ccos": {
                "manifest_version": "1.0.0",
                "side_effect": side_effect,
                "idempotent": bool(conf.get("idempotent", side_effect == "none")),
                "requires_consent": bool(conf.get("requires_consent",
                                                 side_effect != "none")),
                "resource": {"max_bytes": int(conf.get("max_bytes") or 64 * 1024 * 1024),
                             "timeout_ms": int(conf.get("timeout_ms") or 60000)},
                "outputSchema": conf.get("outputSchema"),
                "evidence": {"emit": True, "schema": RECEIPT_SCHEMA},
                "deprecated_at": conf.get("deprecated_at"),
                "replacement": conf.get("replacement"),
            }
        }
        tools.append(item)
    return {"schema": SCHEMA, "tools": tools,
            "top_level_allowed": list(TOP_LEVEL_ALLOWED)}


def validate(manifest: Any) -> list[str]:
    """清单校验 → 问题列表（空 = 合法）。"""
    issues: list[str] = []
    if not isinstance(manifest, dict) or str(manifest.get("schema")) != SCHEMA:
        return ["清单 schema 不匹配（" + GUIDE + "需要 " + SCHEMA + "）"]
    tools = manifest.get("tools")
    if not isinstance(tools, list) or not tools:
        return ["清单没有 tools（" + GUIDE + "至少一个工具）"]
    seen: set[str] = set()
    for item in tools:
        if not isinstance(item, dict):
            issues.append("tools 里有非对象条目")
            continue
        name = str(item.get("name") or "")
        if name in seen:
            issues.append("工具重名：" + name)
        seen.add(name)
        extra = set(item) - set(TOP_LEVEL_ALLOWED) - {"_meta"}
        if extra:
            issues.append(name + " 顶层出现非 MCP 字段 " + str(sorted(extra))
                          + "（" + GUIDE + "扩展字段必须放 _meta）")
        meta = (item.get("_meta") or {}).get("ccos") or {}
        if not meta:
            issues.append(name + " 缺 _meta.ccos（" + GUIDE + "增强字段放这里）")
            continue
        if meta.get("side_effect") not in SIDE_EFFECTS:
            issues.append(name + " 的 side_effect 非法：" + str(meta.get("side_effect")))
        if not isinstance(meta.get("idempotent"), bool):
            issues.append(name + " 的 idempotent 必须是布尔")
        if not isinstance(meta.get("requires_consent"), bool):
            issues.append(name + " 的 requires_consent 必须是布尔")
        if meta.get("side_effect") != "none" and not meta.get("requires_consent"):
            issues.append(name + " 有副作用却不需要同意（" + GUIDE + "写盘/出网必须显式同意）")
        res = meta.get("resource") or {}
        for field in ("max_bytes", "timeout_ms"):
            if not isinstance(res.get(field), int) or res[field] <= 0:
                issues.append(name + " 的 resource." + field + " 必须是正整数")
        if "outputSchema" not in meta:
            issues.append(name + " 必须在 _meta 里显式声明 outputSchema（没有就写 null）")
        ev = meta.get("evidence") or {}
        if not ev.get("emit") or not ev.get("schema"):
            issues.append(name + " 的 evidence 必须声明 emit 与 schema")
        if meta.get("deprecated_at") and not meta.get("replacement"):
            issues.append(name + " 已弃用但没给 replacement")
    return issues


def sign(manifest: dict[str, Any], seed: bytes) -> dict[str, Any]:
    """给清单签名 → {manifest_digest, signature, pubkey}（ed25519）。"""
    from core import ed25519
    if len(seed) != 32:
        raise ValueError("签名种子必须是 32 字节（" + GUIDE + "ed25519 seed）")
    body = digest_of({k: v for k, v in manifest.items() if k != "signature"})
    sig = ed25519.sign(seed, body.encode("ascii"))
    return {"manifest_digest": body, "signature": sig.hex(),
            "pubkey": ed25519.public_key(seed).hex()}


def verify_signature(manifest: dict[str, Any], envelope: dict[str, Any],
                     revoked_ids: list[str] | None = None,
                     tool_id: str = "",
                     expected_pubkey: str = "") -> dict[str, Any]:
    """验签 + 钉根 + 吊销检查 → {ok, issues}。

    只验「签名与公钥自洽」没有意义（换个种子重签一样能过），所以支持 expected_pubkey 钉根：
    没钉根时结论只能是「签名自洽」，不能当来源可信。
    """
    from core import ed25519
    res: dict[str, Any] = {"ok": False, "issues": []}
    body = digest_of({k: v for k, v in manifest.items() if k != "signature"})
    if str(envelope.get("manifest_digest")) != body:
        res["issues"].append("清单 digest 与签名信封不符（" + GUIDE + "清单被改过）")
        return res
    try:
        sig = bytes.fromhex(str(envelope.get("signature") or ""))
        pub = bytes.fromhex(str(envelope.get("pubkey") or ""))
    except ValueError:
        res["issues"].append("签名/公钥不是合法 hex（" + GUIDE + "重建签名信封）")
        return res
    if expected_pubkey and str(expected_pubkey).lower() != pub.hex():
        res["issues"].append("公钥与钉根不符（" + GUIDE + "换根/换清单都必须显式批准）")
        return res
    if not ed25519.verify(pub, body.encode("ascii"), sig):
        res["issues"].append("清单签名验签失败（" + GUIDE + "来源不可信，拒用）")
        return res
    if tool_id and tool_id in (revoked_ids or []):
        res["issues"].append("工具已被吊销：" + tool_id + "（" + GUIDE + "从清单移除并停用）")
        return res
    res["ok"] = True
    return res


def receipt(tool: str, args: Any, result: Any, prev: str = "",
            verdict: str = "ok") -> dict[str, Any]:
    """一次调用的回执（nf-call-receipt/1）：可复算、可串联。"""
    body = {"schema": RECEIPT_SCHEMA, "tool": str(tool),
            "args_digest": digest_of(args), "result_digest": digest_of(result),
            "verdict": str(verdict), "prev": str(prev)}
    body["digest"] = digest_of(body)
    return body


def replay_receipts(items: Any) -> dict[str, Any]:
    res: dict[str, Any] = {"ok": True, "issues": []}
    if not isinstance(items, list):
        return {"ok": False, "issues": ["receipts 必须是数组"]}
    prev = ""
    for idx, item in enumerate(items, 1):
        if str(item.get("prev") or "") != prev:
            res["issues"].append("第 " + str(idx) + " 条 prev 不符")
        body = {k: v for k, v in item.items() if k != "digest"}
        if digest_of(body) != item.get("digest"):
            res["issues"].append("第 " + str(idx) + " 条 digest 不符")
        prev = str(item.get("digest") or "")
    res["ok"] = not res["issues"]
    return res


def same_call_evidence(adapter_a: dict[str, Any], adapter_b: dict[str, Any]) -> bool:
    """同一调用经两个适配器（MCP / HTTP）产出的证据是否同源（args+result digest 相同）。"""
    return (str(adapter_a.get("args_digest")) == str(adapter_b.get("args_digest"))
            and str(adapter_a.get("result_digest")) == str(adapter_b.get("result_digest")))
