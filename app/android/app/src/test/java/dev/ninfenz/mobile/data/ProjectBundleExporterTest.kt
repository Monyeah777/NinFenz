package dev.ninfenz.mobile.data

import java.nio.file.Files
import java.util.zip.ZipFile
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ProjectBundleExporterTest {
    @Test
    fun bundlesAllProjectPackages() {
        val root = Files.createTempDirectory("nf-bundle-src").toFile()
        val projects = java.io.File(root, "projects").apply { mkdirs() }
        java.io.File(projects, "p1.nfproject.json").writeText("{\"id\":\"p1\"}")
        java.io.File(projects, "p2.nfproject.json").writeText("{\"id\":\"p2\"}")
        val out = java.io.File(root, "out")
        val created = ProjectBundleExporter.create(root, out)
        assertEquals(2, created.count)
        ZipFile(created.file).use { zip ->
            assertTrue(zip.getEntry("nf-bundle.json") != null)
            assertTrue(zip.entries().asSequence().any { it.name.startsWith("projects/nf-project-p1") })
            assertTrue(zip.entries().asSequence().any { it.name.startsWith("projects/nf-project-p2") })
        }
    }
}
