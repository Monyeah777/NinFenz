package dev.ninfenz.mobile

import androidx.test.ext.junit.runners.AndroidJUnit4
import androidx.test.platform.app.InstrumentationRegistry
import dev.ninfenz.mobile.data.EntitlementStore
import dev.ninfenz.mobile.data.FeatureGate
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith

/**
 * 真机（instrumentation）验证 Pro 离线授权：
 * 激活 → 层级切换 → 重启恢复（restore）→ 篡改拒绝 → 卸载语义（清空回 Free）。
 * 用 pin 公钥签发的测试向量；不联网、不依赖服务端。
 */
@RunWith(AndroidJUnit4::class)
class LicenseActivationAndroidTest {
    private val context get() = InstrumentationRegistry.getInstrumentation().targetContext

    private val validCode =
        "NF1.eyJiYXRjaCI6InZlY3Rvci0yMDI2LTExLTI4IiwiZWRpdGlvbiI6InBybyIsImlzc3VlZF9hdCI6IjIwMjYtMTEtMjgiLCJtYWpvciI6MCwib3JkZXIiOiJWRUNURVNULTAwMDEiLCJwcm9kdWN0IjoibmYtbW9iaWxlIiwidiI6MX0.FmRD_bf6vwtTyAfDrgC1uUvi4Jsm3fcm116p2OT-XltbZr4sCLfrtLm_VJOPvmzYrWrZcf0Xr7NPMb0LCLV_Bg"

    @Test
    fun activatesProOfflineAndRejectsTampering() = runBlocking {
        val previous = EntitlementStore.storedCode(context)
        try {
            EntitlementStore.deactivate(context)
            FeatureGate.resetForTest()
            assertEquals(FeatureGate.Tier.FREE, FeatureGate.tier())

            val state = EntitlementStore.activate(context, validCode)
            assertTrue(state.reason, state.valid)
            assertEquals("pro", state.edition)
            assertEquals("VECTEST-0001", state.order)
            assertEquals(FeatureGate.Tier.PRO, FeatureGate.tier())
            assertTrue(FeatureGate.auditEnabled())
            assertTrue(FeatureGate.allows("audit.validate"))
            assertTrue(EntitlementStore.isActivated(context))
            assertEquals("pro", EntitlementStore.storedEdition(context))
            assertEquals("VECTEST-0001", EntitlementStore.storedOrder(context))

            // 进程重启语义：层级回默认后 restore 应重新读到 PRO
            FeatureGate.resetForTest()
            EntitlementStore.restore(context)
            assertEquals(FeatureGate.Tier.PRO, FeatureGate.tier())

            // 篡改码必须拒绝，且不应降级已有授权
            val tampered = validCode.dropLast(1) + if (validCode.last() == 'A') "B" else "A"
            val rejected = EntitlementStore.activate(context, tampered)
            assertFalse(rejected.valid)
            assertEquals(FeatureGate.Tier.PRO, FeatureGate.tier())

            // 卸载/清空语义：deactivate 回 Free
            EntitlementStore.deactivate(context)
            FeatureGate.resetForTest()
            assertEquals(FeatureGate.Tier.FREE, FeatureGate.tier())
            assertFalse(EntitlementStore.isActivated(context))
        } finally {
            if (previous.isNotEmpty()) {
                EntitlementStore.activate(context, previous)
            } else {
                EntitlementStore.deactivate(context)
                FeatureGate.resetForTest()
            }
        }
    }
}
