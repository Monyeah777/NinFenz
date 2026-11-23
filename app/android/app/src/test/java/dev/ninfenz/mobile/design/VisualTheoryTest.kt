package dev.ninfenz.mobile.design

import dev.ninfenz.mobile.ui.design.Contrast
import dev.ninfenz.mobile.ui.design.ContrastPairs
import dev.ninfenz.mobile.ui.design.Motion
import dev.ninfenz.mobile.ui.design.Palette
import dev.ninfenz.mobile.ui.design.Radius
import dev.ninfenz.mobile.ui.design.Space
import dev.ninfenz.mobile.ui.design.TypeScale
import dev.ninfenz.mobile.ui.design.VisualTheory
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class VisualTheoryTest {
    @Test
    fun everyRequiredTheoryConstructHasARule() {
        val covered = VisualTheory.rules.map { it.construct }.toSet()
        val missing = VisualTheory.requiredConstructs - covered
        assertTrue("missing theory constructs: $missing", missing.isEmpty())
    }

    @Test
    fun ruleIdsAreUniqueAndTraceable() {
        val ids = VisualTheory.rules.map { it.id }
        assertEquals(ids.size, ids.toSet().size)
        VisualTheory.rules.forEach {
            assertTrue("empty id", it.id.isNotBlank())
            assertTrue("empty source: ${it.id}", it.source.isNotBlank())
            assertTrue("empty token: ${it.id}", it.token.isNotBlank())
            assertTrue("empty rule: ${it.id}", it.rule.isNotBlank())
        }
    }

    @Test
    fun metricsHaveNoPretendInstrumentation() {
        assertEquals(VisualTheory.metrics.size, VisualTheory.metrics.map { it.id }.toSet().size)
        assertTrue(VisualTheory.metrics.any { !it.instrumented })
        VisualTheory.metrics.forEach {
            assertTrue("empty question: ${it.id}", it.question.isNotBlank())
            assertTrue("empty target: ${it.id}", it.target.isNotBlank())
        }
    }

    @Test
    fun spacingAndScaleStayOnTheGrid() {
        assertEquals(listOf(4, 8, 12, 16, 24, 32, 48), Space.all)
        Space.all.forEach { assertEquals(0, it % 4) }
        assertEquals(listOf(4, 8, 12, 16, 28, 999), Radius.all)
        assertEquals(setOf(22f, 16f, 14f, 12f), TypeScale.allowedSizes)
        assertTrue("type weights must stay <=3", TypeScale.all.map { it.weight }.toSet().size <= 3)
        assertEquals(listOf(150, 250, 300), Motion.all)
    }

    @Test
    fun allContrastPairsPassTheirMinimum() {
        assertTrue(ContrastPairs.all.size >= 18)
        ContrastPairs.all.forEach { pair ->
            val ratio = Contrast.ratio(pair.fg.light, pair.bg.light)
            assertTrue("${pair.name} light ratio $ratio < ${pair.min}", ratio >= pair.min)
        }
    }

    @Test
    fun statusIsNotOnlyColor() {
        // 状态 chip 的文案/形状由组件保证；这里锁住“状态色必须成对”的语义。
        assertTrue(Palette.error.name == "status.error")
        assertTrue(Palette.success.name == "status.success")
        assertTrue(Palette.warning.name == "status.warning")
        assertTrue(Palette.info.name == "status.info")
    }
}
