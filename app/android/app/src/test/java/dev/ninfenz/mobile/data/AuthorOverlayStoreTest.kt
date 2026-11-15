package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.FakeCoreBridge
import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.model.ProjectModel
import java.nio.file.Files
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AuthorOverlayStoreTest {

    private val hex = "0123456789abcdef".repeat(4)

    private fun setup(filesDir: java.io.File): Pair<PackEntry, dev.ninfenz.mobile.model.Project> {
        val projects = java.io.File(filesDir, "projects").apply { mkdirs() }
        val doc = ProjectFactory.build(
            id = "p", title = "p", packId = "demo-pack", packVersion = "1.0.0", packTree = hex,
            protocolId = "proto", protocolVersion = "1.0.0", protocolDigest = hex,
            graphId = "graph", graphVersion = "1.0.0", graphDigest = hex, graphSha256 = hex,
            specId = "spec", specVersion = "1.0.0", specDigest = hex, specSha256 = hex
        )
        java.io.File(projects, "p.nfproject.json").writeText(doc.toString(), Charsets.UTF_8)
        val project = ProjectModel.parse(doc.toString())
        val pack = PackEntry("demo-pack", "1.0.0", "示例", "d", 1, hex, java.io.File(filesDir, "pack"))
        return pack to project
    }

    @Test
    fun buildsOverlayShape() {
        val pack = PackEntry("demo-pack", "1.0.0", "示例", "d", 1, hex, java.io.File("x"))
        val overlay = AuthorOverlayFactory.build(pack, mapOf("C-001" to false), mapOf("F-001" to "值"))
        assertEquals("nf-overlay/1", overlay["schema"]?.jsonPrimitive?.content)
        assertEquals("demo-pack", overlay["base"]!!.jsonObject["id"]?.jsonPrimitive?.content)
        assertEquals("false", overlay["clauses"]!!.jsonObject["C-001"]!!.jsonObject["enabled"].toString())
        assertEquals("值", overlay["params"]!!.jsonObject["F-001"]?.jsonPrimitive?.content)
        assertEquals("[]", overlay["presets"].toString())
    }

    @Test
    fun savesOverlayAndUpdatesProjectStatus() = runBlocking {
        val filesDir = Files.createTempDirectory("nf-author-overlay").toFile()
        val (pack, project) = setup(filesDir)
        val bridge = FakeCoreBridge().enqueue(CoreResponse.ok(buildJsonObject { put("verdict", "pass") }))
        val result = AuthorOverlayStore(filesDir, bridge).save(project, pack, mapOf("C-001" to true), mapOf("F-001" to "x"))
        assertTrue(result is SaveOverlayResult.Saved)
        val saved = result as SaveOverlayResult.Saved
        assertEquals(dev.ninfenz.mobile.model.ProjectStatus.AUTHORING, saved.status)

        val overlayFile = java.io.File(filesDir, "projects/p/overlay/nf-overlay.json")
        assertTrue(overlayFile.isFile)
        val raw = kotlinx.serialization.json.Json.parseToJsonElement(
            java.io.File(filesDir, "projects/p.nfproject.json").readText(Charsets.UTF_8)
        ).jsonObject
        assertEquals("overlay/nf-overlay.json", raw["refs"]!!.jsonObject["overlay"]!!.jsonObject["path"]?.jsonPrimitive?.content)
        assertEquals(saved.overlaySha256, raw["refs"]!!.jsonObject["overlay"]!!.jsonObject["sha256"]?.jsonPrimitive?.content)
        assertEquals("authoring", raw["status"]?.jsonPrimitive?.content)
        assertEquals(1, raw["history"]!!.let { it.toString().split("\"op\"").size - 1 })
    }
}
