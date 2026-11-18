package dev.ninfenz.mobile.model

import org.junit.Assert.assertTrue
import org.junit.Test

class CsvTableTest {
    @Test
    fun convertsQuotedCsv() {
        val table = CsvTable.toMarkdown("name,note\nA,\"x,y\"\nB,z")
        assertTrue(table.startsWith("| name | note |"))
        assertTrue(table.contains("| A | x,y |"))
    }
}
