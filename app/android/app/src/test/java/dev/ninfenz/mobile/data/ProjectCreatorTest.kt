package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.FakeCoreBridge
import dev.ninfenz.mobile.core.CoreResponse
import java.nio.file.Files
import java.nio.file.Path
import kotlinx.coroutines.runBlocking
import kotlinx.serialization.json.buildJsonObject
import kotlinx.serialization.json.put
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ProjectCreatorTest {

    private val hex = "0123456789abcdef".repeat(4)

    private fun write(file: Path, text: String) {
        Files.createDirectories(file.parent)
        file.toFile().writeText(text, Charsets.UTF_8)
    }

    private fun setupPack(root: Path): PackEntry {
        write(root.resolve("nf-pack.json"), "{\"id\":\"demo-pack\",\"version\":\"1.0.0\"}")
        write(root.resolve("protocol/nf-protocol-pack.json"), "{\"id\":\"demo-protocol\",\"version\":\"1.0.0\"}")
        write(root.resolve("pipeline/main.nfg.json"), "{\"id\":\"demo-pipeline\",\"version\":\"1.0.0\"}")
        write(root.resolve("spec/main.nfspec.json"), "{\"id\":\"demo-spec\",\"version\":\"1.0.0\"}")
        return PackEntry("demo-pack", "1.0.0", "示例", "d", 3, hex, root.toFile())
    }

    private fun canonical(digest: String) =
        CoreResponse.ok(buildJsonObject { put("digest", digest) })

    @Test
    fun createsProjectThroughCoreCanonicalAndValidate() = runBlocking {
        val root = Files.createTempDirectory("nf-project-creator-test")
        val pack = setupPack(root.resolve("pack"))
        val bridge = FakeCoreBridge()
            .enqueue(canonical(hex))
            .enqueue(canonical(hex))
            .enqueue(canonical(hex))
            .enqueue(CoreResponse.ok(buildJsonObject { put("verdict", "pass") }))

        val result = ProjectCreator(root.toFile(), bridge).create(pack, "演示项目", "demo-project")
        assertTrue(result is CreateProjectResult.Success)
        val success = result as CreateProjectResult.Success
        assertEquals("demo-project", success.project.id)
        assertEquals("demo-pack", success.project.refs.basePackId)
        assertTrue(success.file.isFile)
        assertEquals(listOf("canonical", "canonical", "canonical", "project-validate"), bridge.calls.map { it.first })
    }

    @Test
    fun coreFailureDoesNotWriteHalfProject() = runBlocking {
        val root = Files.createTempDirectory("nf-project-creator-fail")
        val pack = setupPack(root.resolve("pack"))
        val bridge = FakeCoreBridge() // 无排队响应 -> NF-E-005
        val result = ProjectCreator(root.toFile(), bridge).create(pack, "项目", "p1")
        assertTrue(result is CreateProjectResult.Failure)
        assertEquals("NF-E-005", (result as CreateProjectResult.Failure).code)
        assertTrue(root.resolve("projects").toFile().listFiles().isNullOrEmpty())
    }
}
