package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class ProjectArchiverTest {
    @Test
    fun movesProjectOutOfProjectsIntoArchive() {
        val root = Files.createTempDirectory("nf-archive").toFile()
        val projects = java.io.File(root, "projects").apply { mkdirs() }
        val f = java.io.File(projects, "p.nfproject.json").apply { writeText("{}") }
        val archived = ProjectArchiver.archive(f, root, 123L)
        assertFalse(f.exists())
        assertTrue(archived.isFile)
        assertTrue(archived.name.contains("123"))
        assertTrue(archived.readText() == "{}")
    }

    @Test
    fun rejectsFileOutsideProjects() {
        val root = Files.createTempDirectory("nf-archive-2").toFile()
        val f = java.io.File(root, "outside.nfproject.json").apply { writeText("{}") }
        val failed = runCatching { ProjectArchiver.archive(f, root) }.isFailure
        assertTrue(failed)
        assertTrue(f.exists())
    }
}
