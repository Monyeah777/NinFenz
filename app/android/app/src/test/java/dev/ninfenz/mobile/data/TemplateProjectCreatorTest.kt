package dev.ninfenz.mobile.data

import java.io.File
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class TemplateProjectCreatorTest {
    @get:Rule
    val tmp = TemporaryFolder()

    @Test
    fun installsSpecOverrideNextToProject() {
        val candidate = File(tmp.root, "candidate.json")
        candidate.writeText("{\"schema\":\"nf-md-spec/1\"}", Charsets.UTF_8)
        TemplateProjectCreator.installOverride(tmp.root, "p1", candidate)
        val target = TemplateProjectCreator.overrideFile(tmp.root, "p1")
        assertTrue(target.isFile)
        assertEquals(candidate.readText(Charsets.UTF_8), target.readText(Charsets.UTF_8))
    }

    @Test
    fun missingCandidateFailsWithoutCreatingProject() = runBlocking {
        val pack = PackEntry("demo", "1.0.0", "Demo", "", 0, "tree", tmp.root)
        val result = TemplateProjectCreator(tmp.root).create(pack, "Title", File(tmp.root, "missing.json"))
        assertTrue(result is CreateProjectResult.Failure)
        assertTrue((result as CreateProjectResult.Failure).code == "NF-PRJ-001")
    }
}
