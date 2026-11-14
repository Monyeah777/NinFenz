# results/qa/（分层 QA 机读面）

> ⛔ 操作指令：本目录承载 §13A.2 L0–L20 分层 QA 的机读件；`layers.json`（`nf-qa-layers/1`）由 `core/layer_reports.py` 生成（committed==实时重算），人读索引在 `docs/qa/README.md`。未做的层如实 `partial`。
> 状态：v1（2026-11-15 · G5 收口补件）

复算：`python -c "import sys;sys.path.insert(0,'desktop/src');from core import layer_reports as l;l.write('.')"` → `python -m pytest desktop/tests/test_layer_reports.py -q`
