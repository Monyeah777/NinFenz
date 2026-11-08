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
    "时相": ("desktop.tests.test_cognition_bridge", "test_commitment_binds_timestamp_reference",
             "commitment.ts_digest：两侧须指向同一 token"),
    "身份": ("desktop.tests.test_cognition_bridge", "test_verify_detects_state_change",
             "cog_digest ↔ state.digest：discourse 变了即红"),
    "观测": ("desktop.tests.test_cognition_bridge", "test_observation_layer_correspondence",
             "回灌记录与契约失败集逐项对应 + witness_digest 可复算"),
    "语义": ("desktop.tests.test_method_pack",
             "test_claim_kinds_come_from_single_vocabulary",
             "claim_kind 单一词表（包 ⇄ registry 同源，死词也红）"),
    "负空间": ("desktop.tests.test_cognition_control", "test_abstain_requires_search_boundary",
               "abstain 必带 searched 检索边界"),
}

#: 层 → 为什么现在写不出可红判据（缺的是对象，不是文案）
MISSING = {
    "授权": "K5 capability 只有工具级雏形，没有「授权即证据」的信封对象可做两侧核对",
    "对抗": "counterexample move 有语义校验，但没有「反例能被 cc 复算成 fail witness」的对象",
    "资源": "认知预算与验证预算两本账都未落状态，无法比对",
    "自省": "自举（旧版验新版）尚无版本链对象；ADR falsifier 只覆盖部分",
}


class IsomorphismMatrixTest(unittest.TestCase):
    def test_every_covered_layer_points_at_a_real_test(self):
        for layer, (module_name, test_name, _how) in COVERED.items():
            mod = importlib.import_module(module_name)
            found = [n for n in dir(mod)
                     if n.startswith("Test") or n.endswith("Test")]
            holder = None
            for name in found:
                obj = getattr(mod, name)
                if isinstance(obj, type) and hasattr(obj, test_name):
                    holder = name
                    break
            self.assertIsNotNone(holder,
                                 layer + " 声称已覆盖，但 " + module_name + " 里找不到 " + test_name)

    def test_missing_layers_carry_a_reason(self):
        for layer, why in MISSING.items():
            self.assertTrue(why.strip(), layer + " 缺判据但没写原因")
        self.assertEqual(9, len(COVERED) + len(MISSING), "九层必须恰好九项（多一层少一层都要改本判据）")
        self.assertEqual(5, len(COVERED), "覆盖数与设计稿不符，需显式更新矩阵")

    def test_matrix_does_not_claim_overlap(self):
        self.assertEqual(set(), set(COVERED) & set(MISSING), "同一层不能既覆盖又缺失")


if __name__ == "__main__":
    unittest.main()