package dev.ninfenz.mobile.design

import dev.ninfenz.mobile.ui.design.Contrast
import dev.ninfenz.mobile.ui.design.ContrastPairs
import dev.ninfenz.mobile.ui.design.Motion
import dev.ninfenz.mobile.ui.design.Palette
import dev.ninfenz.mobile.ui.design.Radius
import dev.ninfenz.mobile.ui.design.Sizes
import dev.ninfenz.mobile.ui.design.SourceKind
import dev.ninfenz.mobile.ui.design.Sources
import dev.ninfenz.mobile.ui.design.Space
import dev.ninfenz.mobile.ui.design.TypeScale
import dev.ninfenz.mobile.ui.design.shortHash
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

/** 令牌纪律：字号封闭、行高/间距上栅格、对比度过阈值、每个值都能溯源。 */
class DesignTokensTest {

    @Test
    fun typeSizesStayOnScale() {
        TypeScale.all.forEach { token ->
            assertTrue(
                "${token.name} 字号 ${token.size} 不在 ${TypeScale.allowedSizes}",
                token.size in TypeScale.allowedSizes
            )
        }
    }

    @Test
    fun lineHeightsSnapToGrid() {
        TypeScale.all.forEach { token ->
            assertEquals("${token.name} 行高 ${token.line}", 0f, token.line % 4f, 0.001f)
        }
    }

    @Test
    fun cjkTrackingIsZero() {
        TypeScale.all.forEach { token ->
            assertEquals("${token.name} 字距", 0f, token.tracking, 0.001f)
        }
    }

    @Test
    fun spacingIsMultipleOfFour() {
        Space.all.forEach { assertEquals("间距 $it", 0, it % 4) }
    }

    @Test
    fun radiusAndMotionFollowStandards() {
        assertEquals(listOf(4, 8, 12, 16, 28, 999), Radius.all)
        assertEquals(listOf(150, 250, 300), Motion.all)
        assertEquals(56, Sizes.listOneLine)
        assertEquals(72, Sizes.listTwoLine)
        assertEquals(48, Sizes.touchTarget)
    }

    @Test
    fun everyTokenHasRegisteredSource() {
        val ids = Sources.all.map { it.id }.toSet()
        assertEquals("source id 重复", Sources.all.size, ids.size)
        TypeScale.all.forEach { assertTrue("${it.name} 来源未登记", it.source.id in ids) }
        Palette.all.forEach { assertTrue("${it.name} 来源未登记", it.source.id in ids) }
    }

    @Test
    fun derivedTokensExplainThemselves() {
        TypeScale.all.filter { it.source.kind == SourceKind.S5 }.forEach { token ->
            assertNotNull("${token.name} 是 S5 推导，必须有公式/理由", token.derivedBy)
        }
    }

    @Test
    fun contrastPairsPassInBothThemes() {
        ContrastPairs.all.forEach { pair ->
            listOf(false, true).forEach { dark ->
                val ratio = Contrast.ratio(pair, dark)
                assertTrue(
                    "${pair.name} ${if (dark) "深色" else "浅色"} 对比度 $ratio < ${pair.min}",
                    ratio >= pair.min
                )
            }
        }
    }

    @Test
    fun contrastMathMatchesWcag() {
        assertEquals(21.0, Contrast.ratio(0xFFFFFFFF.toInt(), 0xFF000000.toInt()), 0.01)
        assertEquals(1.0, Contrast.ratio(0xFF123456.toInt(), 0xFF123456.toInt()), 0.001)
    }

    @Test
    fun hashGroupingKeepsHeadAndTail() {
        assertEquals("88d2 6e9a … a4b5", shortHash("88d26e9a4f1c2b3d4e5f60718293a4b5"))
        assertEquals("abcd ef01", shortHash("abcdef01"))
    }
}
