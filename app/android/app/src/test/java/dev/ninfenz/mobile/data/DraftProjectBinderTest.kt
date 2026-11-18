package dev.ninfenz.mobile.data

import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

class DraftProjectBinderTest {
    @Test
    fun writesSpecOverrideNextToProject() {
        val filesDir = Files.createTempDirectory("nf-bind-spec").toFile()
        val projects = java.io.File(filesDir, "projects").apply { mkdirs() }
        java.io.File(projects, "p.nfproject.json").writeText("{}")
        val target = DraftProjectBinder.bindSpec(filesDir, "p", "{\"schema\":\"nf-md-spec/1\"}")
        assertTrue(target.isFile)
        assertEquals("{\"schema\":\"nf-md-spec/1\"}", target.readText())
    }

    @Test(expected = IllegalArgumentException::class)
    fun rejectsMissingProject() {
        val filesDir = Files.createTempDirectory("nf-bind-missing").toFile()
        DraftProjectBinder.bindSpec(filesDir, "absent", "{}")
    }
}
