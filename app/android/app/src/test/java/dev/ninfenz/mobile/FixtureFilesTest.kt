package dev.ninfenz.mobile

import dev.ninfenz.mobile.model.AssemblyPlan
import dev.ninfenz.mobile.model.CcosModel
import dev.ninfenz.mobile.model.GraphModel
import dev.ninfenz.mobile.model.ImportModel
import dev.ninfenz.mobile.model.PackUpdateModel
import dev.ninfenz.mobile.model.PlanModel
import dev.ninfenz.mobile.model.ProjectModel
import dev.ninfenz.mobile.model.ProtocolModel
import dev.ninfenz.mobile.model.ReportModel
import dev.ninfenz.mobile.model.SpecModel
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Assume.assumeTrue
import org.junit.Test
import java.io.File

/**
 * 契约夹具对齐测试：读 app/fixtures/schema/valid/<name>/minimal.json（A0 单一真源的样例）。
 * 夹具目录不存在时 skip（例如在 CI 的另一布局里运行），绝不伪造通过。
 */
class FixtureFilesTest {

    private fun fixturesDir(): File {
        val candidates = listOf(
            File("../../fixtures/schema/valid"),
            File("../fixtures/schema/valid"),
            File("app/fixtures/schema/valid")
        )
        return candidates.firstOrNull { it.isDirectory } ?: File("../../fixtures/schema/valid")
    }

    private fun text(name: String): String {
        val file = File(File(fixturesDir(), name), "minimal.json")
        assumeTrue("夹具缺失，跳过：" + file.absolutePath, file.isFile)
        return file.readText(Charsets.UTF_8)
    }

    @Test
    fun parsesContractFixtures() {
        val dir = fixturesDir()
        assumeTrue("夹具目录缺失，跳过：" + dir.absolutePath, dir.isDirectory)

        val importDoc = ImportModel.parse(text("nf-import"))
        assertEquals("markdown", importDoc.format)
        assertTrue(importDoc.confidence in 0..100)
        assertTrue(importDoc.mappings.isNotEmpty())

        val graph = GraphModel.parse(text("nf-pipeline-graph"))
        assertEquals(2, graph.nodes.size)
        assertEquals("N01", graph.nodes.first().id)

        val protocol = ProtocolModel.parse(text("nf-protocol-pack"))
        assertEquals(1, protocol.clauses.size)
        assertEquals(1, protocol.fields.size)

        val spec = SpecModel.parse(text("nf-md-spec"))
        assertEquals(1, spec.sections.size)
        assertEquals(1, spec.slots.size)

        val report = ReportModel.parse(text("nf-validate-report"))
        assertEquals("warn", report.verdict)

        val update = PackUpdateModel.parse(text("nf-pack-update"))
        assertEquals(1, update.conflicts.size)

        val task = CcosModel.parseTask(text("ccos-task"))
        assertEquals("demo-pack", task.packId)

        val result = CcosModel.parseResult(text("ccos-result"))
        assertEquals("pending", result.reviewState)

        val project = ProjectModel.parse(text("nf-project"))
        assertEquals("demo-project", project.id)

        val plan: AssemblyPlan = PlanModel.parse(text("nf-assembly-plan"))
        assertEquals(1, plan.steps.size)
        assertEquals("SLT-01", plan.slots.first())
    }
}
