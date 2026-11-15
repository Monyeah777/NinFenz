package dev.ninfenz.mobile.ui

import androidx.compose.ui.test.assertIsDisplayed
import androidx.compose.ui.test.junit4.createComposeRule
import androidx.compose.ui.test.onNodeWithText
import androidx.compose.ui.test.performClick
import dev.ninfenz.mobile.ui.screens.CcosReviewActions
import dev.ninfenz.mobile.ui.theme.NfTheme
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34], qualifiers = "zh-rCN-w360dp-h640dp-xhdpi")
class CcosReviewActionsTest {
    @get:Rule
    val compose = createComposeRule()

    @Test
    fun approveAndRejectButtonsInvokeCallbacks() {
        var approved = false
        var rejected = false
        compose.setContent {
            NfTheme {
                CcosReviewActions(
                    busy = false,
                    outcome = "核心已接收结果",
                    onApprove = { approved = true },
                    onReject = { rejected = true }
                )
            }
        }
        compose.onNodeWithText("核心已接收结果").assertIsDisplayed()
        compose.onNodeWithText("通过并回传").performClick()
        compose.onNodeWithText("驳回").performClick()
        assertTrue(approved)
        assertTrue(rejected)
    }
}
