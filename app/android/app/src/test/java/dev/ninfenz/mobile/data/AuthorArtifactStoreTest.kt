package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.FakeCoreBridge
import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.model.GraphNode
import dev.ninfenz.mobile.model.MdSpec
import dev.ninfenz.mobile.model.PipelineGraph
import dev.ninfenz.mobile.model.ProjectModel
import dev.ninfenz.mobile.model.SpecSection
import dev.ninfenz.mobile.model.SpecSlot
import java.io.File
import java.nio.file.Files
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.JsonObject
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class AuthorArtifactStoreTest {

    private val hex = "0123456789abcdef".repeat(4)

    private fun setup(filesDir: File): dev.ninfenz.mobile.model.Project {
        val projects = File(filesDir, "projects").apply { mkdirs() }
        val doc = ProjectFactory.build(ProjectBuildSpec(
            id = "p", title = "p", packId = "demo-pack", packVersion = "1.0.0", packTree = hex,
            protocolId = "proto", protocolVersion = "1.0.0", protocolDigest = hex,
            graphId = "graph", graphVersion = "1.0.0", graphDigest = hex, graphSha256 = hex,
            specId = "spec", specVersion = "1.0.0", specDigest = hex, specSha256 = hex
        ))
        File(projects, "p.nfproject.json").writeText(doc.toString(), Charsets.UTF_8)
        return ProjectModel.parse(doc.toString())
    }

    private fun graph() = PipelineGraph(
        id = "graph", version = "1.0.0", title = "G", mode = "simple",
        nodes = listOf(GraphNode("N01", "stage", "S", emptyList(), listOf("out"), null, null, null)),
        edges = emptyList(), weights = emptyMap(), requiredStages = emptyList(), seed = null,
        params = JsonObject(emptyMap())
    )

    private fun spec() = MdSpec(
        id = "spec", title = "S", version = "1.0.0", headingLevel = 2,
        sections = listOf(SpecSection("S1", "T", 1, true, listOf("F1"))),
        slots = listOf(SpecSlot("F1", "f", "S1", "text", true))
    )

    @Test
    fun savesGraphAndUpdatesRefs() = runBlocking {
        val filesDir = Files.createTempDirectory("nf-author-graph").toFile()
        val project = setup(filesDir)
        val bridge = FakeCoreBridge()
            .enqueue(CoreResponse.ok(buildJsonObject { put("digest", hex) }))
            .enqueue(CoreResponse.ok(buildJsonObject { put("verdict", "pass") }))
        val result = AuthorArtifactStore(filesDir, bridge).saveGraph(project, graph())
        assertTrue(result is SaveArtifactResult.Saved)
        val saved = result as SaveArtifactResult.Saved
        assertEquals("authoring/graph.json", saved.path)
        assertTrue(File(filesDir, "projects/p/authoring/graph.json").isFile)
        val raw = kotlinx.serialization.json.Json.parseToJsonElement(
            File(filesDir, "projects/p.nfproject.json").readText(Charsets.UTF_8)
        ).jsonObject
        assertEquals("authoring/graph.json", raw["refs"]!!.jsonObject["graph"]!!.jsonObject["path"]?.jsonPrimitive?.content)
        assertEquals(saved.sha256, raw["refs"]!!.jsonObject["graph"]!!.jsonObject["sha256"]?.jsonPrimitive?.content)
        assertEquals("authoring", raw["status"]?.jsonPrimitive?.content)
    }

    @Test
    fun savesSpecAndUpdatesRefs() = runBlocking {
        val filesDir = Files.createTempDirectory("nf-author-spec").toFile()
        val project = setup(filesDir)
        val bridge = FakeCoreBridge()
            .enqueue(CoreResponse.ok(buildJsonObject { put("digest", hex) }))
            .enqueue(CoreResponse.ok(buildJsonObject { put("verdict", "pass") }))
        val result = AuthorArtifactStore(filesDir, bridge).saveSpec(project, spec())
        assertTrue(result is SaveArtifactResult.Saved)
        assertTrue(File(filesDir, "projects/p/authoring/spec.json").isFile)
    }
}
