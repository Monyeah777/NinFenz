#!/usr/bin/env python3
"""Allstar Dangerous Workflow 契约判据：配置不静默 + 全仓危险工作流扫描零命中（2026-11-11）。

为什么必须有：dangerous_workflow.yaml 此前是 4 行 stub，只声明「用 issue 动作」；而真正决定有没
有危险的是**工作流本身**。该策略委托 OpenSSF Scorecard 的 Dangerous-Workflow 检查执行，检测面
只有两类：不可信代码 checkout（pull_request_target / workflow_run 触发 + actions/checkout 的
with.ref 引用 github.event.pull_request / github.event.workflow_run）与脚本注入（run 里内联攻
击者可控表达式，含 tojson(github) 整上下文序列化）。检测面由 Scorecard 硬编码、配置里既不能增删
规则，所以本件把「本仓当前零命中」这条事实本身变成判据：新增危险写法会红，而不是靠「本文件写了
action: issue」自证安全。

范围：只判 .allstar/dangerous_workflow.yaml + 对受跟踪 .github/workflows/*.yml 的只读扫描。
同族判据：test_workflow_policy（钉 SHA / 最小权限 / timeout）、test_allstar_config_contract
（六件共用契约，含 action=issue 与键集）、test_allstar_branch_protection_contract（谁能推送）。
上游事实来源（2026-11-11）：ossf/scorecard checks/raw/dangerous_workflow.go 的
containsUntrustedContextPattern / validateUntrustedCodeCheckout / validateScriptInjection；
ossf/allstar pkg/policies/workflow/workflow.go（委托 Scorecard + branchList 语义）。
"""
import copy
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".allstar" / "dangerous_workflow.yaml"
ALLOWED_KEYS = {"optConfig", "action", "branchList"}
#: Scorecard containsUntrustedContextPattern 的攻击者可控上下文（逐条镜像上游正则）。
UNTRUSTED_RE = re.compile(
    r"(issue\.title|issue\.body|pull_request\.title|pull_request\.body|discussion\.title|"
    r"discussion\.body|comment\.body|review\.body|review_comment\.body|pages.*\.page_name|"
    r"commits.*\.message|head_commit\.message|head_commit\.author\.email|"
    r"head_commit\.author\.name|commits.*\.author\.email|commits.*\.author\.name|"
    r"blocked_user\.name|blocked_user\.email|pull_request\.head\.ref|"
    r"pull_request\.head\.label|pull_request\.head\.repo\.default_branch)")
#: 序列化整个 github 上下文 = 不可信（scorecard issue #3554）。
TOJSON_RE = re.compile(r"(?i)tojson\s*\(\s*github(\.event)?\s*\)")
#: 不可信 checkout 只在特权触发下危险（PR base 分支 checkout 是默认行为、不危险）。
UNTRUSTED_CHECKOUT_TRIGGERS = {"pull_request_target", "workflow_run"}
UNTRUSTED_CHECKOUT_REFS = ("github.event.pull_request", "github.event.workflow_run")
#: webhook 攻击者输入触发：这些触发下 event 字段由外部用户控制。
ATTACK_INPUT_TRIGGERS = {"issues", "issue_comment", "pull_request_review",
                         "pull_request_review_comment", "discussion", "discussion_comment",
                         "pull_request_target", "workflow_run"}
CAVEAT_MARKERS = ("Scorecard", "Dangerous-Workflow", "branchList", "无法表达")
SECRET_MARKERS = ("token:", "secret:", "ghp_", "PRIVATE KEY")


def load_config(path: Path = CONFIG) -> dict:
    """读危险工作流配置（缺失 / 非法 YAML / 非映射 → ValueError）。"""
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ValueError("缺 PyYAML：" + str(exc)) from exc
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError("危险工作流配置不可读/不可解析：" + str(path) + "：" + str(exc)) from exc
    if not isinstance(doc, dict):
        raise ValueError("危险工作流配置根节点必须是映射：" + str(path))
    return doc


def tracked_workflows(root: Path = ROOT) -> list:
    """受跟踪的 workflow 相对路径（本地产物不参与，避免 .rivet / .worktrees 污染）。"""
    try:
        proc = subprocess.run(["git", "-C", str(root), "ls-files", "-z", ".github/workflows"],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=120)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("git ls-files 不可用：" + str(exc)) from exc
    return sorted(p for p in proc.stdout.split("\0")
                  if p.endswith((".yml", ".yaml")))


def trigger_events(doc: dict) -> set:
    """→ 触发事件名集合（PyYAML 把裸 on: 解析成布尔 True，必须两种键都认）。"""
    on = doc.get("on")
    if on is None:
        on = doc.get(True)
    if isinstance(on, str):
        return {on}
    if isinstance(on, list):
        return {str(x) for x in on}
    if isinstance(on, dict):
        return {str(k) for k in on}
    return set()


def expr_untrusted(expr: str) -> bool:
    """表达式内是否含攻击者可控上下文（镜像 Scorecard 判定）。"""
    if "github.head_ref" in expr:
        return True
    if TOJSON_RE.search(expr):
        return True
    return "github.event." in expr and bool(UNTRUSTED_RE.search(expr))


def run_findings(script: str, name: str, job_id: str) -> list:
    """run 脚本里逐个表达式检查（未闭合表达式记一类，避免静默漏检）。"""
    out = []
    rest = script
    while True:
        start = rest.find("${{")
        if start == -1:
            break
        end = rest.find("}}", start)
        if end == -1:
            out.append(("unclosed_expr", name, job_id, rest[start:start + 40]))
            break
        expr = rest[start + 3:end]
        if expr_untrusted(expr):
            out.append(("script_injection", name, job_id, expr.strip()))
        rest = rest[end:]
    return out


def scan_workflow(doc: dict, name: str = "<memory>") -> list:
    """→ [(类型, 文件, 作业, 细节)]；只覆盖 Scorecard 的两条规则。"""
    if not isinstance(doc, dict):
        return [("non_mapping", name, "", repr(doc)[:60])]
    findings = []
    events = trigger_events(doc)
    jobs = doc.get("jobs")
    for job_id, job in (jobs.items() if isinstance(jobs, dict) else []):
        if not isinstance(job, dict):
            continue
        for step in job.get("steps") or []:
            if not isinstance(step, dict):
                continue
            uses = step.get("uses")
            if (isinstance(uses, str) and "actions/checkout" in uses
                    and events & UNTRUSTED_CHECKOUT_TRIGGERS):
                ref = (step.get("with") or {}).get("ref")
                if isinstance(ref, str) and any(p in ref for p in UNTRUSTED_CHECKOUT_REFS):
                    findings.append(("untrusted_checkout", name, job_id, ref))
            run = step.get("run")
            if isinstance(run, str):
                findings.extend(run_findings(run, name, job_id))
    return findings


def scan_all(root: Path = ROOT) -> tuple:
    """→ (findings, 扫描文件数)。"""
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ValueError("缺 PyYAML：" + str(exc)) from exc
    findings = []
    files = tracked_workflows(root)
    for rel in files:
        doc = yaml.safe_load((root / rel).read_text(encoding="utf-8", errors="replace"))
        findings.extend(scan_workflow(doc, rel))
    return findings, len(files)


def config_issues(doc: dict, findings: list = None, scanned: int = 0, text: str = "") -> list:
    """危险工作流配置契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    findings = [] if findings is None else findings
    for key in sorted(set(doc) - ALLOWED_KEYS):
        issues.append("未知键（Allstar 静默忽略）：" + key)
    if doc.get("action") != "issue":
        issues.append("action 必须显式写 issue（默认 log 无任何可见结果）")
    opt = doc.get("optConfig")
    if not isinstance(opt, dict):
        issues.append("optConfig 必须是映射（与组织级模板逐字对齐）")
    elif opt.get("optOutStrategy") is not True:
        issues.append("optConfig.optOutStrategy 必须是布尔 true（组织级模板一致性）")
    if doc.get("branchList") not in (None, ""):
        issues.append("branchList 非空会收窄扫描面（留空 = 全分支；仓库级是追加不是替换）："
                      + repr(doc.get("branchList")))
    if not isinstance(scanned, int) or scanned < 20:
        issues.append("受跟踪 workflow 扫描面为空或过小（扫描面疑似失效）：" + repr(scanned))
    for finding in findings:
        issues.append("危险工作流命中（Scorecard Dangerous-Workflow）：" + repr(finding))
    for marker in CAVEAT_MARKERS:
        if text and marker not in text:
            issues.append("缺少检测面/边界说明：" + marker)
    if text:
        for marker in SECRET_MARKERS:
            if marker.lower() in text.lower():
                issues.append("不得包含凭据类字样：" + marker)
    return issues


class AllstarDangerousWorkflowContractTest(unittest.TestCase):
    def setUp(self):
        self.doc = load_config()
        self.text = CONFIG.read_text(encoding="utf-8")
        self.findings, self.scanned = scan_all()

    def test_config_matches_contract(self):
        self.assertEqual([], config_issues(self.doc, self.findings, self.scanned, self.text),
                         "危险工作流配置不满足契约")

    def test_scan_covers_all_branches(self):
        """branchList 留空 = 全分支扫描；改成 default / 具体分支都会收窄覆盖。"""
        self.assertNotIn("branchList", self.doc, "留空才等于扫描全部分支（仓库级追加语义）")
        self.assertIn("branchList", self.text, "必须写明 branchList 留空的理由")
        self.assertIn("全部分支", self.text, "必须写明留空 = 扫描全部分支")
        narrowed = copy.deepcopy(self.doc)
        narrowed["branchList"] = "default"
        self.assertTrue(any("收窄" in i for i in config_issues(
            narrowed, [], self.scanned, self.text)))

    def test_tracked_workflows_have_no_dangerous_patterns(self):
        """受跟踪 workflow 全量扫描必须零命中（Scorecard Dangerous-Workflow 两条规则）。"""
        self.assertEqual(len(tracked_workflows()), self.scanned, "扫描面应覆盖全部受跟踪 workflow")
        self.assertGreaterEqual(self.scanned, 20, "扫描面过小，判据可能已失效")
        self.assertEqual([], self.findings, "发现危险工作流写法")

    def test_privileged_triggers_are_audited(self):
        """特权触发面必须被审计：不得有 pull_request_target / workflow_run；webhook 输入
        只经 env: 间接传入。"""
        try:
            import yaml
        except ModuleNotFoundError as exc:
            raise ValueError("缺 PyYAML：" + str(exc)) from exc
        privilege, attack = {}, {}
        for rel in tracked_workflows():
            doc = yaml.safe_load((ROOT / rel).read_text(encoding="utf-8", errors="replace"))
            events = trigger_events(doc if isinstance(doc, dict) else {})
            name = rel.rsplit("/", 1)[-1]
            if events & UNTRUSTED_CHECKOUT_TRIGGERS:
                privilege[name] = sorted(events & UNTRUSTED_CHECKOUT_TRIGGERS)
            if events & ATTACK_INPUT_TRIGGERS:
                attack[name] = sorted(events & ATTACK_INPUT_TRIGGERS)
        self.assertEqual({}, privilege, "不可信 checkout 特权触发必须显式裁决后写进判据")
        self.assertLessEqual(set(attack), {"library-ingest.yml"},
                             "新增 webhook 攻击者输入面必须显式裁决后写进判据")
        for rel in tracked_workflows():
            if rel.rsplit("/", 1)[-1] not in attack:
                continue
            doc = yaml.safe_load((ROOT / rel).read_text(encoding="utf-8", errors="replace"))
            for job in (doc.get("jobs") or {}).values():
                if not isinstance(job, dict):
                    continue
                for step in job.get("steps") or []:
                    if not isinstance(step, dict):
                        continue
                    run = step.get("run")
                    if isinstance(run, str):
                        self.assertNotIn("github.event.issue", run,
                                         "攻击者输入不得内联进 run：" + rel)
                    env = step.get("env")
                    if isinstance(env, dict):
                        self.assertTrue(any("github.event.issue" in str(v)
                                            for v in env.values()),
                                        "攻击者输入应经 env 间接传入：" + rel)

    def test_contract_catches_broken_config(self):
        """变异自证：action=log / branchList 收窄 / 键名拼错 / 注入命中 / 删说明 / 坏 YAML，
        以及扫描器自证（危险写法必须被抓、env 间接写法不得误报）。"""
        base = {"scanned": self.scanned, "text": self.text}
        silent = copy.deepcopy(self.doc)
        silent["action"] = "log"
        self.assertTrue(any("action" in i for i in config_issues(silent, [], **base)))
        narrow = copy.deepcopy(self.doc)
        narrow["branchList"] = "refs/remotes/origin/main"
        self.assertTrue(any("收窄" in i for i in config_issues(narrow, [], **base)))
        typo = copy.deepcopy(self.doc)
        typo["branchlist"] = "default"
        self.assertTrue(any("未知键" in i for i in config_issues(typo, [], **base)))
        fake = config_issues(self.doc, [("script_injection", "x.yml", "j", "expr")], **base)
        self.assertTrue(any("危险工作流命中" in i for i in fake))
        no_caveat = "\n".join(line for line in self.text.splitlines()
                               if "Scorecard" not in line)
        self.assertTrue(any("缺少检测面" in i for i in config_issues(
            self.doc, [], **dict(base, text=no_caveat))))
        with self.assertRaises(ValueError):
            load_config(ROOT / ".allstar" / "no_such_dangerous_workflow.yaml")
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.yaml"
            bad.write_text("branchList: [unclosed\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_config(bad)
        # 扫描器自证：危险写法必须被抓、env 间接写法不得误报。
        checkout = {"on": {"pull_request_target": None}, "jobs": {"j": {"steps": [
            {"uses": "actions/checkout@abc",
             "with": {"ref": "${{ github.event.pull_request.head.sha }}"}},
        ]}}}
        self.assertTrue(scan_workflow(checkout, "x.yml"), "不可信 checkout 必须被抓")
        inject = {"on": {"issues": None}, "jobs": {"j": {"steps": [
            {"run": "echo ${{ github.event.issue.title }}"}]}}}
        self.assertTrue(scan_workflow(inject, "y.yml"), "脚本注入必须被抓")
        tojson = {"on": {"push": None}, "jobs": {"j": {"steps": [
            {"run": "${{ toJSON(github) }}"}]}}}
        self.assertTrue(scan_workflow(tojson, "z.yml"), "整上下文序列化必须被抓")
        safe = {"on": {"issues": None}, "jobs": {"j": {"steps": [
            {"env": {"TITLE": "${{ github.event.issue.title }}"},
             "run": 'echo "$TITLE"'}]}}}
        self.assertEqual([], scan_workflow(safe, "safe.yml"), "env 间接写法不得误报")


if __name__ == "__main__":
    unittest.main()
