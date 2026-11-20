package dev.ninfenz.mobile.data

import java.nio.file.Files
import java.util.zip.ZipEntry
import java.util.zip.ZipOutputStream
import java.util.zip.ZipFile
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class ProjectBundleImporterTest {
    @Test(expected = IllegalArgumentException::class)
    fun rejectsTamperedEntry() {
        val root = Files.createTempDirectory("nf-bundle-bad").toFile()
        val bundle = java.io.File(root, "bad.zip")
        ZipOutputStream(bundle.outputStream()).use { out ->
            out.putNextEntry(ZipEntry("nf-bundle.json"))
            out.write(("{\"schema\":\"nf-bundle/1\",\"projects\":[{\"path\":\"p.zip\",\"sha256\":\"00\"}]}").toByteArray())
            out.closeEntry()
            out.putNextEntry(ZipEntry("p.zip"))
            out.write(byteArrayOf(1, 2, 3))
            out.closeEntry()
        }
        ProjectBundleImporter.import(root, bundle)
    }

    @Test
    fun importsAllProjects() {
        val source = Files.createTempDirectory("nf-bundle-source").toFile()
        val projects = java.io.File(source, "projects").apply { mkdirs() }
        java.io.File(projects, "p1.nfproject.json").writeText("{\"schema\":\"nf-project/1\",\"id\":\"p1\",\"title\":\"P1\",\"refs\":{\"base_pack\":{\"id\":\"pack\",\"version\":\"1.0.0\"},\"protocol\":{\"id\":\"proto\",\"digest\":\"0\"},\"graph\":{\"digest\":\"1\"},\"spec\":{\"digest\":\"2\"}},\"status\":\"draft\",\"review\":{\"state\":\"pending\"},\"history\":[]}")
        java.io.File(projects, "p2.nfproject.json").writeText("{\"schema\":\"nf-project/1\",\"id\":\"p2\",\"title\":\"P2\",\"refs\":{\"base_pack\":{\"id\":\"pack\",\"version\":\"1.0.0\"},\"protocol\":{\"id\":\"proto\",\"digest\":\"0\"},\"graph\":{\"digest\":\"1\"},\"spec\":{\"digest\":\"2\"}},\"status\":\"draft\",\"review\":{\"state\":\"pending\"},\"history\":[]}")
        val bundle = ProjectBundleExporter.create(source, java.io.File(source, "out")).file
        val target = Files.createTempDirectory("nf-bundle-target").toFile()
        val imported = ProjectBundleImporter.import(target, bundle)
        assertEquals(2, imported.count)
        assertTrue(java.io.File(target, "projects/p1.nfproject.json").isFile)
        assertTrue(java.io.File(target, "projects/p2.nfproject.json").isFile)
        ZipFile(bundle).use { assertTrue(it.getEntry("nf-bundle.json") != null) }
    }
}
