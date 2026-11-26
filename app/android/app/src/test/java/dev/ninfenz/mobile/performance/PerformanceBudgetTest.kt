package dev.ninfenz.mobile.performance

import dev.ninfenz.mobile.data.SearchHit
import dev.ninfenz.mobile.data.SearchIndex
import dev.ninfenz.mobile.data.SearchKind
import dev.ninfenz.mobile.model.MarkdownBlocks
import org.junit.Assert.assertTrue
import org.junit.Test

/** JVM 预算烟测：只证明模型层不回退；真机 60fps/内存仍需设备门禁。 */
class PerformanceBudgetTest {
    @Test
    fun parsesTenThousandBlocksUnderBudget() {
        val text = (1..10_000).joinToString("\n\n") { "段落 " + it }
        val started = System.nanoTime()
        val blocks = MarkdownBlocks.parse(text)
        val elapsedMs = (System.nanoTime() - started) / 1_000_000
        assertTrue("blocks=" + blocks.size, blocks.size >= 10_000)
        assertTrue("parse=" + elapsedMs + "ms", elapsedMs < 1_500)
    }

    @Test
    fun searchesTenThousandHitsUnderBudget() {
        val hits = (1..10_000).map { index ->
            SearchHit(
                kind = SearchKind.SECTION,
                title = "节 " + index,
                detail = "SEC-" + index,
                body = if (index == 7777) "needle target" else "ordinary body " + index
            )
        }
        val index = SearchIndex(java.nio.file.Files.createTempDirectory("nf-perf").toFile())
        val started = System.nanoTime()
        val found = index.search(hits, "needle")
        val elapsedMs = (System.nanoTime() - started) / 1_000_000
        assertTrue("found=" + found.size, found.isNotEmpty())
        assertTrue("search=" + elapsedMs + "ms", elapsedMs < 500)
    }
}
