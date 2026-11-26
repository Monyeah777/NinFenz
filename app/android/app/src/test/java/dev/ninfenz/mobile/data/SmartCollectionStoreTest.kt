package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.model.Project
import dev.ninfenz.mobile.model.ProjectRefs
import dev.ninfenz.mobile.model.ProjectReview
import dev.ninfenz.mobile.model.ProjectStatus
import java.io.File
import java.nio.file.Files
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class SmartCollectionStoreTest {
    private fun project() = Project(
        id = "p1", title = "客户案例",
        refs = ProjectRefs("pack-a", "1.0.0", "tree", "proto", "digest", "graph", "spec", null),
        status = ProjectStatus.ASSEMBLED,
        review = ProjectReview("none", null, null, null),
        historyCount = 0
    )

    @Test
    fun matchesAllAndAnyRules() {
        val dir = Files.createTempDirectory("nf-smart").toFile()
        LibraryMetaStore(dir).apply { toggle("p1"); addTag("p1", "客户") }
        val meta = LibraryMetaStore(dir)
        val entry = ProjectEntry(project(), File(dir, "p1.json"))
        val store = SmartCollectionStore(dir)
        val all = SmartCollectionStore.Collection("c1", "客户已收藏", true, listOf(
            SmartCollectionStore.Rule("tag", "客户"),
            SmartCollectionStore.Rule("favorite", "true")
        ))
        assertTrue(store.matches(all, entry, meta))
        val any = SmartCollectionStore.Collection("c2", "任一", false, listOf(
            SmartCollectionStore.Rule("tag", "不存在"),
            SmartCollectionStore.Rule("status", "assembled")
        ))
        assertTrue(store.matches(any, entry, meta))
        assertFalse(store.matches(all.copy(rules = listOf(SmartCollectionStore.Rule("status", "draft"))), entry, meta))
    }
}
