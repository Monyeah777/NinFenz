package dev.ninfenz.mobile.data

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import org.junit.Assert.assertTrue
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [34])
class SearchIndexStoreTest {
    @Test
    fun rebuildsAndSearchesWithFtsOrFallback() {
        val context = ApplicationProvider.getApplicationContext<Context>()
        val store = SearchIndexStore(context, "search-test-" + System.nanoTime() + ".db")
        store.rebuild(
            listOf(
                SearchHit(SearchKind.PROJECT, "Alpha", "demo", projectId = "p1", body = "needle target"),
                SearchHit(SearchKind.SECTION, "Beta", "demo", projectId = "p1", body = "other")
            )
        )
        val results = store.search("needle")
        assertTrue(results.any { it.title == "Alpha" })
        store.close()
    }
}
