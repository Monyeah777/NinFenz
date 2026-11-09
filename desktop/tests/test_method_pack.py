"""方法包判据：领域专业性必须是**可校验的数据**，不是文档里的形容词。

判据盯五件事：
① 包形状（id/version/domain、expert_moves 必需字段、evidence_standards 必填）；
② 可执行（每个 maps_to 必须指向仓内**真实存在**的原子/算子/move id）；
③ 组合（并集去重、序稳定、不评分）；
④ 诚实（未知包/坏包 fail-closed 并给修复指引）；
⑤ 接线（研究计划确实带上了领域块，且 CLI 可列）。
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import cognition_plan, method_pack  # noqa: E402

NF = (sys.executable, str(ROOT / "scripts" / "nf.py"))
PACK_IDS = ("watermarking", "evidence-audit", "metacognition",
            "evaluation-design", "prompt-injection-defense", "data-provenance",
            "resilience", "handoff", "privacy", "supply-chain", "operations")






def pack_doc_issues(text: str, packs: list) -> list[str]:
    """方法包文档数字判据的**纯函数核**（第 109 轮抽出，供变异测试喂坏文本）。

    规则：文档里的「N 个域 / N 个专家动作 / N 个证据类目」必须等于实际数据。
    """
    import re

    moves = sum(len(p["expert_moves"]) for p in packs)
    kinds = sum(len(p["evidence_standards"]) for p in packs)
    claims = {"个域": len(packs), "个专家动作": moves, "个证据类目": kinds}
    issues: list[str] = []
    for label, actual in claims.items():
        found = re.findall(r"(\d+)\s*" + label, text)
        if not found:
            issues.append("文档里没写「" + label + "」")
            continue
        for value in found:
            if int(value) != actual:
                issues.append("文档写 " + value + " " + label + "，实际 " + str(actual))
    return issues

class PackShapeTest(unittest.TestCase):
    def test_index_lists_registered_packs(self):
        packs = method_pack.list_packs(str(ROOT))
        self.assertEqual(set(PACK_IDS), {p["id"] for p in packs})

    def test_every_registered_pack_validates(self):
        for pid in PACK_IDS:
            pack = method_pack.load_pack(str(ROOT), pid)
            self.assertEqual([], method_pack.validate_pack(pack), pid)

    def test_pack_requires_core_fields(self):
        bad = {"schema": "nf-method-pack/1", "id": "x", "version": "1", "domain": "d",
               "expert_moves": [{"id": "X1", "name": "n", "why": "w",
                                 "maps_to": ["k.partition"]}]}
        issues = method_pack.validate_pack(bad)
        self.assertTrue(any("evidence_standards" in i for i in issues), issues)
        self.assertTrue(any("common_failures" in i for i in issues), issues)

    def test_unknown_maps_to_is_rejected(self):
        bad = {"schema": "nf-method-pack/1", "id": "x", "version": "1", "domain": "d",
               "expert_moves": [{"id": "X1", "name": "n", "why": "w",
                                 "maps_to": ["no.such.atom"]}],
               "evidence_standards": [{"claim_kind": "k", "required": ["r"]}],
               "common_failures": ["f"]}
        self.assertTrue(any("未知动作" in i for i in method_pack.validate_pack(bad)))

    def test_duplicate_move_id_is_rejected(self):
        mv = {"id": "X1", "name": "n", "why": "w", "maps_to": ["k.partition"]}
        bad = {"schema": "nf-method-pack/1", "id": "x", "version": "1", "domain": "d",
               "expert_moves": [mv, dict(mv)],
               "evidence_standards": [{"claim_kind": "k", "required": ["r"]}],
               "common_failures": ["f"]}
        self.assertTrue(any("重复" in i for i in method_pack.validate_pack(bad)))


class PackContentTest(unittest.TestCase):
    def test_watermarking_pack_covers_attack_surface(self):
        pack = method_pack.load_pack(str(ROOT), "watermarking")
        names = " ".join(m["name"] for m in pack["expert_moves"])
        self.assertIn("攻击面", names)
        self.assertIn("同步", names)
        std = method_pack.obligations(pack, "robustness")
        self.assertTrue(any("BER" in r for r in std["standards"][0]["required"]))

    def test_evidence_audit_pack_contains_claim_card(self):
        pack = method_pack.load_pack(str(ROOT), "evidence-audit")
        names = " ".join(m["name"] for m in pack["expert_moves"])
        self.assertIn("立卡", names)
        std = method_pack.obligations(pack, "closure")
        self.assertTrue(any("Claim Card" in r for r in std["standards"][0]["required"]))

    def test_evaluation_design_pack_has_pre_registration_and_controls(self):
        pack = method_pack.load_pack(str(ROOT), "evaluation-design")
        ids = {m["id"] for m in pack["expert_moves"]}
        for need in ("ev.pre_register", "ev.blind_partition", "ev.negative_control",
                     "ev.synthetic_guard", "ev.cost_accounting"):
            self.assertIn(need, ids, "评测设计包缺关键动作：" + need)
        kinds = {st["claim_kind"] for st in pack["evidence_standards"]}
        self.assertEqual({"efficacy", "cost", "reliability"}, kinds)
        self.assertTrue(any("合成" in f for f in pack["common_failures"]))

    def test_prompt_injection_pack_has_plane_separation_and_receipts(self):
        pack = method_pack.load_pack(str(ROOT), "prompt-injection-defense")
        ids = {m["id"] for m in pack["expert_moves"]}
        for need in ("pi.plane_separation", "pi.allowlist_surface", "pi.consent_gate",
                     "pi.receipt_audit", "pi.redteam_cases"):
            self.assertIn(need, ids, "注入防御包缺关键动作：" + need)
        kinds = {st["claim_kind"] for st in pack["evidence_standards"]}
        self.assertEqual({"defense-efficacy", "audit-trail", "least-privilege"}, kinds)
        # 例子里必须点名真实接线件，不能只说概念
        text = " ".join(str(x.get("case") or "") for x in pack["examples"])
        self.assertIn("mcp_ingress", text)


    def test_prompt_injection_moves_have_real_code_anchors(self):
        """包里的动作不能只是文字：每个 pi.* 动作都要在真实代码里有锚点。

        映射（动作 → 代码锚点）写死在本判据里，改了实现就得同步改这里——
        这样「包说我们做了平面分离/白名单/同意门/回执」就不是自述，而是可核。
        """
        anchors = {
            "pi.allowlist_surface": ("desktop/src/core/mcp_ingress.py", ("allow_tools", "deny")),
            "pi.consent_gate": ("desktop/src/core/mcp_ingress.py", ("consent",)),
            "pi.receipt_audit": ("desktop/src/core/mcp_ingress.py", ("record_call", "receipt")),
            "pi.least_privilege": ("desktop/src/core/mcp_ingress.py", ("max_args",)),
            # 输出/参数侧 schema 复核在运行时（schema_check 注入点），不在 ingress 本身
            "pi.output_side_check": ("desktop/src/core/mcp_runtime.py", ("schema_check",)),
        }
        pack = method_pack.load_pack(str(ROOT), "prompt-injection-defense")
        ids = {m["id"] for m in pack["expert_moves"]}
        for move_id, (rel, tokens) in anchors.items():
            self.assertIn(move_id, ids, "包缺动作：" + move_id)
            text = (ROOT / rel).read_text(encoding="utf-8")
            hit = [t for t in tokens if t in text]
            self.assertTrue(hit, "动作 " + move_id + " 在 " + rel + " 里没有锚点（"
                            + "/".join(tokens) + "）")


    def test_all_packs_compose_without_conflict(self):
        """全部已注册域一起组合：证据类目并集、常见错法去重、动作不重复 id、序稳定。"""
        ids = [p["id"] for p in method_pack.list_packs(str(ROOT))]
        self.assertEqual(len(PACK_IDS), len(ids), ids)
        composed = method_pack.compose([method_pack.load_pack(str(ROOT), p) for p in ids])
        kinds = [st["claim_kind"] for st in composed["evidence_standards"]]
        self.assertEqual(len(kinds), len(set(kinds)), "证据类目应去重：" + str(kinds))
        self.assertGreaterEqual(len(kinds), 12)
        self.assertEqual(len(composed["common_failures"]),
                         len(set(composed["common_failures"])))
        move_ids = [m["id"] for m in composed["expert_moves"]]
        self.assertEqual(len(move_ids), len(set(move_ids)))
        # 组合语义是「按传入包序并集」（不排序），所以只断言：同一输入序可复现、
        # 逆序时集合相同（内容不丢），而**不**要求字节相同。
        same = method_pack.compose([method_pack.load_pack(str(ROOT), p) for p in ids])
        self.assertEqual([m["id"] for m in same["expert_moves"]], move_ids)
        rev = method_pack.compose([method_pack.load_pack(str(ROOT), p) for p in reversed(ids)])
        self.assertEqual(set(move_ids), {m["id"] for m in rev["expert_moves"]},
                         "逆序组合不得丢动作")


    def test_every_pack_move_has_code_anchor_or_declared_conceptual(self):
        """每个方法包的动作要么有真实代码锚点，要么在 CONCEPTUAL 里写明为什么不能有。

        依据（第 27 轮立的规矩）：包只是文字时会退化成知识卡片；本判据逼每个动作
        指向本仓的可核实现（文件 + 关键词），或显式承认它是纯概念动作。
        """
        anchors = {
            "WM-1": ("scripts/watermark_bench.py", ("attacks",)),
            "WM-2": ("scripts/watermark_sync_probe.py", ("sync",)),
            "WM-3": ("scripts/watermark_dct_probe.py", ("qim",)),
            "WM-4": ("scripts/watermark_ecc_probe.py", ("crc",)),
            "WM-5": ("scripts/watermark_bench.py", ("ber",)),
            "EA-1": ("desktop/src/core/cognition_workspace/claims.py", ("obligations",)),
            "EA-2": ("desktop/src/core/closure.py", ("criteria",)),
            "EA-3": ("desktop/src/core/cognition_workspace/claims.py", ("ready",)),
            "EA-4": ("protocol/closure/ledger.json", ("reverse_fixture",)),
            "EA-5": ("desktop/src/core/closure.py", ("criteria",)),
            "MC-1": ("desktop/src/core/cognition_workspace/control.py", ("ritual",)),
            "MC-2": ("desktop/src/core/cognition_workspace/operators.py", ("estimate",)),
            "MC-3": ("desktop/src/core/calibration.py", ("ece",)),
            "MC-4": ("desktop/src/core/cognition_workspace/operators.py", ("switch",)),
            "MC-5": ("desktop/src/core/cognition_workspace/session.py", ("replay",)),
            "ev.pre_register": ("desktop/src/core/eval_harness.py", ("frozen_before_run",)),
            "ev.blind_partition": ("desktop/src/core/eval_harness.py", ("blind_review",)),
            "ev.negative_control": ("desktop/src/core/eval_harness.py", ("negative_control",)),
            "ev.synthetic_guard": ("desktop/src/core/eval_harness.py", ("synthetic",)),
            "ev.effect_and_variance": ("desktop/src/core/grouped_report.py", ("sd",)),
            "ev.cost_accounting": ("desktop/src/core/eval_harness.py", ("cost_accounting",)),
            "ev.replicate": ("scripts/eval_run.py", ("--check",)),
            "pi.allowlist_surface": ("desktop/src/core/mcp_ingress.py", ("allow",)),
            "pi.consent_gate": ("desktop/src/core/mcp_ingress.py", ("consent",)),
            "pi.receipt_audit": ("desktop/src/core/mcp_ingress.py", ("record_call",)),
            "pi.least_privilege": ("desktop/src/core/mcp_ingress.py", ("max_args",)),
            "pi.output_side_check": ("desktop/src/core/mcp_runtime.py", ("schema_check",)),
            # 红队用例集已落成数据 + 逐条判据（第 40 轮）
            "pi.redteam_cases": ("protocol/redteam/mcp_injection_cases.json", ("RT-01",)),
            # 数据溯源域（第 48 轮）：锚点落在「已有的协议/度量面」，不另造概念
            "pv.datasheet": ("scripts/eval_run.py", ("checklist",)),
            "pv.field_lineage": ("protocol/asset_contracts.json", ("field",)),
            "pv.missing_semantics": ("desktop/src/core/grouped_report.py", ("note",)),
            "pv.license_gate": ("desktop/src/core/closure.py", ("criteria",)),
            "pv.version_pin": ("protocol/eval/protocol.json", ("analysis_plan",)),
            "pv.leakage_audit": ("protocol/eval/protocol.json", ("prohibitions",)),
            # 韧性工程域（第 66 轮）：锚点落既有隔离/变异/回滚/失败面
            "rs.blast_radius": ("desktop/src/core/build_isolation.py", ("isolat",)),
            "rs.chaos_drill": ("desktop/src/core/purity_scan.py", ("mutation",)),
            "rs.rollback_path": ("protocol/closure/ledger.json", ("reverse_fixture",)),
            "rs.fail_closed": ("desktop/src/core/decision_layer.py", ("abstain",)),
            "rs.degradation": ("desktop/src/core/as_of.py", ("as_of",)),
            "rs.postmortem": ("desktop/src/core/allowlist_expiry.py", ("expired",)),
            # 协作交接域（第 67 轮）：锚点落桥/批准/复验/回执
            "co.resumable_frame": ("desktop/src/core/cognition_workspace/session.py", ("step",)),
            "co.commitment_record": ("desktop/src/core/cognition_workspace/bridge.py",
                                     ("commitment",)),
            "co.role_separation": ("desktop/src/core/approval.py",
                                   ("allowed_approvers",)),
            "co.disagreement_log": ("protocol/closure/ledger.json", ("evidence",)),
            "co.external_verify": ("desktop/src/core/evidence.py", ("verify",)),
            "co.version_pin": ("desktop/src/core/receipts.py", ("receipt",)),
            # 隐私工程域（第 106 轮）：锚点落入口同意 / 到期 / 吊销面
            "pr.minimization": ("desktop/src/core/mcp_ingress.py", ("max_args",)),
            "pr.purpose": ("desktop/src/core/grouped_report.py", ("groups",)),
            "pr.retention": ("desktop/src/core/allowlist_expiry.py", ("expired",)),
            "pr.consent": ("desktop/src/core/mcp_ingress.py", ("consent",)),
            "pr.deidentify": ("protocol/redteam/mcp_injection_cases.json", ("RT-0",)),
            "pr.deletion_proof": ("desktop/src/core/evidence.py", ("revoked",)),
            # 供应链安全域（第 111 轮）：锚点落 packaging / 静态扫描 / 溯源记录
            "sc.pin_inputs": ("packaging/npm/tools/stage-payload.mjs", ("manifest",)),
            "sc.materials_products": ("desktop/src/core/evidence.py", ("sha256",)),
            "sc.reproducible_build": ("packaging/npm/tools/stage-payload.mjs", ("digest",)),
            "sc.verify_artifacts": ("packaging/npm/tools/verify-tarball.mjs", ("tarball",)),
            "sc.static_scan": ("scripts/sast_check.py", ("baseline",)),
            "sc.provenance_record": ("scripts/release_conclusion.py", ("supply_chain",)),
            # 运维可观测性域（第 122 轮）：锚点落预算 / 复盘 / 指标面
            "op.slo": ("desktop/src/core/perf_budget.py", ("budget",)),
            "op.health_signal": ("desktop/src/core/fence_health.py", ("fence",)),
            "op.alert_actionable": ("desktop/src/core/injection_budget.py", ("budget",)),
            "op.burn": ("desktop/src/core/perf_budget.py", ("p95",)),
            "op.review_blameless": ("desktop/src/core/postmortem.py", ("cause",)),
            "op.panel_same_source": ("desktop/src/core/domain_metrics.py", ("metrics",)),
        }
        #: 纯概念动作（本仓还没有对应实现）→ 理由。为空表示「全都该有锚点」。
        CONCEPTUAL = {"pi.plane_separation": "结构性保证（argv-only/无 shell），不是单一代码点"}
        for pid in PACK_IDS:
            pack = method_pack.load_pack(str(ROOT), pid)
            for mv in pack["expert_moves"]:
                mid = mv["id"]
                if mid in CONCEPTUAL:
                    self.assertTrue(mv.get("why"), mid + " 声明为概念动作但没有 why")
                    continue
                self.assertIn(mid, anchors, "动作没登记锚点：" + mid)
                rel, tokens = anchors[mid]
                text = (ROOT / rel).read_text(encoding="utf-8")
                self.assertTrue(any(t in text for t in tokens),
                                mid + " 在 " + rel + " 里找不到锚点（" + "/".join(tokens) + "）")

    def test_vocabulary_check_can_be_killed(self):
        """判据 #4 的变异测试：故意改坏 registry / 包，核对函数必须报出来。

        只有「真实数据为空」证明不了判据有效；这里用两份故意错的数据证明它会红，
        对应设计里「门禁变异分」的最小事例。
        """
        packs = [method_pack.load_pack(str(ROOT), pid) for pid in PACK_IDS]
        registry = json.loads((ROOT / "protocol" / "criteria" / "registry.json")
                              .read_text(encoding="utf-8"))
        self.assertEqual({"unknown": [], "unused": []},
                         method_pack.vocabulary_mismatches(packs, registry))
        # ① 去掉一个词 → 包用到的词变成「未登记」
        broken = dict(registry, claim_kinds=list(registry["claim_kinds"])[1:])
        self.assertTrue(method_pack.vocabulary_mismatches(packs, broken)["unknown"])
        # ② 加一个没人用的词 → 变成「死词」
        extra = dict(registry, claim_kinds=list(registry["claim_kinds"]) + ["ghost-kind"])
        self.assertEqual(["ghost-kind"],
                         method_pack.vocabulary_mismatches(packs, extra)["unused"])

    def test_pack_doc_count_judge_can_be_killed(self):
        """变异测试（第 109 轮）：方法包文档的数字写错必须被纯函数核报出来。"""
        packs = [method_pack.load_pack(str(ROOT), pid) for pid in PACK_IDS]
        moves = sum(len(p["expert_moves"]) for p in packs)
        kinds = sum(len(p["evidence_standards"]) for p in packs)
        good = f"**{len(packs)} 个域 / {moves} 个专家动作 / {kinds} 个证据类目**"
        self.assertEqual([], pack_doc_issues(good, packs))
        wrong = f"**{len(packs) - 1} 个域 / {moves} 个专家动作 / {kinds} 个证据类目**"
        self.assertTrue(pack_doc_issues(wrong, packs))

    def test_examples_cite_existing_files(self):
        """包里的 example 引用的路径必须真实存在（防「例子里的文件早就改名了」）。

        依据（第 107 轮）：九域 10 处路径引用里有 7 处写成 `core/x.py`（少了 `desktop/src/` 前缀）——
        不影响阅读，但**复制粘贴会失败**，而且改名后没人发现。本判据要求引用写全并真实存在。
        """
        import re
        pat = re.compile(r"[A-Za-z0-9_./-]+\.(?:py|json|md|mjs|sh)")
        missing = []
        total = 0
        for pid in PACK_IDS:
            pack = method_pack.load_pack(str(ROOT), pid)
            for ex in pack.get("examples") or []:
                for tok in pat.findall(str(ex.get("case") or "")):
                    total += 1
                    if not (ROOT / tok).is_file():
                        missing.append(pid + " → " + tok)
        self.assertGreaterEqual(total, 8, "例子里的路径引用太少（判据可能已失效）")
        self.assertEqual([], missing, f"例子引用了不存在的路径：{missing}")

    def test_doc_counts_match_packs(self):
        """文档写的「N 个域 / N 个专家动作 / N 个证据类目」必须等于实际（防口径漂移）。"""
        import re
        doc = (ROOT / "docs" / "ccos" / "method-packs-v0.md").read_text(encoding="utf-8")
        packs = [method_pack.load_pack(str(ROOT), pid) for pid in PACK_IDS]
        moves = sum(len(p["expert_moves"]) for p in packs)
        kinds = sum(len(p["evidence_standards"]) for p in packs)
        self.assertEqual([], pack_doc_issues(doc, packs))
        claims = {
            "个域": len(packs),
            "个专家动作": moves,
            "个证据类目": kinds,
        }
        for label, actual in claims.items():
            found = re.findall(r"(\d+)\s*" + label, doc)
            self.assertTrue(found, "文档里没写「" + label + "」")
            for text in found:
                self.assertEqual(int(text), actual,
                                 f"文档写 {text} {label}，实际 {actual}（改文档或补包）")

    def test_checklist_projection_covers_all_moves(self):
        """清单投影：每域动作一条、按包内顺序、证据标准齐带（不评分不排序）。"""
        for pid in PACK_IDS:
            pack = method_pack.load_pack(str(ROOT), pid)
            doc = method_pack.checklist(pack)
            self.assertEqual("nf-method-checklist/1", doc["schema"], pid)
            self.assertEqual(len(pack["expert_moves"]), len(doc["items"]), pid)
            self.assertEqual([str(m["id"]) for m in pack["expert_moves"]],
                             [it["move"] for it in doc["items"]], pid + " 顺序须与包一致")
            self.assertEqual([str(st["claim_kind"])
                              for st in pack["evidence_standards"]],
                             [st["claim_kind"] for st in doc["evidence_standards"]], pid)
            for it in doc["items"]:
                self.assertTrue(it["why"].strip(), pid + " 动作缺 why")
            self.assertIn("不评分", doc["note"])

    def test_checklist_rejects_broken_pack(self):
        with self.assertRaises(ValueError) as ctx:
            method_pack.checklist({"schema": "nf-method-pack/1"})
        self.assertIn("修复指引", str(ctx.exception))

    def test_claim_kinds_come_from_single_vocabulary(self):
        """同构判据 #4（语义层）：方法包的 claim_kind 必须来自 criteria registry 的单一词表。

        两侧要「说同一件事」：包里的证据标准与 registry 的领域词表必须同源。
        ① 包里的每个 claim_kind 都在 registry.claim_kinds 内；
        ② 词表里不能有没人用的死词（只增不用的词表 = 假统一）。
        """
        import json
        reg = json.loads((ROOT / "protocol" / "criteria" / "registry.json")
                         .read_text(encoding="utf-8"))
        vocab = set(reg.get("claim_kinds") or [])
        self.assertTrue(vocab, "registry 缺 claim_kinds 词表")
        used = set()
        for pid in PACK_IDS:
            pack = method_pack.load_pack(str(ROOT), pid)
            for std in pack["evidence_standards"]:
                kind = str(std["claim_kind"])
                used.add(kind)
                self.assertIn(kind, vocab, "包 " + pid + " 用了未登记词：" + kind)
        self.assertEqual(sorted(vocab - used), [],
                         f"词表里有没人用的死词：{sorted(vocab - used)}")
    def test_metacognition_pack_has_calibration_standard(self):
        pack = method_pack.load_pack(str(ROOT), "metacognition")
        std = method_pack.obligations(pack, "calibration")
        self.assertTrue(any("基线" in r for r in std["standards"][0]["required"]))

    def test_unknown_claim_kind_is_rejected_with_guide(self):
        pack = method_pack.load_pack(str(ROOT), "watermarking")
        with self.assertRaises(ValueError) as ctx:
            method_pack.obligations(pack, "no-such-kind")
        self.assertIn("修复指引", str(ctx.exception))


class ComposeTest(unittest.TestCase):
    def test_compose_unions_and_dedupes(self):
        packs = [method_pack.load_pack(str(ROOT), pid) for pid in ("watermarking",
                                                                  "watermarking")]
        out = method_pack.compose(packs)
        ids = [m["id"] for m in out["expert_moves"]]
        self.assertEqual(len(ids), len(set(ids)), "重复包必须去重")

    def test_compose_keeps_kind_order_stable(self):
        packs = [method_pack.load_pack(str(ROOT), pid) for pid in ("evidence-audit",
                                                                  "watermarking")]
        a = method_pack.compose(packs)
        b = method_pack.compose(packs)
        self.assertEqual(json.dumps(a, sort_keys=True), json.dumps(b, sort_keys=True))
        self.assertEqual([s["claim_kind"] for s in a["evidence_standards"]],
                         [s["claim_kind"] for s in b["evidence_standards"]])

    def test_compose_requires_packs(self):
        with self.assertRaises(ValueError):
            method_pack.compose([])

    def test_unknown_pack_id_is_rejected_with_guide(self):
        with self.assertRaises(ValueError) as ctx:
            method_pack.load_pack(str(ROOT), "no-such-pack")
        self.assertIn("修复指引", str(ctx.exception))


class PlanIntegrationTest(unittest.TestCase):
    def test_plan_without_packs_has_no_domain_block(self):
        doc = cognition_plan.plan("水印抗转码", 1, root=str(ROOT))
        self.assertIsNone(doc["domain"])

    def test_plan_with_pack_carries_expert_moves(self):
        doc = cognition_plan.plan("屏幕拍摄水印", 1, root=str(ROOT),
                                  pack_ids=["watermarking"])
        self.assertEqual(["watermarking"], doc["domain"]["packs"])
        self.assertGreaterEqual(len(doc["domain"]["expert_moves"]), 3)
        self.assertTrue(doc["domain"]["common_failures"])

    def test_plan_with_two_packs_composes(self):
        doc = cognition_plan.plan("证据链审计", 1, root=str(ROOT),
                                  pack_ids=["watermarking", "evidence-audit"])
        self.assertEqual(2, len(doc["domain"]["packs"]))
        kinds = {s["claim_kind"] for s in doc["domain"]["evidence_standards"]}
        self.assertIn("robustness", kinds)
        self.assertIn("closure", kinds)


class CliTest(unittest.TestCase):
    def test_packs_list(self):
        proc = subprocess.run([*NF, "cognition", "--packs-list"], capture_output=True,
                              text=True, encoding="utf-8", errors="replace", timeout=180)
        self.assertEqual(0, proc.returncode, proc.stderr[-300:])
        self.assertIn("watermarking", proc.stdout)

    def test_plan_with_pack_out_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "plan.json"
            proc = subprocess.run([*NF, "cognition", "--plan", "屏幕拍摄水印",
                                   "--depth", "1", "--pack", "watermarking",
                                   "--out", str(out), "--json"],
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace", timeout=180)
            self.assertEqual(0, proc.returncode, proc.stderr[-300:])
            doc = json.loads(proc.stdout)
            self.assertEqual(["watermarking"], doc["domain"]["packs"])
            self.assertEqual(doc, json.loads(out.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
