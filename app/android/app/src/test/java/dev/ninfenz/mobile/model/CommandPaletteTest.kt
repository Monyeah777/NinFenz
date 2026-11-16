package dev.ninfenz.mobile.model

import org.junit.Assert.assertEquals
import org.junit.Test

class CommandPaletteTest {
    private val items = listOf(
        CommandPalette.Item("import", "导入内容"),
        CommandPalette.Item("search", "搜索"),
        CommandPalette.Item("settings", "设置")
    )

    @Test
    fun emptyQueryReturnsAll() {
        assertEquals(3, CommandPalette.filter(items, "").size)
        assertEquals(3, CommandPalette.filter(items, "  ").size)
    }

    @Test
    fun filtersByTitleOrIdCaseInsensitive() {
        assertEquals(listOf("import"), CommandPalette.filter(items, "导入").map { it.id })
        assertEquals(listOf("search"), CommandPalette.filter(items, "SEARCH").map { it.id })
        assertEquals(0, CommandPalette.filter(items, "不存在").size)
    }
}
