package dev.ninfenz.mobile.ui.theme

import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.ui.unit.dp
import dev.ninfenz.mobile.ui.design.NfShape
import dev.ninfenz.mobile.ui.design.NfType
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
        assertEquals(RoundedCornerShape(4.dp), NfShape.shapes.extraSmall)
        assertEquals(RoundedCornerShape(8.dp), NfShape.shapes.small)
        assertEquals(RoundedCornerShape(12.dp), NfShape.shapes.medium)
        assertEquals(RoundedCornerShape(16.dp), NfShape.shapes.large)
        assertEquals(RoundedCornerShape(28.dp), NfShape.shapes.extraLarge)
    }

    @Test
    fun typographyUsesFourStepScale() {
        assertEquals(22f, NfType.screenTitle.fontSize.value)
        assertEquals(28f, NfType.screenTitle.lineHeight.value)
        assertEquals(16f, NfType.itemTitle.fontSize.value)
        assertEquals(24f, NfType.itemTitle.lineHeight.value)
        assertEquals(16f, NfType.body.fontSize.value)
        assertEquals(24f, NfType.body.lineHeight.value)
        assertEquals(14f, NfType.secondary.fontSize.value)
        assertEquals(20f, NfType.secondary.lineHeight.value)
        assertEquals(12f, NfType.meta.fontSize.value)
        assertEquals(20f, NfType.meta.lineHeight.value)
    }
}
