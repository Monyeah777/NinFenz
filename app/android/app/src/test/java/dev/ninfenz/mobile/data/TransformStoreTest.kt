package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.model.FlashFillModel
import java.nio.file.Files
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test

class TransformStoreTest {
    @Test
    fun savesAndLoads() {
        val dir = Files.createTempDirectory("transform").toFile()
        val store = TransformStore(dir)
        assertNull(store.load("p1"))
        val t = FlashFillModel.Transform("prefix", "【")
        store.save("p1", t)
        assertEquals(t, store.load("p1"))
    }
}
