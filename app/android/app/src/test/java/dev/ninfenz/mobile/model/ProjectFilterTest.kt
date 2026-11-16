package dev.ninfenz.mobile.model

import dev.ninfenz.mobile.data.ProjectEntry
import dev.ninfenz.mobile.data.ProjectFactory
import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Test

class ProjectFilterTest {
    private val hex = "0123456789abcdef".repeat(4)

    private fun entry(id: String, status: ProjectStatus): ProjectEntry {
        val doc = ProjectFactory.build(
            id = id, title = id, packId = "demo-pack", packVersion = "1.0.0", packTree = hex,
            protocolId = "proto", protocolVersion = "1.0.0", protocolDigest = hex,
            graphId = "graph", graphVersion = "1.0.0", graphDigest = hex, graphSha256 = hex,
            specId = "spec", specVersion = "1.0.0", specDigest = hex, specSha256 = hex
        ).toString().replace("\"status\":\"draft\"", "\"status\":\"" + status.wire + "\"")
        return ProjectEntry(ProjectModel.parse(doc), File(id + ".nfproject.json"))
    }

    @Test
    fun nullKeepsAll() {
        val all = listOf(entry("a", ProjectStatus.DRAFT), entry("b", ProjectStatus.EXPORTED))
        assertEquals(2, ProjectFilter.apply(all, null).size)
    }

    @Test
    fun filtersByStatus() {
        val all = listOf(entry("a", ProjectStatus.DRAFT), entry("b", ProjectStatus.EXPORTED))
        assertEquals(listOf("a"), ProjectFilter.apply(all, ProjectStatus.DRAFT).map { it.project.id })
        assertEquals(listOf("b"), ProjectFilter.apply(all, ProjectStatus.EXPORTED).map { it.project.id })
    }
}
