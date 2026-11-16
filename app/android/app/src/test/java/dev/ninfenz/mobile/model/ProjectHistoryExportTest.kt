package dev.ninfenz.mobile.model

import org.junit.Assert.assertTrue
import org.junit.Test

class ProjectHistoryExportTest {
    private fun project(history: String): Project = ProjectModel.parse(
        "{\"schema\":\"nf-project/1\",\"id\":\"p\",\"title\":\"演示 | 项目\",\"refs\":{" +
            "\"base_pack\":{\"id\":\"pack\",\"version\":\"1.0.0\"}," +
            "\"protocol\":{\"id\":\"proto\",\"digest\":\"0000\"}," +
            "\"graph\":{\"digest\":\"1111\"},\"spec\":{\"digest\":\"2222\"}}," +
            "\"status\":\"draft\",\"review\":{\"state\":\"pending\"},\"history\":[" + history + "]}"
    )

    @Test
    fun exportsTableAndEscapesTitle() {
        val md = ProjectHistoryExport.toMarkdown(
            project("{\"op\":\"status:draft->authoring\",\"digest\":\"abc\",\"at\":\"2026-11-15T00:00:00Z\"}")
        )
        assertTrue(md.contains("# 项目历史"))
        assertTrue(md.contains("\\|"))
        assertTrue(md.contains("status:draft->authoring"))
        assertTrue(md.contains("abc"))
    }

    @Test
    fun emptyHistoryStillExports() {
        val md = ProjectHistoryExport.toMarkdown(project(""))
        assertTrue(md.contains("（无历史记录）"))
    }
}
