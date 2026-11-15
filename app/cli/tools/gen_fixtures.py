"""生成并校验 app/fixtures 下的 schema 正反样例与 sample-pack / sample-pack-v2。

用法（仓库根，app/cli 在 PYTHONPATH）：
    python app/cli/tools/gen_fixtures.py            # 重新生成（覆盖夹具）
    python app/cli/tools/gen_fixtures.py --check    # 只校验（不写盘）

纪律：夹具是产物，生成器是唯一来源；改夹具先改这里，再跑测试。
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
TOOLS_DIR = HERE.parent
CLI_DIR = HERE.parents[1]
sys.path.insert(0, str(CLI_DIR))
sys.path.insert(0, str(TOOLS_DIR))

from fixtures_common import write_json  # noqa: E402
from invalid_docs import invalid_docs  # noqa: E402
from sample_pack import build_sample_packs  # noqa: E402
from valid_docs import valid_docs  # noqa: E402

REPO = CLI_DIR.parents[1]
FIXTURES = REPO / "app" / "fixtures"
SCHEMAS = REPO / "app" / "schema"


def schema_stems() -> list[str]:
    return sorted(p.name[: -len(".schema.json")] for p in SCHEMAS.glob("*.schema.json"))


def build_fixtures() -> dict:
    valid = valid_docs()
    valid_dir = FIXTURES / "schema" / "valid"
    invalid_dir = FIXTURES / "schema" / "invalid"
    for directory in (valid_dir, invalid_dir):
        if directory.exists():
            shutil.rmtree(directory)
    for stem, docs in valid.items():
        for index, doc in enumerate(docs, start=1):
            name = "minimal.json" if index == 1 else f"case-{index}.json"
            write_json(valid_dir / stem / name, doc)
    expected = {
        "schema": "nf-app-fixture-expectations/1",
        "note": (
            "invalid 夹具 → 期望错误码（码必须登记于 app/schema/error_codes.json）。"
            "测试断言：夹具被对应 schema 拒绝、映射与目录一致、code 已登记且 exit 与登记一致。"
        ),
        "fixtures": {},
    }
    for stem, name, doc, codes, violated in invalid_docs(valid):
        write_json(invalid_dir / stem / name, doc)
        expected["fixtures"][f"invalid/{stem}/{name}"] = {
            "schema": stem,
            "codes": codes,
            "violated": violated,
        }
    write_json(invalid_dir / "EXPECTED.json", expected)
    trees = build_sample_packs(FIXTURES)
    return {
        "valid": sum(len(docs) for docs in valid.values()),
        "invalid": len(expected["fixtures"]),
        "packs": trees,
    }


def check_fixtures() -> list[str]:
    """轻量自检：schema 正样例全过、反样例全拒、EXPECTED 与目录一致。"""
    import jsonschema

    problems: list[str] = []
    valid_dir = FIXTURES / "schema" / "valid"
    invalid_dir = FIXTURES / "schema" / "invalid"
    expected_path = invalid_dir / "EXPECTED.json"
    expected = json.loads(expected_path.read_text(encoding="utf-8")) if expected_path.is_file() else {"fixtures": {}}
    declared = set(expected.get("fixtures", {}))
    actual: set[str] = set()
    for stem in schema_stems():
        schema = json.loads((SCHEMAS / f"{stem}.schema.json").read_text(encoding="utf-8"))
        validator = jsonschema.Draft202012Validator(schema)
        vdir = valid_dir / stem
        idir = invalid_dir / stem
        if not vdir.is_dir() or not list(vdir.glob("*.json")):
            problems.append(f"{stem}: 缺正样例")
        else:
            for path in sorted(vdir.glob("*.json")):
                errs = list(validator.iter_errors(json.loads(path.read_text(encoding="utf-8"))))
                if errs:
                    problems.append(f"正样例被拒: {path}: {errs[0].message}")
        if not idir.is_dir() or len(list(idir.glob("*.json"))) < 2:
            problems.append(f"{stem}: 反样例少于 2")
        else:
            for path in sorted(idir.glob("*.json")):
                rel = f"invalid/{stem}/{path.name}"
                actual.add(rel)
                errs = list(validator.iter_errors(json.loads(path.read_text(encoding="utf-8"))))
                if not errs:
                    problems.append(f"反样例未被拒: {path}")
                if rel not in declared:
                    problems.append(f"反样例未登记期望码: {rel}")
    for extra in sorted(declared - actual):
        problems.append(f"EXPECTED 指向不存在的夹具: {extra}")
    return problems


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(description="生成/校验 app/fixtures 夹具")
    parser.add_argument("--check", action="store_true", help="只校验不写盘")
    args = parser.parse_args(argv)
    if args.check:
        problems = check_fixtures()
    else:
        stats = build_fixtures()
        problems = check_fixtures()
        print(f"generated: valid={stats['valid']} invalid={stats['invalid']} v1={stats['packs']['v1_tree'][:12]} v2={stats['packs']['v2_tree'][:12]}")
    for line in problems:
        print("FAIL", line)
    print("fixtures ok" if not problems else f"{len(problems)} problems")
    return 0 if not problems else 1


if __name__ == "__main__":
    raise SystemExit(main())
