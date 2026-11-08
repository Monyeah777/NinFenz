"""九双生层同构判据**矩阵**：只允许「有测试点名」的层被算作已覆盖。

为什么（第 56 轮）：设计稿可以说「九条同构判据」，但仓库里必须有五条能指到具体测试方法。
本件把矩阵写成数据，并 **AST/反射校验** 每个「covered」条目的测试方法真实存在——
测试改名/删除就红，防止「覆盖状态」靠记忆维护。

矩阵现状（2026-11-08）：5 covered / 4 missing；missing 必须写明为什么现在写不出判据。
"""
import importlib
import unittest

#: 层 → (所属模块, 测试名, 覆盖形式)
COVERED = {
    "时相": ("desktop.tests.test_cognition_bridge",
             "test_commitment_binds_timestamp_reference",
             "commitment.ts_digest：两侧须指向同一 token"),
    "身份": ("desktop.tests.test_cognition_bridge", "test_verify_detects_state_change",
             "cog_digest ↔ state.digest：discourse 变了即红"),
    "观测": ("desktop.tests.test_cognition_bridge",
             "test_observation_layer_correspondence",
             "回灌记录与契约失败集逐项对应 + witness_digest 可复算"),
    "语义": ("desktop.tests.test_method_pack",
             "test_claim_kinds_come_from_single_vocabulary",
             "claim_kind 单一词表（包 ⇄ registry 同源，死词也红）"),
    "负空间": ("desktop.tests.test_cognition_control",
               "test_abstain_requires_search_boundary",
               "abstain 必带 searched 检索边界"),
}

#: 层 → 为什么现在写不出可红判据（缺的是对象，不是文案）
MISSING = {
    "授权": "契约侧已有 `approval.subject_digest` 绑定（改动即失效），"
           "但认知侧 control_record 无「谁授权」字段",
    "对抗": "`counterexample` move 有语义校验，但缺 `witness_ref` 引用对象（反例无法被 cc 复算）",
    "资源": "认知侧 `discourse.budget` 账实相符已守，验证侧只有 `perf_budget` 阈值、无逐次记账",
    "自省": "ADR 有 `falsifier` 但也无 `version_chain`（旧版验新版缺对象）",
}



#: 层 → (模块, 变异测试名)：证明该层判据**能被故意改坏打死**（不是只在好数据上为空）
KILL_TESTS = {
    "时相": ("desktop.tests.test_cognition_bridge",
             "test_commitment_binds_timestamp_reference"),
    "身份": ("desktop.tests.test_cognition_bridge", "test_verify_detects_state_change"),
    "观测": ("desktop.tests.test_cognition_bridge",
             "test_observation_correspondence_can_be_killed"),
    "语义": ("desktop.tests.test_method_pack",
             "test_vocabulary_check_can_be_killed"),
    "负空间": ("desktop.tests.test_cognition_control",
               "test_abstain_requires_search_boundary"),
}

def _import_test_module(module_name: str):
    """按「包路径」或「裸模块名」导入测试模块（两种跑法都要能工作）。

    为什么要有回退（第 86 轮实测）：分片跑测试时模块是**裸名**（`test_cognition_bridge`），
    此时 `importlib.import_module("desktop.tests....")` 会 ModuleNotFoundError——
    判据因此在前一次快照里 ERROR（不是 FAIL）。判据不能只在一种跑法下成立。
    """
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError:
        import sys
        from pathlib import Path

        here = str(Path(__file__).resolve().parent)
        if here not in sys.path:
            sys.path.insert(0, here)
        return importlib.import_module(module_name.rsplit(".", 1)[-1])


def _has_test(module_name: str, test_name: str) -> bool:
    """模块里是否存在该测试方法（反射查证；供正例与变异例共用）。"""
    mod = _import_test_module(module_name)
    return any(isinstance(getattr(mod, name), type)
               and hasattr(getattr(mod, name), test_name)
               for name in dir(mod) if name.endswith("Test"))


class IsomorphismMatrixTest(unittest.TestCase):
    def test_every_covered_layer_points_at_a_real_test(self):
        for layer, (module_name, test_name, _how) in COVERED.items():
            self.assertTrue(_has_test(module_name, test_name),
                            layer + " 声称已覆盖，但 " + module_name
                            + " 里找不到 " + test_name)

    def test_every_covered_layer_has_a_kill_test(self):
        """覆盖 ≠ 可证：每层都必须有一条「故意改坏必红」的变异测试，且真实存在。"""
        self.assertEqual(set(COVERED), set(KILL_TESTS),
                         "covered 与 kill 表必须一一对应")
        for layer, (module_name, test_name) in KILL_TESTS.items():
            self.assertTrue(_has_test(module_name, test_name),
                            layer + " 的变异测试不存在：" + test_name)

    def test_reflective_check_can_be_killed(self):
        """变异测试：指向不存在的测试方法时，反射查证必须返回 False。"""
        self.assertTrue(_has_test("desktop.tests.test_cognition_bridge",
                                  "test_commitment_binds_timestamp_reference"))
        self.assertFalse(_has_test("desktop.tests.test_cognition_bridge",
                                   "test_this_method_does_not_exist_xyz"))

    def test_both_import_styles_work_for_referenced_modules(self):
        """两种跑法都要能导入：包路径 + 裸模块名（分片跑测试时是裸名）。

        依据（第 86 轮快照实测）：判据曾因只支持包路径导入而在分片里 **ERROR**（不是 FAIL）。
        这条把「两种导入风格均可用」变成判据，覆盖 COVERED / KILL_TESTS 引用的全部模块。
        """
        referenced = sorted({m for m, _t, _h in COVERED.values()}
                            | {m for m, _t in KILL_TESTS.values()})
        for module in referenced:
            bare = module.rsplit(".", 1)[-1]
            self.assertIsNotNone(_import_test_module(module), module + " 包路径导入失败")
            self.assertIsNotNone(_import_test_module(bare), bare + " 裸名导入失败")

    def test_missing_layers_carry_a_reason(self):
        for layer, why in MISSING.items():
            self.assertTrue(why.strip(), layer + " 缺判据但没写原因")
        self.assertEqual(9, len(COVERED) + len(MISSING),
                         "九层必须恰好九项（多一层少一层都要改本判据）")
        self.assertEqual(5, len(COVERED), "覆盖数与设计稿不符，需显式更新矩阵")

    def test_missing_reasons_name_a_concrete_object(self):
        """missing 理由不能是「暂时没做」——必须点名一个具体字段/对象（反引号 token）。"""
        for layer, why in MISSING.items():
            self.assertRegex(why, r"`[A-Za-z0-9_.:/\-]+`",
                             layer + " 的缺失理由没有点名具体对象：" + why)

    def test_matrix_does_not_claim_overlap(self):
        self.assertEqual(set(), set(COVERED) & set(MISSING), "同一层不能既覆盖又缺失")


if __name__ == "__main__":
    unittest.main()
