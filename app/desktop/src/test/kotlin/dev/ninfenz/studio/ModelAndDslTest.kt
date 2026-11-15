package dev.ninfenz.studio

import dev.ninfenz.studio.core.J
import dev.ninfenz.studio.model.CcosModel
import dev.ninfenz.studio.model.Dsl
import dev.ninfenz.studio.model.GraphModel
import dev.ninfenz.studio.model.ProjectModel
import dev.ninfenz.studio.model.ProjectStatus
import dev.ninfenz.studio.model.ReportModel
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertThrows
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File

class ModelAndDslTest {

    private val sampleDsl = """
        # 示例
        graph demo-pipeline 1.0.0
        mode pro
        node N01 stage "阶段"
        node N02 module "模块" module=mod-outline
        edge E01 N01:out -> N02:in
        weight N01 30
        weight N02 40
        required N01
    """.trimIndent()

    @Test
    fun parsesDslIntoGraph() {
        val result = Dsl.parse(sampleDsl)
        assertTrue(result.issues.toString(), result.ok)
        assertEquals("demo-pipeline", result.graph.id)
        assertEquals("1.0.0", result.graph.version)
        assertEquals(2, result.graph.nodes.size)
        assertEquals(1, result.graph.edges.size)
        assertEquals(30, result.graph.weights["N01"])
        assertEquals(listOf("N01"), result.graph.requiredStages)
    }

    @Test
    fun emitAndReparseRoundTrip() {
        val first = Dsl.parse(sampleDsl)
        val text = Dsl.emit(first.graph)
        val second = Dsl.parse(text)
        assertEquals(first.graph.nodes.size, second.graph.nodes.size)
        assertEquals(first.graph.edges.size, second.graph.edges.size)
        assertEquals(first.graph.weights, second.graph.weights)
        assertTrue(second.issues.toString(), second.ok)
    }

    @Test
    fun reportsDslErrorsWithLines() {
        val bad = "node N01 stage\n" +
            "bogus directive\n" +
            "edge E01 N01:out -> N99:in\n" +
            "weight N01 300\n"
        val result = Dsl.parse(bad)
        assertFalse(result.ok)
        assertTrue(result.issues.any { it.message.contains("标题") })
        assertTrue(result.issues.any { it.message.contains("未知指令") })
        assertTrue(result.issues.any { it.message.contains("未声明节点") })
        assertTrue(result.issues.any { it.message.contains("权重越界") })
    }

    @Test
    fun graphIssuesFindDanglingEdge() {
        val graph = Dsl.parse(sampleDsl).graph
        val broken = graph.copy(edges = graph.edges + dev.ninfenz.studio.model.GraphEdge("E02", "N01", "N99", "out", "in", "data"))
        assertTrue(GraphModel.issues(broken).any { it.code == "NF-GRF-003" })
    }

    @Test
    fun parsesContractFixturesFromRepo() {
        val dir = fixtureDir()
        assumeTrue("夹具目录缺失，跳过", dir.isDirectory)
        val project = ProjectModel.parse(File(dir, "nf-project/minimal.json").readText(Charsets.UTF_8))
        assertEquals("demo-project", project.id)
        assertEquals(ProjectStatus.VALIDATED, project.status)

        val report = ReportModel.parse(File(dir, "nf-validate-report/minimal.json").readText(Charsets.UTF_8))
        assertEquals("warn", report.verdict)
        assertTrue(report.issues.isNotEmpty())

        val result = CcosModel.parseResult(File(dir, "ccos-result/minimal.json").readText(Charsets.UTF_8))
        assertEquals("pending", result.reviewState)
        assertTrue(result.reviewRequired)
    }

    @Test
    fun rejectsUnknownSchemaAndBadJson() {
        val ex = assertThrows(dev.ninfenz.studio.core.ModelException::class.java) {
            ProjectModel.parse("{\"schema\":\"nf-project/9\"}")
        }
        assertEquals("NF-E-001", ex.code)
        val ex2 = assertThrows(dev.ninfenz.studio.core.ModelException::class.java) {
            J.parseObject("not-json", "项目")
        }
        assertEquals("NF-E-002", ex2.code)
    }

    private fun fixtureDir(): File {
        val candidates = listOf(
            File("../fixtures/schema/valid"),
            File("../../app/fixtures/schema/valid"),
            File("app/fixtures/schema/valid")
        )
        return candidates.firstOrNull { it.isDirectory } ?: File("../fixtures/schema/valid")
    }
}
