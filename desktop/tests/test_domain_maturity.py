# -*- coding: utf-8 -*-
"""T5.1 · 域包成熟度 M0–M3（`nf domain maturity`）判据。

覆盖四件事：
1. 四级 fixture：M0 模板 / M1 机检+产出面在册 / M2 真实模型执行 / M3 用户签收（逐级包含）；
2. 三种负例：**无证据降级**（声明 > 计算 = 虚标）、**artifact 缺失**、**check_rc != 0**；
   另加「executor 是工具/装配器 → 降 M1 并标缺真实模型执行」「digest 不可复算」「签收 digest 失效」；
3. `--write` 落盘：`protocol/domain_maturity.json` + `registry protocols[].maturity` 投影（仅新增
   该字段、幂等）；
4. CLI `--json` 形状（真跑 `nf domain maturity --json`，只读面）。

夹具全在临时目录（不落仓）；机检面用**注入 gate** 模拟（不跑整仓 verify）——真实同源执行面由
`nf domain maturity --json` 的 CLI 用例覆盖。
"""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "desktop" / "src"))
sys.path.insert(0, str(ROOT / "desktop" / "tests"))

try:
    import yaml  # noqa: F401  （protocol.yaml 解析链必需；缺依赖时跳过夹具用例）
    HAVE_YAML = True
except Exception:                                            # pragma: no cover - 环境面
    HAVE_YAML = False

from core import domain_maturity as dm  # noqa: E402

import cli_harness  # noqa: E402


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _gate(status="pass"):
    """注入的机检结果（形状同 `machine_gate()`：status + 六条 checks）。"""
    checks = {str(n): {"status": "PASS" if status == "pass" else
                       ("FAIL" if n == 32 else "PASS"), "source": "test"}
              for n in dm.MACHINE_CHECKS}
    return {"status": status, "scope": "repo", "checks": checks,
            "source": "injected", "note": "test gate"}


class Fixture:
    """合成一个最小包 → 逐级加证据（M0 → M1 → M2 → M3）。"""

    def __init__(self, root, name="测试域包"):
        self.root = Path(root)
        self.name = name

    def _write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        # 字节写：避开 Windows 文本模式的 \n → \r\n 翻译（digest 判据要的是文件真实字节）
        p.write_bytes(text.encode("utf-8"))

    def package(self, *, declared=None, modules=2, readme=True, with_outputs_block=False):
        pkg = {"conformance": "L2", "id": self.name, "name": self.name,
               "pipeline": "P99",
               "module_id_range": ["M99"],
               "categories": ["测试"],
               "dependencies": {"core_only": True, "core_modules": ["M00"],
                                "cross_package": []},
               "references": [],
               "modules": [{"id": "M99", "desc": "测试模块"}]
               if modules else [],
               "assets": {"count": 1, "readme": "README.md"},
               "mount_layers": {"P40 行为决策": {"default": ["M99"], "available": []}}}
        if declared is not None:
            pkg["maturity"] = declared
        if with_outputs_block:
            pkg["outputs"] = {}
        doc = {"protocol": {"schema_version": "2"}, "package": pkg}
        # JSON 是合法 YAML：夹具不依赖 PyYAML 的 dump 行为；解析侧仍走 yaml.safe_load。
        self._write("community/%s/protocol.yaml" % self.name,
                    json.dumps(doc, ensure_ascii=False, indent=2) + "\n")
        if readme:
            self._write("community/%s/README.md" % self.name, "# %s\n" % self.name)
        for i in range(modules):
            self._write("community/%s/modules/M%02d_测试模块%d.md" % (self.name, 90 + i, i),
                        "# 模块 M%02d\n" % (90 + i))
        return self

    def _read_pkg(self):
        return json.loads((self.root / "community" / self.name / "protocol.yaml")
                          .read_text(encoding="utf-8"))["package"]

    def _rewrite_pkg(self, pkg):
        doc = {"protocol": {"schema_version": "2"}, "package": pkg}
        self._write("community/%s/protocol.yaml" % self.name,
                    json.dumps(doc, ensure_ascii=False, indent=2) + "\n")

    def index(self, *, drift=False):
        rel = "outputs/REPORT.json"
        self._write("community/%s/%s" % (self.name, rel), '{"ok": true}\n')
        if drift:
            listed = "outputs/MISSING.json"
        else:
            listed = rel
        self._write("community/%s/outputs/INDEX.json" % self.name,
                    json.dumps({"schema": "nf-output-index/1", "package": self.name,
                                "outputs": [{"path": listed, "form": "json", "tier": "T2",
                                             "role": "data"}]}, ensure_ascii=False) + "\n")
        return self

    def m2(self, *, executor="convaiinnovations/laya-multilingual@0.3.5",
           date="2026-10-26", rc=0, digest="auto", artifact="outputs/EVIDENCE.md",
           digest_override=None, write_artifact=True):
        body = "# 证据包\n"
        if artifact and write_artifact:
            self._write("community/%s/%s" % (self.name, artifact), body)
        pkg = self._read_pkg()
        out = pkg.get("outputs") if isinstance(pkg.get("outputs"), dict) else {}
        out.update({"executor": executor, "date": date, "check_rc": rc})
        if artifact:
            out["artifact"] = artifact
        if digest_override is not None:
            out["digest"] = digest_override
        elif digest == "auto" and artifact:
            out["digest"] = _sha(body)
        pkg["outputs"] = out
        self._rewrite_pkg(pkg)
        return self

    def signoff(self, *, digest=None, accepted=True, verdict="pass"):
        self._write("protocol/audit.json",
                    json.dumps({"schema": "nf-audit/1",
                                "required_fields": ["id", "date", "scope", "verdict",
                                                    "auditor", "subjects"],
                                "verdict_vocabulary": ["pass", "fail", "warn"],
                                "rules": ["审计规则（夹具）"]}, ensure_ascii=False) + "\n")
        proto = self.root / "community" / self.name / "protocol.yaml"
        want = digest if digest is not None else hashlib.sha256(proto.read_bytes()).hexdigest()
        subj = "community/%s/protocol.yaml:%s" % (self.name, want)
        lines = ["---", "id: AUD-9001", "date: 2026-10-26",
                 "scope: community/%s" % self.name, "verdict: %s" % verdict,
                 "auditor: 测试", "subjects:", "  - %s" % subj]
        if accepted:
            lines += ["accepted_by: 作者", "accepted_at: 2026-10-26"]
        lines += ["---", "", "# 审计记录（夹具）", ""]
        self._write("results/audit/test-signoff.md", "\n".join(lines))
        return self

    def registry(self):
        entries = [{"id": self.name, "pipeline": "P99"}]
        self._write(dm.REGISTRY_REL, json.dumps({"protocols": entries},
                                                ensure_ascii=False, indent=2) + "\n")
        return self

    def sample_library(self, entry="NF-TEST-1", *, pipeline="P99", assoc_pipeline=None):
        """合成 library 官方样本 + library/INDEX.md 台账行（分支 b）。"""
        body = ["# 测试装配样本", "", "> 管线：%s · 八段骨架" % pipeline, ""]
        body += ["## %d. 段%d" % (i, i) for i in range(8)]
        body += ["", "M00 数据槽（见 §1）。"]
        self._write("library/%s.md" % entry, "\n".join(body) + "\n")
        shown = pipeline if assoc_pipeline is None else assoc_pipeline
        row = ("| %s | 测试流 %s · 样本 | 测试 | 作者 | 2026-10-26 | MIT | general | active | "
               "装配样本 |" % (entry, shown))
        self._write("library/INDEX.md",
                    "| 编号 | 标题 | 类型 | 作者 | 入库 | 许可 | 分级 | 状态 | 说明 |\n"
                    "|---|---|---|---|---|---|---|---|---|\n" + row + "\n")
        return self

    def sample_docs(self, fname="完整版样本_测试流P99.md", *, pipeline="P99", ledger=True):
        """合成 docs 官方样本（+ 可选 protocol 台账指认）。"""
        body = ["# 叙事世界完整版：测试流（%s）" % pipeline, "",
                "> active_pipeline = %s" % pipeline, ""]
        body += ["## %d. 段%d" % (i, i) for i in range(8)]
        self._write("docs/%s" % fname, "\n".join(body) + "\n")
        if ledger:
            self._write("protocol/ledger.json",
                        json.dumps({"source": "docs/%s" % fname}, ensure_ascii=False) + "\n")
        return self

    def compute(self, gate=None, sample_probe=None):
        return dm.compute(self.root, gate=_gate() if gate is None else gate,
                          sample_probe=sample_probe)


@unittest.skipUnless(HAVE_YAML, "PyYAML 不在（protocol.yaml 解析链必需）")
class MaturityLadderTest(unittest.TestCase):
    """M0 / M1 / M2 / M3 四级 fixture（逐级包含）。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="nf_maturity_")
        self.fx = Fixture(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_m0_template_only(self):
        self.fx.package()
        row = self.fx.compute()["packages"][0]
        self.assertEqual("M0", row["maturity"])
        self.assertEqual("M1", row["next_level"])
        self.assertTrue(row["evidence"]["M0"]["ok"])
        self.assertIn("outputs/INDEX.json", " ".join(row["missing"]))

    def test_m1_machine_gate_and_index(self):
        self.fx.package().index()
        row = self.fx.compute()["packages"][0]
        self.assertEqual("M1", row["maturity"])
        self.assertTrue(row["evidence"]["M1"]["ok"])
        self.assertIn("缺真实模型执行", " ".join(row["missing"]))

    def test_m2_real_model_record(self):
        self.fx.package().index().m2()
        row = self.fx.compute()["packages"][0]
        self.assertEqual("M2", row["maturity"])
        ev = row["evidence"]["M2"]
        self.assertTrue(ev["ok"])
        self.assertEqual("model", ev["executor_kind"])
        self.assertTrue(ev["digest_ok"])
        self.assertEqual("M3", row["next_level"])

    def test_m2_structured_model_executor(self):
        self.fx.package().index().m2(
            executor={"kind": "model", "id": "convaiinnovations/laya-multilingual",
                      "version": "0.3.5"})
        row = self.fx.compute()["packages"][0]
        self.assertEqual("M2", row["maturity"])

    def test_m3_user_signoff_binds_digest(self):
        self.fx.package().index().m2().signoff()
        row = self.fx.compute()["packages"][0]
        self.assertEqual("M3", row["maturity"])
        self.assertIsNone(row["next_level"])
        self.assertTrue(row["evidence"]["M3"]["ok"])
        self.assertEqual("results/audit/test-signoff.md", row["evidence"]["M3"]["entry"])

    def test_declared_matches_computed_makes_no_misdeclared(self):
        self.fx.package(declared="M0")
        row = self.fx.compute()["packages"][0]
        self.assertFalse(row["misdeclared"])


@unittest.skipUnless(HAVE_YAML, "PyYAML 不在（protocol.yaml 解析链必需）")
class MaturityNegativeTest(unittest.TestCase):
    """负例：无证据降级 / artifact 缺失 / check_rc!=0 / 工具 executor / digest 失效。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="nf_maturity_neg_")
        self.fx = Fixture(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_no_evidence_downgrades_declared_m3(self):
        """无证据降级：只声明 M3、零证据 → 计算 M0 且标虚标（不许自报）。"""
        self.fx.package(declared="M3")
        doc = self.fx.compute()
        row = doc["packages"][0]
        self.assertEqual("M0", row["maturity"])
        self.assertTrue(row["misdeclared"])
        self.assertEqual(1, doc["summary"]["misdeclared"])

    def test_artifact_missing_downgrades_to_m1(self):
        self.fx.package().index().m2(artifact="outputs/NOT_THERE.md", write_artifact=False)
        row = self.fx.compute()["packages"][0]
        self.assertEqual("M1", row["maturity"])
        self.assertIn("artifact", " ".join(row["missing"]))

    def test_check_rc_nonzero_downgrades_to_m1(self):
        self.fx.package().index().m2(rc=1)
        row = self.fx.compute()["packages"][0]
        self.assertEqual("M1", row["maturity"])
        self.assertIn("check_rc", " ".join(row["missing"]))
        self.assertFalse(row["evidence"]["M2"]["ok"])

    def test_tool_executor_marked_missing_real_model(self):
        """executor 是工具/装配器 → 降 M1 并标「缺真实模型执行」。"""
        self.fx.package().index().m2(
            executor='python scripts/nf.py assemble --build（官方 assembler）')
        row = self.fx.compute()["packages"][0]
        self.assertEqual("M1", row["maturity"])
        self.assertEqual("tool", row["evidence"]["M2"]["executor_kind"])
        self.assertIn("缺真实模型执行", " ".join(row["missing"]))

    def test_digest_mismatch_downgrades_to_m1(self):
        self.fx.package().index().m2(digest_override="0" * 64)
        row = self.fx.compute()["packages"][0]
        self.assertEqual("M1", row["maturity"])
        self.assertIn("digest", " ".join(row["missing"]))

    def test_stale_signoff_digest_stays_m2(self):
        self.fx.package().index().m2().signoff(digest="f" * 64)
        row = self.fx.compute()["packages"][0]
        self.assertEqual("M2", row["maturity"])
        self.assertIn("用户签收", " ".join(row["missing"]))

    def test_signoff_without_acceptance_stays_m2(self):
        self.fx.package().index().m2().signoff(accepted=False)
        row = self.fx.compute()["packages"][0]
        self.assertEqual("M2", row["maturity"])

    def test_gate_red_blocks_m1_even_with_index(self):
        """机检未全绿 → 有 INDEX 也停在 M0（fail-closed，不逐包洗绿）。"""
        self.fx.package().index()
        row = self.fx.compute(gate=_gate("fail"))["packages"][0]
        self.assertEqual("M0", row["maturity"])
        self.assertIn("机检未全绿", " ".join(row["missing"]))

    def test_index_path_drift_blocks_m1(self):
        self.fx.package().index(drift=True)
        row = self.fx.compute()["packages"][0]
        self.assertEqual("M0", row["maturity"])
        self.assertIn("不在盘", " ".join(row["missing"]))

    def test_index_output_check_failure_blocks_m1(self):
        """分支 a 负例：INDEX 在册但某件产出面未过 nf output check → 不算 M1。"""
        self.fx.package().index()
        self.fx._write("community/%s/outputs/REPORT.json" % self.fx.name, "not json\n")
        row = self.fx.compute()["packages"][0]
        self.assertEqual("M0", row["maturity"])
        self.assertIn("nf output check", " ".join(row["missing"]))


@unittest.skipUnless(HAVE_YAML, "PyYAML 不在（protocol.yaml 解析链必需）")
class M1BranchSampleTest(unittest.TestCase):
    """M1 分支 b（官方样本产物）判据：合格 / 证据缺失 / 样本 check 失败 / 非法关联。"""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="nf_maturity_sample_")
        self.fx = Fixture(self._tmp.name).package(declared="M1")

    def tearDown(self):
        self._tmp.cleanup()

    def _planner(self, pipe="P99"):
        def plan(_pkg, name):
            return "测试", {"matched": True, "package": name, "pipeline": pipe,
                           "allowed_module_ids": ["M00"]}
        return plan

    def _checker(self, issues=()):
        def check(_text, _plan, expected_pipeline=None):
            return list(issues), {"segments": 8}
        return check

    def _sample_ev(self, planner=None, checker=None):
        pkg = self.fx._read_pkg()
        return dm._sample_evidence(self.fx.root, self.fx.name, pkg,
                                   planner=planner or self._planner(),
                                   checker=checker or self._checker())

    def test_library_sample_traceable_and_passes_check(self):
        """分支 b（library）：样本在场 + library/INDEX.md 台账行指认包管线 + check 通过。"""
        self.fx.sample_library()
        ev = self._sample_ev()
        self.assertTrue(ev["ok"], ev)
        self.assertEqual("library/NF-TEST-1.md", ev["sample"])
        self.assertEqual("library", ev["sample_kind"])
        self.assertEqual("library/INDEX.md", ev["association"]["ledger"])
        self.assertEqual(8, ev["check"]["segments"])

    def test_docs_sample_traceable_via_protocol_ledger(self):
        """分支 b（docs）：样本声明本包管线 + protocol 台账指认该路径 + check 通过。"""
        self.fx.sample_docs()
        ev = self._sample_ev()
        self.assertTrue(ev["ok"], ev)
        self.assertEqual("docs", ev["sample_kind"])
        self.assertEqual("ledger.json", ev["association"]["ledger"])

    def test_evidence_missing_stays_m0(self):
        """证据缺失：无 INDEX 且无任何关联样本 → 保持 M0（不许虚报 M1）。"""
        def probe(root, name, pkg):
            return dm._sample_evidence(root, name, pkg,
                                       planner=self._planner(), checker=self._checker())
        row = self.fx.compute(sample_probe=probe)["packages"][0]
        self.assertEqual("M0", row["maturity"])
        self.assertIn("无可验收产物证据", " ".join(row["missing"]))

    def test_sample_check_failure_blocks_m1(self):
        """样本 check 失败：样本在场但未过 nf assemble --check → 不算 M1。"""
        self.fx.sample_library()
        ev = self._sample_ev(checker=self._checker(["八段骨架缺段：##3"]))
        self.assertFalse(ev["ok"])
        self.assertIn("未过 assemble --check", " ".join(ev["missing"]))

    def test_illegal_association_declares_other_pipeline(self):
        """非法关联：台账行声明的管线与本包不一致 → 不指认（不得靠路径猜）。"""
        self.fx.sample_library(pipeline="P99", assoc_pipeline="P07")
        ev = self._sample_ev()
        self.assertFalse(ev["ok"])
        self.assertIn("台账行未声明本包管线", " ".join(ev["missing"]))

    def test_docs_sample_without_ledger_not_identified(self):
        """docs 样本没有 provenance/协议台账指认 → 不进分支 b。"""
        self.fx.sample_docs(ledger=False)
        ev = self._sample_ev()
        self.assertFalse(ev["ok"])
        self.assertIn("台账未指认", " ".join(ev["missing"]))

    def test_sample_branch_lifts_to_m1(self):
        """集成：分支 b 成立 → 计算等级 M1（下一级 M2）。"""
        self.fx.sample_library()
        probe = lambda r, n, pkg: dm._sample_evidence(  # noqa: E731 - 测试内联注入
            r, n, pkg, planner=self._planner(), checker=self._checker())
        doc = self.fx.compute(sample_probe=probe)
        row = doc["packages"][0]
        self.assertEqual("M1", row["maturity"])
        self.assertEqual("sample", row["evidence"]["M1"]["branch"])
        self.assertEqual("library/NF-TEST-1.md", row["evidence"]["M1"]["sample"])
        self.assertEqual("M2", row["next_level"])


class RealRepoM1EvidenceTest(unittest.TestCase):
    """真仓代表包：分支 b 端到端（真实 library/docs 样本 + 同源 assemble check）。"""

    PKGS = ("技术文档域包", "校园情感领域包", "西幻生存领域包",
            "通用核心基础包", "校园西幻轻混组合包")

    @classmethod
    def setUpClass(cls):
        cls.rows = {row["package"]: row
                    for row in dm.compute(ROOT, packages=cls.PKGS, gate=_gate())["packages"]}

    def test_official_samples_upgrade_to_m1(self):
        expect = {
            "技术文档域包": ("library/NF-TECHDOC-Monyeah777-1.md", "library/INDEX.md"),
            "校园情感领域包": ("library/NF-1.md", "library/INDEX.md"),
            "西幻生存领域包": ("docs/完整版样本_西幻生存流P03.md", "drill_fidelity.json"),
        }
        for pkg, (sample, ledger) in expect.items():
            row = self.rows[pkg]
            self.assertEqual("M1", row["maturity"], row["missing"])
            m1 = row["evidence"]["M1"]
            self.assertEqual("sample", m1["branch"])
            self.assertEqual(sample, m1["sample"])
            # 台账必须来自协议溯源件，**不得**是本判据自己的产出（自指）
            self.assertEqual(ledger, m1["association"]["ledger"])
            self.assertNotIn("domain_maturity", m1["association"]["ledger"])
            self.assertEqual(8, m1["sample_check"]["segments"])

    def test_packages_without_evidence_stay_m0(self):
        for pkg in ("通用核心基础包", "校园西幻轻混组合包"):
            row = self.rows[pkg]
            self.assertEqual("M0", row["maturity"])
            self.assertIsNone(row["evidence"]["M1"]["branch"])


class ExecutorClassifyTest(unittest.TestCase):
    """executor 判定面（M2 的诚实边界）。"""

    def test_tool_and_assembler_not_model(self):
        for text in ("python scripts/nf.py assemble --build",
                     "官方 assembler（引用式八段）",
                     "nf assemble --check", "agent: gpt-4o", "make build"):
            kind, why = dm.classify_executor(text)
            self.assertEqual("tool", kind, (text, why))

    def test_model_with_version_is_model(self):
        for text in ("convaiinnovations/laya-multilingual@0.3.5",
                     "Qwen3-32B-instruct", "deepseek-chat v3"):
            kind, why = dm.classify_executor(text)
            self.assertEqual("model", kind, (text, why))

    def test_unknown_when_no_evidence(self):
        self.assertEqual("unknown", dm.classify_executor("")[0])
        self.assertEqual("unknown", dm.classify_executor("某执行者")[0])


@unittest.skipUnless(HAVE_YAML, "PyYAML 不在（protocol.yaml 解析链必需）")
class ComputeAndWriteTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="nf_maturity_write_")
        self.fx = Fixture(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_summary_and_shape(self):
        self.fx.package(declared="M0").index().registry()
        doc = self.fx.compute()
        self.assertEqual(dm.SCHEMA, doc["schema"])
        self.assertEqual("domain-maturity", doc["kind"])
        self.assertEqual(list(dm.MACHINE_CHECKS), doc["machine_checks"])
        self.assertEqual(set(dm.LEVELS), {k for k in doc["levels"]})
        self.assertEqual(1, doc["summary"]["total"])
        self.assertEqual(1, doc["summary"]["M1"])
        self.assertEqual(0, doc["summary"]["misdeclared"])

    def test_write_outputs_projects_registry_and_is_idempotent(self):
        self.fx.package(declared="M1").index().registry()
        doc = self.fx.compute()
        stats = dm.write_outputs(self.fx.root, doc)
        out = self.fx.root / dm.OUTPUT_REL
        self.assertTrue(out.is_file(), "protocol/domain_maturity.json 未落盘")
        payload = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(dm.SCHEMA, payload["schema"])
        reg = json.loads((self.fx.root / dm.REGISTRY_REL).read_text(encoding="utf-8"))
        self.assertEqual("M1", reg["protocols"][0]["maturity"])
        self.assertEqual(1, stats["registry"]["updated"])
        first = out.read_bytes()
        dm.write_outputs(self.fx.root, dm.compute(self.fx.root, gate=_gate()))
        self.assertEqual(first, out.read_bytes(), "同输入必须同字节（幂等）")

    def test_registry_only_new_field(self):
        self.fx.package(declared="M1").index().registry()
        dm.write_outputs(self.fx.root, self.fx.compute())
        reg = json.loads((self.fx.root / dm.REGISTRY_REL).read_text(encoding="utf-8"))
        self.assertEqual(["id", "pipeline", "maturity"], list(reg["protocols"][0]))


class CliJsonShapeTest(unittest.TestCase):
    """CLI `--json` 形状（真跑只读面；同源机检由本用例覆盖）。"""

    def test_maturity_json_shape(self):
        rc, out, err = cli_harness.run_cli(["domain", "maturity", "--json"])
        self.assertEqual(0, rc, err[-500:])
        doc = json.loads(out)
        self.assertEqual("nf-domain-maturity/1", doc.get("schema"))
        self.assertEqual("domain-maturity", doc.get("kind"))
        self.assertEqual([14, 15, 16, 23, 29, 32], doc.get("machine_checks"))
        self.assertIn(doc["machine_gate"]["status"], ("pass", "fail"))
        self.assertEqual(set(str(n) for n in doc["machine_checks"]),
                         set(doc["machine_gate"]["checks"]))
        pkgs = doc.get("packages") or []
        self.assertEqual(len(dm.discover_packages(ROOT)), len(pkgs))
        for row in pkgs:
            for key in ("package", "path", "declared", "maturity", "missing", "evidence"):
                self.assertIn(key, row)
            self.assertIn(row["maturity"], list(dm.LEVELS) + [None])
        summary = doc["summary"]
        self.assertEqual(len(pkgs), summary["total"])
        self.assertEqual(len(pkgs), sum(summary[k] for k in dm.LEVELS) + summary["unrated"])

    def test_help_lists_levels(self):
        rc, out, _err = cli_harness.run_cli(["domain", "maturity", "--help"])
        self.assertEqual(0, rc)
        self.assertIn("M0", out)
        self.assertIn("--write", out)


if __name__ == "__main__":
    unittest.main()
