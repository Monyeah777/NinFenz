package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.model.ProjectModel
import dev.ninfenz.mobile.model.ProjectStatus
import kotlinx.serialization.json.jsonObject
import kotlinx.serialization.json.jsonPrimitive
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ProjectFactoryTest {

    private val hex = "0123456789abcdef".repeat(4)

    private fun build() = ProjectFactory.build(ProjectBuildSpec(
        id = "my-project",
        title = "我的项目",
        packId = "demo-pack",
        packVersion = "1.0.0",
        packTree = hex,
        protocolId = "demo-protocol",
        protocolVersion = "1.0.0",
        protocolDigest = hex,
        graphId = "demo-pipeline",
        graphVersion = "1.0.0",
        graphDigest = hex,
        graphSha256 = hex,
        specId = "demo-spec",
        specVersion = "1.0.0",
        specDigest = hex,
        specSha256 = hex
    ))

    @Test
    fun buildsSchemaValidProjectDocument() {
        val document = build()
        assertEquals("nf-project/1", document["schema"]?.jsonPrimitive?.content)
        assertEquals("my-project", document["id"]?.jsonPrimitive?.content)
        assertEquals("我的项目", document["title"]?.jsonPrimitive?.content)
        assertEquals("draft", document["status"]?.jsonPrimitive?.content)

        val refs = document["refs"]!!.jsonObject
        assertEquals("demo-pack", refs["base_pack"]!!.jsonObject["id"]?.jsonPrimitive?.content)
        assertEquals("pack/pipeline/main.nfg.json", refs["graph"]!!.jsonObject["path"]?.jsonPrimitive?.content)
        assertEquals("pack/spec/main.nfspec.json", refs["spec"]!!.jsonObject["path"]?.jsonPrimitive?.content)
        assertEquals("none", document["review"]!!.jsonObject["state"]?.jsonPrimitive?.content)
        assertTrue(document["history"].toString() == "[]")

        // 必须能被 App 的 ProjectModel 解析（与核心 schema 同一形状）
        val parsed = ProjectModel.parse(document.toString())
        assertEquals("my-project", parsed.id)
        assertEquals(ProjectStatus.DRAFT, parsed.status)
        assertEquals("demo-pack", parsed.refs.basePackId)
        assertEquals(null, parsed.refs.assemblyDigest)
    }
}
