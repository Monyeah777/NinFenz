"""P-C5 判据：密封跑法（Dockerfile.crosscheck）与 CI 接线必须是**真钉住**的，不是摆样子。

为什么单列：密封最容易做成「写了个 Dockerfile」——基础镜像用 tag、SDK 不校验哈希、CI 里
装的是 latest。这些都不会报错，只会让「环境可复现」变成一句无法复核的话。故本判据只认：
  - 每个 FROM 都带 @sha256:；
  - 无法用镜像钉住的输入（.NET SDK）在构建期**真做**哈希校验；
  - CI 不重复整仓基线门（verify.sh 只有 ci-verify 一份），且以 full 模式跑矩阵；
  - 每个 uses: 都钉到 commit SHA。
本机无容器引擎 ⇒ 容器**跑不跑**由 CI 承载；本地降级面是 cross_lang_verify.py --digest。
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCKERFILE = ROOT / "Dockerfile.crosscheck"
DOCKERIGNORE = ROOT / ".dockerignore"
WORKFLOW = ROOT / ".github" / "workflows" / "cross-lang.yml"
VERIFY = ROOT / "scripts" / "cross_lang_verify.py"


def _from_lines(text: str) -> list[str]:
    return [ln.strip() for ln in text.splitlines() if ln.strip().upper().startswith("FROM ")]


def _code_lines(text: str) -> str:
    """去掉整行注释后的正文——「不重复基线门」要判的是**执行**，不是注释里提了一嘴。"""
    kept = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("//"):
            continue
        kept.append(line)
    return "\n".join(kept)


def _arg_defaults(text: str) -> dict:
    """ARG 的默认值。FROM 常用 $VAR 间接钉 digest，只看 FROM 行会漏判。"""
    return {m.group(1): m.group(2)
            for m in re.finditer(r"(?m)^ARG\s+([A-Za-z_][A-Za-z0-9_]*)=(\S+)\s*$", text)}


def _resolve_image(image: str, defaults: dict) -> str:
    m = re.fullmatch(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", image)
    return defaults.get(m.group(1), "") if m else image


class DockerfileTest(unittest.TestCase):
    def test_every_from_resolves_to_a_digest_pinned_image(self):
        text = DOCKERFILE.read_text(encoding="utf-8")
        lines = _from_lines(text)
        self.assertGreaterEqual(len(lines), 2, "多阶段构建至少两个 FROM")
        defaults = _arg_defaults(text)
        unpinned = []
        for line in lines:
            image = line.split()[1]
            resolved = _resolve_image(image, defaults)
            if "@sha256:" not in resolved:
                unpinned.append(f"{image} -> {resolved or '(ARG 未定义默认值)'}")
        self.assertEqual([], unpinned, f"这些 FROM 没解析到 digest：{unpinned}")

    def test_arg_placeholders_are_all_defined(self):
        text = DOCKERFILE.read_text(encoding="utf-8")
        used = set(re.findall(r"(?m)^FROM\s+\$\{([A-Za-z_][A-Za-z0-9_]*)\}", text))
        self.assertTrue(used, "FROM 应有 ARG 化的镜像名（便于换版本时连哈希一起换）")
        self.assertEqual(set(), used - set(_arg_defaults(text)), "FROM 引用了没有默认值的 ARG")

    def test_net_sdk_input_is_hash_verified_at_build_time(self):
        text = DOCKERFILE.read_text(encoding="utf-8")
        self.assertIn("DOTNET_SDK_SHA512", text)
        self.assertRegex(text, r"sha512sum\s+-c\s+-", "SDK 必须真做哈希校验，不是只写在注释里")
        self.assertRegex(text, r"\$\{DOTNET_SDK_URL\}", "URL 必须来自 ARG（换版本即换哈希）")

    def test_runs_the_matrix_in_full_mode(self):
        text = DOCKERFILE.read_text(encoding="utf-8")
        self.assertIn("--require-full", text)
        for name in ("jcs_conformance.json", "jcs_reject.json"):
            self.assertIn(name, text, f"密封跑法必须覆盖 {name}")
        self.assertIn("--coverage", text, "覆盖棘轮也要在密封里跑")

    def test_does_not_duplicate_the_repository_gate(self):
        # 「整仓基线门」只有 ci-verify 一份；密封镜像里若也跑 verify.sh，就出现第二个权威。
        self.assertNotIn("verify.sh", _code_lines(DOCKERFILE.read_text(encoding="utf-8")))

    def test_build_context_excludes_artifacts(self):
        text = DOCKERIGNORE.read_text(encoding="utf-8")
        for pattern in ("**/target/", "**/bin/", "**/obj/", ".rivet"):
            self.assertIn(pattern, text, f".dockerignore 须排除 {pattern}")


class PipelineWiringTest(unittest.TestCase):
    def test_workflow_triggers_on_push_to_main(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertRegex(text, r"(?m)^on:\s*$")
        self.assertRegex(text, r"(?m)^\s{2}push:\s*$")
        self.assertRegex(text, r"(?m)^\s{4}branches:\s*\[main\]\s*$")

    def test_every_action_is_pinned_to_a_commit_sha(self):
        text = WORKFLOW.read_text(encoding="utf-8")
        refs = re.findall(r"uses:\s*(\S+)", text)
        self.assertTrue(refs, "工作流里应有 checkout 之类的 action")
        bad = [r for r in refs if not re.search(r"@[0-9a-f]{40}$", r)]
        self.assertEqual([], bad, f"未钉 SHA 的 action：{bad}")

    def test_full_mode_and_coverage_ratchet_are_wired(self):
        text = _code_lines(WORKFLOW.read_text(encoding="utf-8"))
        self.assertGreaterEqual(text.count("--require-full"), 2, "两条清单都要 full 模式")
        self.assertIn("--coverage", text)
        # 逐清单确认：full 模式真的挂在两条清单上，而不是只挂了一条
        for name in ("jcs_conformance.json", "jcs_reject.json"):
            block = text.split(name, 1)[1][:200]
            self.assertIn("--require-full", block, f"{name} 未以 full 模式跑")

    def test_workflow_does_not_rerun_the_repository_gate(self):
        self.assertNotIn("verify.sh", _code_lines(WORKFLOW.read_text(encoding="utf-8")),
                         "整仓基线门归 ci-verify.yml；这里只跑矩阵")

    def test_local_fallback_face_exists(self):
        # 本机无容器引擎 ⇒ 降级面必须真在场：--digest 记录工具链版本与产物 sha256。
        text = VERIFY.read_text(encoding="utf-8")
        self.assertIn("--digest", text)
        self.assertIn("def collect_digests", text)


if __name__ == "__main__":
    unittest.main()
