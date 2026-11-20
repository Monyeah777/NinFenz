package dev.ninfenz.mobile.model

import org.junit.Assert.assertTrue
import org.junit.Test

class CsvTableTest {
    @Test
    fun detectsSemicolonAndTab() {
        val semi = CsvTable.toMarkdown("a;b\n1;2")
        assertTrue(semi.startsWith("| a | b |"))
        assertTrue(semi.contains("| 1 | 2 |"))
        val tab = CsvTable.toMarkdown("a\tb\n1\t2")
        assertTrue(tab.startsWith("| a | b |"))
        assertTrue(tab.contains("| 1 | 2 |"))
    }

    @Test
    fun convertsQuotedCsv() {
        val table = CsvTable.toMarkdown("name,note\nA,\"x,y\"\nB,z")
        assertTrue(table.startsWith("| name | note |"))
        assertTrue(table.contains("| A | x,y |"))
    }
}
