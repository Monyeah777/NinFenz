package dev.ninfenz.mobile.model

import dev.ninfenz.mobile.data.ProjectEntry
import java.io.File
import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Test

class ProjectSorterTest {
    private fun entry(id: String, title: String, status: ProjectStatus, modified: Long): ProjectEntry {
        val dir = Files.createTempDirectory("nf-sort").toFile()
        val f = File(dir, id + ".nfproject.json").apply { writeText("{}") }
        f.setLastModified(modified)
        val project = ProjectModel.parse(
            "{\"schema\":\"nf-project/1\",\"id\":\"" + id + "\",\"title\":\"" + title + "\",\"refs\":{" +
                "\"base_pack\":{\"id\":\"pack\",\"version\":\"1.0.0\"}," +
                "\"protocol\":{\"id\":\"proto\",\"digest\":\"0000\"}," +
                "\"graph\":{\"digest\":\"1111\"},\"spec\":{\"digest\":\"2222\"}}," +
                "\"status\":\"" + status.wire + "\",\"review\":{\"state\":\"pending\"},\"history\":[]}"
        )
        return ProjectEntry(project, f)
    }

    @Test
    fun sortsByRecentTitleAndStatus() {
        val a = entry("a", "Bravo", ProjectStatus.EXPORTED, 1000L)
        val b = entry("b", "alpha", ProjectStatus.DRAFT, 2000L)
        val list = listOf(a, b)
        assertEquals(listOf("b", "a"), ProjectSorter.sort(list, ProjectSort.RECENT).map { it.project.id })
        assertEquals(listOf("b", "a"), ProjectSorter.sort(list, ProjectSort.TITLE).map { it.project.id })
        assertEquals(listOf("b", "a"), ProjectSorter.sort(list, ProjectSort.STATUS).map { it.project.id })
    }
}
