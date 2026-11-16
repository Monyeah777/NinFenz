package dev.ninfenz.mobile.data

import java.nio.file.Files
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.jsonObject
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ProjectDuplicatorTest {
    private fun writeSource(root: java.io.File): java.io.File {
        val projects = java.io.File(root, "projects").apply { mkdirs() }
        val f = java.io.File(projects, "p.nfproject.json")
        f.writeText(
            "{\"schema\":\"nf-project/1\",\"id\":\"p\",\"title\":\"演示\",\"refs\":{" +
                "\"base_pack\":{\"id\":\"pack\",\"version\":\"1.0.0\"}," +
                "\"protocol\":{\"id\":\"proto\",\"digest\":\"0000\"}," +
                "\"graph\":{\"digest\":\"1111\"},\"spec\":{\"digest\":\"2222\"}}," +
                "\"status\":\"exported\",\"review\":{\"state\":\"approved\"}," +
                "\"history\":[{\"op\":\"export\",\"digest\":\"abc\"}]}",
            Charsets.UTF_8
        )
        return f
    }

    @Test
    fun copiesRefsAndResetsStateReviewHistory() {
        val root = Files.createTempDirectory("nf-dup").toFile()
        val source = writeSource(root)
        val target = ProjectDuplicator.duplicate(source, root)
        assertTrue(target.name.startsWith("p-copy"))
        val obj = Json.parseToJsonElement(target.readText()).jsonObject
        assertEquals("draft", obj["status"].toString().trim('"'))
        assertEquals("pending", obj["review"].toString().let { Regex("\"state\":\"([^\"]+)\"").find(it)?.groupValues?.get(1) })
        assertEquals("[]", obj["history"].toString())
        assertTrue(obj["refs"].toString().contains("pack"))
    }

    @Test
    fun avoidsIdCollision() {
        val root = Files.createTempDirectory("nf-dup-2").toFile()
        val source = writeSource(root)
        ProjectDuplicator.duplicate(source, root)
        val second = ProjectDuplicator.duplicate(source, root)
        assertTrue(second.name.contains("copy-2"))
    }
}
