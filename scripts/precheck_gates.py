"""precheck 闸门名单（**数据件**，逻辑在 `precheck.py`）。

为什么单独成文件（第 81 轮）：`precheck.py` 已到模块行数上限（112），而名单本身还在增长；
把「数据」与「执行逻辑」拆开，既让名单可继续增长，也让 `precheck.py` 只留读写与渲染。
名单腐烂由 `test_precheck` 守（每个模块必须真实存在、id 唯一）。
"""

#: 快车道：每轮新增模块/命令/解析后最容易踩的横向面（顺序即优先级）
GATES = (
    ("json_shape", "desktop.tests.test_json_shape_contracts"),
    ("dead_code", "desktop.tests.test_dead_code"),
    ("atomic_write", "desktop.tests.test_core_atomic_writes"),
    ("silent_skip", "desktop.tests.test_silent_skip_reasons"),
    ("write_flag", "desktop.tests.test_write_flag_gate"),
    ("coupling_fresh", "desktop.tests.test_coupling_metrics"),
    ("docs_anchors", "desktop.tests.test_ccos_docs_anchors"),
    ("abi_docs", "desktop.tests.test_ccos_abi_docs"),
    ("method_pack", "desktop.tests.test_method_pack"),
    ("claims", "desktop.tests.test_cognition_claims"),
    ("bridge", "desktop.tests.test_cognition_bridge"),
    ("eval_harness", "desktop.tests.test_eval_harness"),
    ("calibration", "desktop.tests.test_calibration"),
    ("grouped_report", "desktop.tests.test_grouped_report"),
    ("evidence_graph", "desktop.tests.test_evidence_graph"),
    ("atom_catalog", "desktop.tests.test_atom_catalog"),
    ("cognition_control", "desktop.tests.test_cognition_control"),
    ("isomorphism", "desktop.tests.test_isomorphism_matrix"),
    ("clock_purity", "desktop.tests.test_judge_clock_purity"),
    ("report_determinism",
     "desktop.tests.test_verify_report.BuildTest.test_build_is_deterministic"),
    ("gate_probe", "desktop.tests.test_gate_probe"),
    ("judge_mutation", "desktop.tests.test_judge_mutation_probe"),
)

#: 慢但值得（--full 才跑）：CLI 面与纯度扫描约 2–3 分钟
SLOW_GATES = (
    ("cli_error_framing", "desktop.tests.test_cli_error_framing"),
    ("purity", "desktop.tests.test_purity_scan"),
)
