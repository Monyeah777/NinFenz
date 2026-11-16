package dev.ninfenz.mobile.model

import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ProjectDiffTest {
    private fun project(status: String, history: String = ""): Project = ProjectModel.parse(
        "{\"schema\":\"nf-project/1\",\"id\":\"p\",\"title\":\"p\",\"refs\":{" +
            "\"base_pack\":{\"id\":\"pack\",\"version\":\"1.0.0\"}," +
            "\"protocol\":{\"id\":\"proto\",\"digest\":\"0000\"}," +
            "\"graph\":{\"digest\":\"1111\"},\"spec\":{\"digest\":\"2222\"}}," +
            "\"status\":\"" + status + "\",\"review\":{\"state\":\"pending\"},\"history\":[" + history + "]}"
    )

    @Test
    fun reportsStatusAndHistoryDiff() {
        val a = project("draft", "{\"op\":\"create\"}")
        val b = project("authoring", "{\"op\":\"create\"},{\"op\":\"edit\"}")
        val report = ProjectDiff.compare(a, b)
        assertTrue(report.hasChanges)
        assertTrue(report.changes.any { it.field == "status" && it.before == "draft" && it.after == "authoring" })
        assertEquals(listOf("edit"), report.historyOnlyAfter)
        assertEquals(emptyList<String>(), report.historyOnlyBefore)
    }

    @Test
    fun identicalProjectsHaveNoChanges() {
        val a = project("draft")
        assertFalse(ProjectDiff.compare(a, a).hasChanges)
    }
}
