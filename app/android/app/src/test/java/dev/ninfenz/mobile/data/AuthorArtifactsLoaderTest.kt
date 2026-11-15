package dev.ninfenz.mobile.data

import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test

class AuthorArtifactsLoaderTest {

    private fun samplePack(): PackEntry? {
        val candidates = listOf(
            File("../../fixtures/sample-pack"),
            File("../fixtures/sample-pack"),
            File("app/fixtures/sample-pack")
        )
        val dir = candidates.firstOrNull { File(it, "nf-pack.json").isFile } ?: return null
        return PackEntry("demo-pack", "1.0.0", "示例", "d", 8, "4cb1502595c81614d6f924fac7f6acbad1b794412bf5a270cf2d111a5789a95e", dir)
    }

    @Test
    fun loadsProtocolGraphAndSpecFromPack() {
        val pack = samplePack()
        assumeTrue("sample-pack 缺失，跳过", pack != null)
        val artifacts = AuthorArtifactsLoader.load(pack!!)
        assertEquals("demo-protocol", artifacts.protocol.id)
        assertTrue(artifacts.protocol.clauses.isNotEmpty())
        assertEquals("demo-pipeline", artifacts.graph.id)
        assertTrue(artifacts.graph.nodes.isNotEmpty())
        assertEquals("demo-spec", artifacts.spec.id)
        assertTrue(artifacts.spec.sections.isNotEmpty())
    }

    @Test
    fun missingPackFilesFailClosed() {
        val dir = File(System.getProperty("java.io.tmpdir"), "nf-author-missing-" + System.nanoTime())
        dir.mkdirs()
        val pack = PackEntry("x", "1.0.0", "x", "x", 0, "a".repeat(64), dir)
        val failed = runCatching { AuthorArtifactsLoader.load(pack) }.isFailure
        assertTrue(failed)
    }
}
