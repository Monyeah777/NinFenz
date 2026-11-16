package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ProjectRenamerTest {
    private val doc = "{\"schema\":\"nf-project/1\",\"id\":\"p\",\"title\":\"旧标题\",\"refs\":{" +
        "\"base_pack\":{\"id\":\"pack\",\"version\":\"1.0.0\"}," +
        "\"protocol\":{\"id\":\"proto\",\"digest\":\"0000\"}," +
        "\"graph\":{\"digest\":\"1111\"},\"spec\":{\"digest\":\"2222\"}}," +
        "\"status\":\"draft\",\"review\":{\"state\":\"pending\"},\"history\":[]}"

    @Test
    fun renamesAndKeepsOtherFields() {
        val dir = Files.createTempDirectory("nf-rename").toFile()
        val f = java.io.File(dir, "p.nfproject.json").apply { writeText(doc) }
        val renamed = ProjectRenamer.rename(f, "  新标题  ")
        assertEquals("新标题", renamed.title)
        assertEquals("p", renamed.id)
        assertEquals(dev.ninfenz.mobile.model.ProjectStatus.DRAFT, renamed.status)
    }

    @Test
    fun rejectsBlankTitleAndLeavesFile() {
        val dir = Files.createTempDirectory("nf-rename-2").toFile()
        val f = java.io.File(dir, "p.nfproject.json").apply { writeText(doc) }
        assertTrue(runCatching { ProjectRenamer.rename(f, "   ") }.isFailure)
        assertTrue(f.readText().contains("旧标题"))
    }
}
