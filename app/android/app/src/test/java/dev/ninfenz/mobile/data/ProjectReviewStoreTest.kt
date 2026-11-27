package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.FakeCoreBridge
import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.model.ProjectModel
import java.io.File
import java.nio.file.Files
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.Json
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.JsonPrimitive
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ProjectReviewStoreTest {
    private val hex = "0123456789abcdef".repeat(4)

    private fun setup(filesDir: File): dev.ninfenz.mobile.model.Project {
        val projects = File(filesDir, "projects").apply { mkdirs() }
        val doc = ProjectFactory.build(ProjectBuildSpec(
            id = "p", title = "p", packId = "demo-pack", packVersion = "1.0.0", packTree = hex,
            protocolId = "proto", protocolVersion = "1.0.0", protocolDigest = hex,
            graphId = "graph", graphVersion = "1.0.0", graphDigest = hex, graphSha256 = hex,
            specId = "spec", specVersion = "1.0.0", specDigest = hex, specSha256 = hex
        )).toMutableMap()
        doc["status"] = JsonPrimitive("validated")
        File(projects, "p.nfproject.json").writeText(kotlinx.serialization.json.JsonObject(doc).toString(), Charsets.UTF_8)
        return ProjectModel.parse(File(projects, "p.nfproject.json").readText())
    }

    @Test
    fun approvingWritesReviewAndReviewedStatus() = runBlocking {
        val filesDir = Files.createTempDirectory("nf-review").toFile()
        val project = setup(filesDir)
        val bridge = FakeCoreBridge()
            .enqueue(CoreResponse.ok(buildJsonObject { put("digest", hex) }))
            .enqueue(CoreResponse.ok(buildJsonObject { put("verdict", "pass") }))
        val result = ProjectReviewStore(filesDir, bridge).review(project, true, "reviewer-a", "通过")
        assertTrue(result is ReviewResult.Reviewed)
        val raw = Json.parseToJsonElement(File(filesDir, "projects/p.nfproject.json").readText()).jsonObject
        assertEquals("reviewed", raw["status"]?.jsonPrimitive?.content)
        val review = raw["review"]!!.jsonObject
        assertEquals("approved", review["state"]?.jsonPrimitive?.content)
        assertEquals("reviewer-a", review["reviewer"]?.jsonPrimitive?.content)
        assertTrue(raw["history"].toString().contains("review:approved"))
    }

    @Test
    fun detectsStaleReviewDigest() = runBlocking {
        val filesDir = Files.createTempDirectory("nf-review-stale").toFile()
        setup(filesDir)
        val file = File(filesDir, "projects/p.nfproject.json")
        val raw = Json.parseToJsonElement(file.readText()).jsonObject.toMutableMap()
        raw["status"] = JsonPrimitive("reviewed")
        raw["review"] = buildJsonObject {
            put("state", "approved")
            put("reviewer", "r")
            put("note", "ok")
            put("subject_digest", "old")
        }
        file.writeText(JsonObject(raw).toString())
        val bridge = FakeCoreBridge().enqueue(CoreResponse.ok(buildJsonObject { put("digest", "new") }))
        assertTrue(ProjectReviewStore(filesDir, bridge).isStale(file))
        val same = FakeCoreBridge().enqueue(CoreResponse.ok(buildJsonObject { put("digest", "old") }))
        assertFalse(ProjectReviewStore(filesDir, same).isStale(file))
    }

    @Test
    fun rejectingKeepsStatusAndRequiresFields() = runBlocking {
        val filesDir = Files.createTempDirectory("nf-review-2").toFile()
        val project = setup(filesDir)
        val bridge = FakeCoreBridge()
            .enqueue(CoreResponse.ok(buildJsonObject { put("digest", hex) }))
            .enqueue(CoreResponse.ok(buildJsonObject { put("verdict", "pass") }))
        val result = ProjectReviewStore(filesDir, bridge).review(project, false, "reviewer-a", "需补充")
        assertTrue(result is ReviewResult.Reviewed)
        val raw = Json.parseToJsonElement(File(filesDir, "projects/p.nfproject.json").readText()).jsonObject
        assertEquals("validated", raw["status"]?.jsonPrimitive?.content)
        assertEquals("rejected", raw["review"]!!.jsonObject["state"]?.jsonPrimitive?.content)
        val blank = ProjectReviewStore(filesDir, FakeCoreBridge()).review(project, true, "", "")
        assertTrue(blank is ReviewResult.Failure)
    }
}
