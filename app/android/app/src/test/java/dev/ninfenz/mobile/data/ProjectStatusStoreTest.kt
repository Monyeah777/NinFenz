package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.FakeCoreBridge
import dev.ninfenz.mobile.core.CoreResponse
import dev.ninfenz.mobile.model.ProjectModel
import dev.ninfenz.mobile.model.ProjectStatus
import java.io.File
import java.nio.file.Files
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ProjectStatusStoreTest {

    private val hex = "0123456789abcdef".repeat(4)

    private fun setup(filesDir: File): dev.ninfenz.mobile.model.Project {
        val projects = File(filesDir, "projects").apply { mkdirs() }
        val doc = ProjectFactory.build(
            id = "p", title = "p", packId = "demo-pack", packVersion = "1.0.0", packTree = hex,
            protocolId = "proto", protocolVersion = "1.0.0", protocolDigest = hex,
            graphId = "graph", graphVersion = "1.0.0", graphDigest = hex, graphSha256 = hex,
            specId = "spec", specVersion = "1.0.0", specDigest = hex, specSha256 = hex
        )
        File(projects, "p.nfproject.json").writeText(doc.toString(), Charsets.UTF_8)
        return ProjectModel.parse(doc.toString())
    }

    @Test
    fun advancesStepwiseAndAppendsHistory() = runBlocking {
        val filesDir = Files.createTempDirectory("nf-status-store").toFile()
        val project = setup(filesDir)
        val bridge = FakeCoreBridge().enqueue(CoreResponse.ok(buildJsonObject { put("verdict", "pass") }))
        val result = ProjectStatusStore(filesDir, bridge).advance(project, ProjectStatus.VALIDATED)
        assertTrue(result is StatusAdvanceResult.Advanced)
        val advanced = result as StatusAdvanceResult.Advanced
        assertEquals(ProjectStatus.VALIDATED, advanced.to)

        val raw = kotlinx.serialization.json.Json.parseToJsonElement(
            File(filesDir, "projects/p.nfproject.json").readText(Charsets.UTF_8)
        ).jsonObject
        assertEquals("validated", raw["status"]?.jsonPrimitive?.content)
        val ops = Regex("\"op\":\"(status:[^\"]+)\"").findAll(raw["history"].toString()).map { it.groupValues[1] }.toList()
        assertEquals(listOf("status:draft->authoring", "status:authoring->assembled", "status:assembled->validated"), ops)
    }

    @Test
    fun coreFailureLeavesProjectUntouched() = runBlocking {
        val filesDir = Files.createTempDirectory("nf-status-fail").toFile()
        val project = setup(filesDir)
        val before = File(filesDir, "projects/p.nfproject.json").readText(Charsets.UTF_8)
        val bridge = FakeCoreBridge() // 无响应 -> NF-E-005
        val result = ProjectStatusStore(filesDir, bridge).advance(project, ProjectStatus.ASSEMBLED)
        assertTrue(result is StatusAdvanceResult.Failure)
        assertEquals(before, File(filesDir, "projects/p.nfproject.json").readText(Charsets.UTF_8))
    }
}
