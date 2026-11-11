#!/usr/bin/env python3
"""Allstar Binary Artifacts 契约判据：配置白名单为空 + 全仓零二进制工件（2026-11-11）。

为什么必须有：binary_artifacts.yaml 此前是 4 行 stub；而该策略的实际内容就是「仓库里有哪些二进制
工件、哪些被放行」。上游把检测委托给 OpenSSF Scorecard 的 Binary-Artifacts 检查：前 1024 字节
magic 命中可执行/打包格式即算，或扩展名属该集合并内容非文本也算（图片/字体/普通 zip 不算）。仓库级
唯一调节面是 ignorePaths（完整路径白名单、不支持 glob）——写一条就放行一个路径，而 fail-open 的
解析让写错键名不会红。本件把「受跟踪文件零二进制 + 白名单为空」钉成契约：新增二进制会红；要放行必须
同时在配置里写明理由、并在本判据的已审计白名单登记。

范围：只判 .allstar/binary_artifacts.yaml + 对 git 跟踪面的只读扫描（本地产物不参与）。
上游事实来源（2026-11-11）：ossf/scorecard checks/raw/binary_artifact.go 的
checkBinaryFileReader / binaryFileTypes / isText / binaryTestLen=1024；ossf/allstar
pkg/policies/binary/binary.go 的 OrgConfig(ignoreFiles) / RepoConfig(ignorePaths) 与合并语义。
"""
import copy
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / ".allstar" / "binary_artifacts.yaml"
ALLOWED_KEYS = {"optConfig", "action", "ignorePaths"}
#: 已审计放行白名单（当前为空）。每加一条都必须同时写进配置注释并附理由，不能只改配置。
AUDITED_IGNORES = frozenset()
#: Scorecard binaryFileTypes 集合（逐条镜像上游）。
BINARY_EXTS = frozenset({
    "crx", "deb", "dex", "dey", "elf", "o", "a", "so", "macho", "iso", "class", "jar",
    "bundle", "dylib", "lib", "msi", "dll", "drv", "efi", "exe", "ocx", "pyc", "pyo",
    "par", "rpm", "wasm", "whl",
})
#: magic → 扩展名（只取可执行/打包格式；用 hex 字面量避免源码转义歧义）。
MAGIC = (
    ("7f454c46", "elf"),            # 0x7f ELF
    ("4d5a", "exe"),                # MZ / PE
    ("cffaedfe", "macho"),
    ("cefaedfe", "macho"),
    ("feedfacf", "macho"),
    ("feedface", "macho"),
    ("cafebabe", "class"),          # fat Mach-O / Java class 共用魔数
    ("0061736d", "wasm"),           # 0x00 asm
    ("43723234", "crx"),            # Cr24
    ("edabeedb", "rpm"),
    ("213c617263683e", "a"),        # !<arch>
)
BINARY_TEST_LEN = 1024              # 上游只看前 1024 字节
CAVEAT_MARKERS = ("Scorecard", "Binary-Artifacts", "ignorePaths", "无法表达")
SECRET_MARKERS = ("token:", "secret:", "ghp_", "PRIVATE KEY")
GLOB_CHARS = ("*", "?", "[")


def load_config(path: Path = CONFIG) -> dict:
    """读二进制工件配置（缺失 / 非法 YAML / 非映射 → ValueError）。"""
    try:
        import yaml
    except ModuleNotFoundError as exc:
        raise ValueError("缺 PyYAML：" + str(exc)) from exc
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        raise ValueError("二进制工件配置不可读/不可解析：" + str(path) + "：" + str(exc)) from exc
    if not isinstance(doc, dict):
        raise ValueError("二进制工件配置根节点必须是映射：" + str(path))
    return doc


def tracked_files(root: Path = ROOT) -> list:
    """git 跟踪面（本地产物不参与扫描）。"""
    try:
        proc = subprocess.run(["git", "-C", str(root), "ls-files", "-z"],
                              capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=180)
    except (OSError, subprocess.SubprocessError) as exc:
        raise ValueError("git ls-files 不可用：" + str(exc)) from exc
    return [p for p in proc.stdout.split("\0") if p]


def is_text(data: bytes) -> bool:
    """镜像上游 isText：出现非 \n\t\r 的控制字符即非文本。"""
    return all(byte >= 0x20 or byte in (0x0A, 0x09, 0x0D)
               for byte in data[:BINARY_TEST_LEN])


def magic_ext(data: bytes) -> str:
    """前 1024 字节 magic → 扩展名（未命中返回空串）。"""
    head = data[:BINARY_TEST_LEN]
    for hexstr, ext in MAGIC:
        if head.startswith(bytes.fromhex(hexstr)):
            return ext
    return ""


def check_file(rel: str, data: bytes) -> str:
    """→ 命中类型（magic:xxx / ext:xxx）或空串；空文件跳过（镜像上游）。"""
    if not data:
        return ""
    fmt = magic_ext(data)
    if fmt in BINARY_EXTS:
        return "magic:" + fmt
    ext = rel.rsplit(".", 1)[-1].lower() if "." in rel else ""
    if ext in BINARY_EXTS and not is_text(data):
        return "ext:" + ext
    return ""


def scan_tracked(root: Path = ROOT) -> tuple:
    """→ ([(路径, 命中类型)], 扫描文件数)。"""
    files = tracked_files(root)
    hits = []
    for rel in files:
        try:
            data = (root / rel).read_bytes()[:BINARY_TEST_LEN]
        except OSError:
            continue
        kind = check_file(rel, data)
        if kind:
            hits.append((rel, kind))
    return hits, len(files)


def ignore_issues(entries) -> list:
    """ignorePaths 必须是完整路径 list、不能有 glob、且每条都要在已审计白名单里。"""
    if entries is None:
        return []
    if not isinstance(entries, list):
        return ["ignorePaths 必须是 list（上游仅支持完整路径）"]
    issues = []
    for entry in entries:
        if not isinstance(entry, str) or not entry.strip():
            issues.append("ignorePaths 条目必须是非空字符串：" + repr(entry))
            continue
        if any(ch in entry for ch in GLOB_CHARS):
            issues.append("ignorePaths 不支持 glob（必须是完整路径）：" + entry)
        if entry not in AUDITED_IGNORES:
            issues.append("ignorePaths 条目未审计（当前白名单为空，等于凭空放行）：" + entry)
    return issues


def config_issues(doc: dict, hits: list = None, tracked: int = 0, text: str = "") -> list:
    """二进制工件配置契约问题列表（纯函数，便于变异自证）。"""
    issues = []
    hits = [] if hits is None else hits
    for key in sorted(set(doc) - ALLOWED_KEYS):
        issues.append("未知键（Allstar 静默忽略）：" + key)
    if doc.get("action") != "issue":
        issues.append("action 必须显式写 issue（默认 log 无任何可见结果）")
    opt = doc.get("optConfig")
    if not isinstance(opt, dict):
        issues.append("optConfig 必须是映射（与组织级模板逐字对齐）")
    elif opt.get("optOutStrategy") is not True:
        issues.append("optConfig.optOutStrategy 必须是布尔 true（组织级模板一致性）")
    issues.extend(ignore_issues(doc.get("ignorePaths")))
    if not isinstance(tracked, int) or tracked < 4000:
        issues.append("跟踪面为空或过小（扫描面疑似失效）：" + repr(tracked))
    for rel, kind in hits:
        issues.append("二进制工件（Scorecard Binary-Artifacts）：" + rel + " [" + kind + "]")
    for marker in CAVEAT_MARKERS:
        if text and marker not in text:
            issues.append("缺少检测面/边界说明：" + marker)
    if text:
        for marker in SECRET_MARKERS:
            if marker.lower() in text.lower():
                issues.append("不得包含凭据类字样：" + marker)
    return issues


class AllstarBinaryArtifactsContractTest(unittest.TestCase):
    def setUp(self):
        self.doc = load_config()
        self.text = CONFIG.read_text(encoding="utf-8")
        self.hits, self.tracked = scan_tracked()

    def test_config_matches_contract(self):
        self.assertEqual([], config_issues(self.doc, self.hits, self.tracked, self.text),
                         "二进制工件配置不满足契约")

    def test_ignore_paths_stay_empty(self):
        """零命中的前提下 ignorePaths 必须为空；任何未审计条目/glob 都必须报。"""
        self.assertNotIn("ignorePaths", self.doc, "零命中时白名单必须为空")
        self.assertIn("ignorePaths", self.text, "必须写明 ignorePaths 留空的理由")
        one = copy.deepcopy(self.doc)
        one["ignorePaths"] = ["desktop/bin/tool.exe"]
        self.assertTrue(any("未审计" in i for i in config_issues(
            one, [], self.tracked, self.text)))
        glob = copy.deepcopy(self.doc)
        glob["ignorePaths"] = ["*.dll"]
        self.assertTrue(any("glob" in i for i in config_issues(
            glob, [], self.tracked, self.text)))

    def test_tracked_files_have_no_binary_artifacts(self):
        """受跟踪文件全量扫描必须零命中（Scorecard Binary-Artifacts 判定）。"""
        self.assertEqual(len(tracked_files()), self.tracked, "扫描面应覆盖全部受跟踪文件")
        self.assertGreaterEqual(self.tracked, 4000, "扫描面过小，判据可能已失效")
        self.assertEqual([], self.hits, "发现二进制工件")

    def test_detector_mirrors_scorecard(self):
        """检测器自证：可执行/打包格式必抓；图片/字体/文本/空文件不得误报。"""
        self.assertEqual("magic:elf", check_file("x.bin", bytes.fromhex("7f454c46") + b"\x00"))
        self.assertEqual("magic:exe", check_file("x.dat", bytes.fromhex("4d5a") + b"\x00"))
        self.assertEqual("magic:macho", check_file("x.dat", bytes.fromhex("cffaedfe") + b"\x00"))
        self.assertEqual("magic:wasm", check_file("x.dat", bytes.fromhex("0061736d") + b"\x00"))
        self.assertEqual("ext:jar", check_file("lib/a.jar", b"PK\x03\x04\x00\x00"))
        self.assertEqual("ext:pyc", check_file("a.pyc", b"\x00\x01\x02\x03"))
        self.assertEqual("", check_file("logo.png", bytes.fromhex("89504e47") + b"\x00\x01"))
        self.assertEqual("", check_file("a.zip", b"PK\x03\x04\x00\x00"))
        self.assertEqual("", check_file("README.md", b"# hello\n"))
        self.assertEqual("", check_file("notes.a", b"plain text\n"))
        self.assertEqual("", check_file("empty.jar", b""))

    def test_contract_catches_broken_config(self):
        """变异自证：action=log / 未审计放行 / 键名拼错 / 命中注入 / 删说明 / 坏 YAML。"""
        base = {"tracked": self.tracked, "text": self.text}
        silent = copy.deepcopy(self.doc)
        silent["action"] = "log"
        self.assertTrue(any("action" in i for i in config_issues(silent, [], **base)))
        typo = copy.deepcopy(self.doc)
        typo["ignorepaths"] = []
        self.assertTrue(any("未知键" in i for i in config_issues(typo, [], **base)))
        fake = config_issues(self.doc, [("desktop/bin/a.exe", "magic:exe")], **base)
        self.assertTrue(any("二进制工件" in i for i in fake))
        no_caveat = "\n".join(line for line in self.text.splitlines()
                               if "Binary-Artifacts" not in line)
        self.assertTrue(any("缺少检测面" in i for i in config_issues(
            self.doc, [], **dict(base, text=no_caveat))))
        with self.assertRaises(ValueError):
            load_config(ROOT / ".allstar" / "no_such_binary_artifacts.yaml")
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.yaml"
            bad.write_text("ignorePaths: [unclosed\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_config(bad)


if __name__ == "__main__":
    unittest.main()
