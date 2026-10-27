"""重生成 CLI 命令面 golden 夹具（改了命令面才运行；行为面变更须在评审里说明）。

用法：python scripts/make_cli_surface.py
"""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from cli_surface_lib import serialize  # noqa: E402

spec = importlib.util.spec_from_file_location("nf_surface_probe", ROOT / "scripts" / "nf.py")
nf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(nf)

doc = serialize(nf._build_parser())
out = ROOT / "desktop" / "tests" / "fixtures" / "cli_surface.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n",
               encoding="utf-8", newline="\n")
print("wrote", out.relative_to(ROOT), "commands:", len(doc["commands"]))
