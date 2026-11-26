package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.model.Project
import dev.ninfenz.mobile.model.ProjectRefs
import dev.ninfenz.mobile.model.ProjectReview
import dev.ninfenz.mobile.model.ProjectStatus
import java.io.File
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Rule
import org.junit.Test
import org.junit.rules.TemporaryFolder

class PackLockStoreTest {
    @get:Rule
    val tmp = TemporaryFolder()

    private val tree = "a".repeat(64)

    private fun project(treeValue: String = tree): Project = Project(
        id = "p1",
        title = "P",
        refs = ProjectRefs("pack", "1.0.0", treeValue, "proto", "b".repeat(64), "c".repeat(64), "d".repeat(64), null),
        status = ProjectStatus.DRAFT,
        review = ProjectReview("none", null, null, null),
        historyCount = 0
    )

    private fun pack(treeValue: String = tree): PackEntry =
        PackEntry("pack", "1.0.0", "Pack", "", 1, treeValue, File(tmp.root, "pack"))

    @Test
    fun locksAndVerifiesInstalledPack() {
        val store = PackLockStore(tmp.root)
        assertEquals(PackLockStore.Status.MISSING, store.verify(project(), listOf(pack())).status)
        store.lock(project())
        assertEquals(PackLockStore.Status.OK, store.verify(project(), listOf(pack())).status)
        assertEquals(PackLockStore.Status.TREE_MISMATCH, store.verify(project(), listOf(pack("b".repeat(64)))).status)
        assertEquals(PackLockStore.Status.PACK_MISSING, store.verify(project(), emptyList()).status)
        store.unlock("p1")
        assertNull(store.load("p1"))
    }

    @Test
    fun detectsProjectReferenceChange() {
        val store = PackLockStore(tmp.root)
        store.lock(project())
        assertEquals(PackLockStore.Status.PROJECT_CHANGED, store.verify(project("b".repeat(64)), listOf(pack())).status)
    }
}
