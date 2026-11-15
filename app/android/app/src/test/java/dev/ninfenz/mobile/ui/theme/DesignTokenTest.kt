package dev.ninfenz.mobile.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.unit.dp
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DesignTokenTest {

    @Test
    fun spacingIsMultipleOf4() {
        val values = listOf(NfSpacing.xs, NfSpacing.s, NfSpacing.m, NfSpacing.l, NfSpacing.xl, NfSpacing.xxl, NfSpacing.xxxl, NfSpacing.page)
        for (value in values) {
            assertTrue("非 4dp 倍数：" + value, value.value % 4f == 0f)
        }
    }

    @Test
    fun shapesUseTokenScale() {
        assertEquals(RoundedCornerShape(4.dp), NfShapes.extraSmall)
        assertEquals(RoundedCornerShape(8.dp), NfShapes.small)
        assertEquals(RoundedCornerShape(12.dp), NfShapes.medium)
        assertEquals(RoundedCornerShape(16.dp), NfShapes.large)
        assertEquals(RoundedCornerShape(24.dp), NfShapes.extraLarge)
    }

    @Test
    fun typographyUsesSevenStepScale() {
        assertEquals(32f, NfTypography.displaySmall.fontSize.value)
        assertEquals(40f, NfTypography.displaySmall.lineHeight.value)
        assertEquals(24f, NfTypography.headlineSmall.fontSize.value)
        assertEquals(20f, NfTypography.titleLarge.fontSize.value)
        assertEquals(16f, NfTypography.titleMedium.fontSize.value)
        assertEquals(14f, NfTypography.bodyMedium.fontSize.value)
        assertEquals(23f, NfTypography.bodyMedium.lineHeight.value)
        assertEquals(11f, NfTypography.labelSmall.fontSize.value)
    }
}
