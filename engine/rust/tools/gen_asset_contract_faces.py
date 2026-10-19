"""为 `asset_contract` 的三个**声明面整体判据**生成对拍 + 变异自证。

三个面（真源同名函数，`desktop/src/core/asset_contract.py`）：

| 面 | 真源函数 | 判据 |
|---|---|---|
| D1 两册合一 | `_registry_issues` | 本册声明为数据的 `protocol/**/*.json` 必须已在 `protocol/data_contracts.json` 登记 |
| ④ 导出漂移 | `_export_drift` | `protocol/generated/asset_contract.frictionless.json` == 实时 `frictionless_export` |
| ⑤ 声明自检 | `_schema_self_check` | 本册声明必须过 `protocol/schema/asset_contracts.schema.json` |

为什么需要本脚本：真语料上三面都是**空集**，oracle 只能核到「都对」这一侧——判据是否真的
接线、文案是否真的对齐，空集看不出来。故用**同一份夹具**同时喂两侧、并逐面做变异自证：

    clean（三面全绿）
      ├─ registration_missing（D1 红一条）
      ├─ export_drift（④ 红一条）
      ├─ schema_missing（⑤ 红一条）
      └─ restored（= clean，改回即同时回绿）

期望值**一律由真源现算**（本脚本调用 Python 侧函数），同一批文案写进两处：
- Rust：`engine/rust/src/asset_contract.rs` 的 `// >>> GENERATED` 段
  （`asset_contract_integral_faces_mutation_parity`）；
- Python：`desktop/tests/test_asset_contract_faces.py`（整份由本脚本生成）。
两处断言同一批 issue 文案 ⇒「两侧同时红 / 同时绿」被两份测试共同钉住。

用法：python engine/rust/tools/gen_asset_contract_faces.py
"""
import json
import pathlib
import pprint
import shutil
import sys

ROOT = pathlib.Path('.').resolve()
sys.path.insert(0, str(ROOT / 'desktop' / 'src'))
sys.path.insert(0, str(ROOT / 'engine' / 'rust' / 'tools'))
from _rustlit import raw as rr  # noqa: E402
from core import asset_contract as ac  # noqa: E402

FIX = ROOT / 'engine' / 'rust' / 'target' / 'test-fixtures' / 'asset-contract-faces'

#: 声明件：**只**声明一件数据真源（`protocol/probe.json`）——D1 的登记册判据只在
#: 「本册有 protocol 真源件」时才适用，故夹具必须有这一件，否则该面不参与（`targets` 空）。
DECL = {
    "schema": "nf-asset-contracts/1",
    "data": [{"format": "json", "id": "probe", "path": "protocol/probe.json"}],
    "code": [],
    "script": [],
    "index": [],
    "chains": [],
}
PROBE = {"a": 1}
REG_OK = {"schema": "nf-data-contracts/1",
          "contracts": [{"artifact": "protocol/probe.json", "id": "probe"}]}
REG_MISSING = {"schema": "nf-data-contracts/1", "contracts": []}
#: ⑤ 用最小可移植 schema（声明件是对象即通过）——本脚本要证的是「接线 + 文案」，
#: 不是再验一遍 `json_schema` 引擎（那条由 conformance/分支判据覆盖）。
SELF_SCHEMA = {"type": "object"}
#: ⑤ 的**校验分支**（schema 在场但声明不符）：与「缺件分支」是两支，必须各自踩到——
#: 只踩缺件时，把校验调用删成恒空也照样绿（实测：本轮变异自证抓到的假绿）。
SELF_SCHEMA_VIOLATING = {"type": "object", "required": ["schema", "no_such_key"]}


def dumps(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)


def base_files(export_text):
    """clean 夹具的全部件。`export_text` 由**真源实时导出**现算（见 `build_live_export`）。"""
    return {
        'protocol/asset_contracts.json': dumps(DECL) + "\n",
        'protocol/probe.json': dumps(PROBE) + "\n",
        'protocol/data_contracts.json': dumps(REG_OK) + "\n",
        'protocol/schema/asset_contracts.schema.json': dumps(SELF_SCHEMA) + "\n",
        'protocol/generated/asset_contract.frictionless.json': export_text,
    }


def build_live_export():
    """在临时树上跑真源 `frictionless_export`，拿「导出件应有的内容」。"""
    tmp = FIX / '_live'
    if tmp.exists():
        shutil.rmtree(tmp)
    for rel, text in base_files('\n').items():
        if rel.endswith('frictionless.json'):
            continue
        p = tmp / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')
    pkg, errs = ac.frictionless_export(str(tmp))
    if errs:
        raise SystemExit('真源 frictionless_export 报错，夹具前提不成立：%s' % errs)
    return json.dumps(pkg, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


EXPECTED_LIVE = build_live_export()
BASE = base_files(EXPECTED_LIVE)

#: 导出漂移：把导出件的 name 改掉（其余不变）——`_export_drift` 只比「有没有漂」。
DRIFTED_LIVE = json.dumps(json.loads(EXPECTED_LIVE) | {"name": "ninfenz-asset-contracts-drift"},
                          ensure_ascii=False, indent=2, sort_keys=True) + "\n"

CASES = [
    # (用例名, 覆盖的件, 删掉的件, 说明)
    ("clean", {}, [], "三面全绿（D1 已登记 / ④ 导出件==实时导出 / ⑤ 过可移植 schema）"),
    ("registration_missing", {'protocol/data_contracts.json': dumps(REG_MISSING) + "\n"},
     [], "变异：登记册少了 protocol/probe.json → D1 必须红"),
    ("export_drift",
     {'protocol/generated/asset_contract.frictionless.json': DRIFTED_LIVE},
     [], "变异：导出件与实时导出不一致 → ④ 必须红"),
    ("schema_missing", {}, ['protocol/schema/asset_contracts.schema.json'],
     "变异：可移植 schema 缺件 → ⑤ 的**缺件分支**必须红"),
    ("schema_violation",
     {'protocol/schema/asset_contracts.schema.json': dumps(SELF_SCHEMA_VIOLATING) + "\n"},
     [], "变异：schema 在场但声明不符（缺必填 no_such_key）→ ⑤ 的**校验分支**必须红"),
    ("restored", {}, [], "恢复：改回与 clean 同一份 → 三面必须同时回绿"),
]


def build_tree(name, overrides, deleted):
    d = FIX / gu(name)
    if d.exists():
        shutil.rmtree(d)
    for rel, text in BASE.items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')
    for rel, text in overrides.items():
        p = d / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding='utf-8')
    for rel in deleted:
        p = d / rel
        if p.exists():
            p.unlink()
    return d


def gu(name):
    """目录名：用例名保持可读（仅小写字母/下划线，无平台差异）。"""
    return 'case-' + name


def case_files(name, overrides, deleted):
    """该用例**完整**的件表（clean 基础上覆盖/删除）——Rust 侧据此重建同一棵树。"""
    files = dict(BASE)
    for rel in deleted:
        files.pop(rel, None)
    files.update(overrides)
    return sorted(files.items())


records = []
for name, overrides, deleted, why in CASES:
    d = build_tree(name, overrides, deleted)
    doc, load_issues = ac.load(str(d))
    if load_issues:
        raise SystemExit('%s 的声明件应可读，实得 %s' % (name, load_issues))
    reg = ac._registry_issues(str(d), doc)
    exp = ac._export_drift(str(d))
    sch = ac._schema_self_check(str(d))
    scan_issues, warns, stats = ac.scan(str(d))
    records.append({
        'name': name,
        'why': why,
        'files': case_files(name, overrides, deleted),
        'registry': reg,
        'export_drift': exp,
        'schema_self': sch,
        'scan_issues': scan_issues,
        'scan_stats': json.dumps(stats, ensure_ascii=False, sort_keys=True),
    })
    print('# %-22s registry=%d export=%d schema=%d scan=%d'
          % (name, len(reg), len(exp), len(sch), len(scan_issues)))
    for i in reg + exp + sch:
        print('#   -> %s' % i)

# 断言变异确实生效、恢复确实回绿（生成器自己先自证一遍，避免写出一份「恒绿」的期望值）
by = {r['name']: r for r in records}
assert not by['clean']['registry'] and not by['clean']['export_drift'] \
    and not by['clean']['schema_self'] and not by['clean']['scan_issues'], 'clean 必须全绿'
assert len(by['registration_missing']['registry']) == 1, 'registration_missing 必须红一条（D1）'
assert by['registration_missing']['registry'] == by['registration_missing']['scan_issues'], \
    'scan 的 issues 应与 D1 面逐字一致（其余面保持绿）'
assert len(by['export_drift']['export_drift']) == 1, 'export_drift 必须红一条（④）'
assert by['export_drift']['export_drift'] == by['export_drift']['scan_issues'], \
    'scan 的 issues 应与 ④ 面逐字一致（其余面保持绿）'
assert len(by['schema_missing']['schema_self']) == 1, 'schema_missing 必须红一条（⑤ 缺件分支）'
assert len(by['schema_violation']['schema_self']) == 1, 'schema_violation 必须红一条（⑤ 校验分支）'
assert by['schema_violation']['schema_self'] == by['schema_violation']['scan_issues'], \
    'scan 的 issues 应与 ⑤ 面逐字一致（其余面保持绿）'
for k in ('registry', 'export_drift', 'schema_self', 'scan_issues'):
    assert by['restored'][k] == by['clean'][k], 'restored 必须与 clean 逐字一致（%s）' % k

# ---------------------------------------------------------------- Rust 生成段
ARRS = {}
for r in records:
    ARRS[r['name']] = '        AcFaceFixture {\n' \
        '            name: %s,\n' \
        '            files: &[\n%s\n            ],\n' \
        '            registry: %s,\n' \
        '            export_drift: %s,\n' \
        '            schema_self: %s,\n' \
        '            scan_issues: %s,\n' \
        '            scan_stats: %s,\n' \
        '        },' % (
            rr(r['name']),
            '\n'.join('                (%s, %s),' % (rr(rel), rr(text))
                      for rel, text in r['files']),
            '&[%s]' % ', '.join(rr(x) for x in r['registry']),
            '&[%s]' % ', '.join(rr(x) for x in r['export_drift']),
            '&[%s]' % ', '.join(rr(x) for x in r['schema_self']),
            '&[%s]' % ', '.join(rr(x) for x in r['scan_issues']),
            rr(r['scan_stats']),
        )

RUST = '''
    // >>> GENERATED by tools/gen_asset_contract_faces.py（勿手改；重跑生成器覆盖本段）
    /// ===== 三个「声明面整体判据」（D1 / ④ / ⑤）的对拍 + 变异自证 =====
    ///
    /// 真语料上三面都是空集，oracle 只能核到「都对」那一侧——判据有没有接线、文案有没有对齐，
    /// 空集看不出来。故用**同一份夹具**逐面变异：clean（全绿）→ registration_missing /
    /// export_drift / schema_missing（各红一条）→ restored（= clean，改回即回绿）。
    ///
    /// 期望值由 `tools/gen_asset_contract_faces.py` 跑**真源同名函数**现算；同一批文案同时写进
    /// 本段与 `desktop/tests/test_asset_contract_faces.py` ⇒ 两侧断言同一批 issue。
    struct AcFaceFixture {
        name: &'static str,
        files: &'static [(&'static str, &'static str)],
        registry: &'static [&'static str],
        export_drift: &'static [&'static str],
        schema_self: &'static [&'static str],
        scan_issues: &'static [&'static str],
        scan_stats: &'static str,
    }

    const AC_FACE_CASES: &[AcFaceFixture] = &[
%s
    ];

    fn write_ac_face_fixture(root: &std::path::Path, files: &[(&str, &str)]) {
        for (rel, body) in files {
            let p = root.join(rel);
            if let Some(parent) = p.parent() {
                std::fs::create_dir_all(parent).expect("夹具父目录可建");
            }
            std::fs::write(&p, body).expect("夹具件可写");
        }
    }

    /// 三个声明面（D1 / ④ / ⑤）的 issues —— 与真源 `scan` 里的调用序一致。
    fn ac_face_issues(root: &std::path::Path) -> (Vec<String>, Vec<String>, Vec<String>) {
        let (doc, _load_issues) = load(root);
        (registry_issues(root, &doc), export_drift(root), schema_self_check(root))
    }

    #[test]
    fn asset_contract_integral_faces_mutation_parity() {
        for case in AC_FACE_CASES {
            let root = crate::testutil::fixture(&format!("asset-contract-faces-{}", case.name));
            write_ac_face_fixture(&root, case.files);
            let (reg, exp, sch) = ac_face_issues(&root);
            assert_eq!(reg, case.registry, "{} 的 D1 登记册 issues 不一致", case.name);
            assert_eq!(exp, case.export_drift, "{} 的 ④ 导出漂移 issues 不一致", case.name);
            assert_eq!(sch, case.schema_self, "{} 的 ⑤ 声明自检 issues 不一致", case.name);
            let (issues, _warns, stats) = scan(&root);
            assert_eq!(issues, case.scan_issues, "{} 的 scan issues 不一致", case.name);
            let want: Json = crate::jsonread::convert(
                &serde_json::from_str::<serde_json::Value>(case.scan_stats).unwrap(),
            )
            .unwrap();
            assert!(
                crate::jsonread::json_eq(&stats, &want),
                "{} 的 scan stats 不一致\\n  实得 {}\\n  期望 {}",
                case.name,
                stats.dumps(),
                want.dumps()
            );
        }
    }

    /// 真语料上三面必须**各自为空**（真源同语料实测见生成器输出）。
    ///
    /// 分开断言是为了**归因**：`asset_contract_scan_matches_truth_source` 只断言聚合 issues
    /// 为空，某面静默不接线时也能绿（这正是本次补齐前的既有缺口）。
    #[test]
    fn asset_contract_integral_faces_clean_on_real_corpus() {
        let root = ac_repo_root();
        let (doc, load_issues) = load(&root);
        assert!(load_issues.is_empty(), "真语料声明件须可读：{:?}", load_issues);
        assert_eq!(
            registry_issues(&root, &doc),
            Vec::<String>::new(),
            "真语料 D1 登记册面须空"
        );
        assert_eq!(export_drift(&root), Vec::<String>::new(), "真语料 ④ 导出漂移面须空");
        assert_eq!(
            schema_self_check(&root),
            Vec::<String>::new(),
            "真语料 ⑤ 声明自检面须空"
        );
    }
    // <<< GENERATED
''' % '\n'.join(ARRS[r['name']] for r in records)

BEGIN = '    // >>> GENERATED by tools/gen_asset_contract_faces.py（勿手改；重跑生成器覆盖本段）\n'
END = '    // <<< GENERATED\n'
path = ROOT / 'engine' / 'rust' / 'src' / 'asset_contract.rs'
t = path.read_text(encoding='utf-8')
block = BEGIN + RUST.split(BEGIN, 1)[1]
if BEGIN in t:
    a = t.index(BEGIN)
    b = t.index(END, a) + len(END)
    t = t[:a] + block + t[b:]
else:
    t = t.rstrip()[:-1].rstrip() + '\n' + block + '}\n'
path.write_text(t, encoding='utf-8', newline='')
print('# 已写入 asset_contract.rs 的三面变异自证段')

# ---------------------------------------------------------------- Python 对拍测试
PY_CASES = [{k: r[k] for k in ('name', 'why', 'files', 'registry', 'export_drift',
                               'schema_self', 'scan_issues', 'scan_stats')} for r in records]
PY = '''"""GENERATED by engine/rust/tools/gen_asset_contract_faces.py（勿手改；重跑生成器覆盖本文件）

三个**声明面整体判据**在真源侧的对拍 + 变异自证：
D1 登记册（`_registry_issues`）/ ④ 导出漂移（`_export_drift`）/ ⑤ 声明自检（`_schema_self_check`）。

同一批夹具与期望值同时写进 Rust 侧（`engine/rust/src/asset_contract.rs` 的
`asset_contract_integral_faces_mutation_parity`）——两侧断言的是**同一批 issue 文案**，
故「变异即同时红、恢复即同时绿」由两份测试共同钉住。
"""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "desktop" / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "desktop" / "src"))

from core import asset_contract as ac  # noqa: E402

CASES = %s


class AssetContractIntegralFacesTest(unittest.TestCase):
    """D1 / ④ / ⑤ 三面的逐面变异自证（与 Rust 侧同一批夹具、同一批文案）。"""

    def _build(self, tmp, files):
        for rel, text in files:
            p = Path(tmp) / rel
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")

    def test_faces_and_scan_match_generated_expectations(self):
        for case in CASES:
            with self.subTest(case=case["name"]):
                with tempfile.TemporaryDirectory() as tmp:
                    self._build(tmp, case["files"])
                    doc, load_issues = ac.load(tmp)
                    self.assertEqual(load_issues, [], case["name"])
                    self.assertEqual(ac._registry_issues(tmp, doc), case["registry"],
                                     "%%s 的 D1 登记册 issues 不一致" %% case["name"])
                    self.assertEqual(ac._export_drift(tmp), case["export_drift"],
                                     "%%s 的 ④ 导出漂移 issues 不一致" %% case["name"])
                    self.assertEqual(ac._schema_self_check(tmp), case["schema_self"],
                                     "%%s 的 ⑤ 声明自检 issues 不一致" %% case["name"])
                    issues, _warns, stats = ac.scan(tmp)
                    self.assertEqual(issues, case["scan_issues"],
                                     "%%s 的 scan issues 不一致" %% case["name"])
                    self.assertEqual(json.dumps(stats, ensure_ascii=False, sort_keys=True),
                                     case["scan_stats"], "%%s 的 scan stats 不一致" %% case["name"])


if __name__ == "__main__":
    unittest.main()
''' % pprint.pformat(PY_CASES, width=100, sort_dicts=True)

py_path = ROOT / 'desktop' / 'tests' / 'test_asset_contract_faces.py'
py_path.write_text(PY, encoding='utf-8', newline='')
print('# 已写入 desktop/tests/test_asset_contract_faces.py（%d 个用例夹具）' % len(PY_CASES))
