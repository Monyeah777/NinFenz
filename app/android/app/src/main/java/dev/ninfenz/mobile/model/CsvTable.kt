package dev.ninfenz.mobile.model

/** 把 CSV 转为 Markdown 表格；只做结构转换，不推断字段语义。 */
object CsvTable {
    fun toMarkdown(csv: String): String {
        val cleaned = if (csv.lineSequence().firstOrNull()?.startsWith("sep=", ignoreCase = true) == true) {
            csv.substringAfter('\n', "")
        } else {
            csv
        }
        val rows = parse(cleaned, detectDelimiter(cleaned))
        if (rows.isEmpty()) return ""
        val width = rows.maxOf { it.size }
        val normalized = rows.map { row -> row + List(width - row.size) { "" } }
        val header = normalized.first()
        val body = normalized.drop(1)
        return buildString {
            appendLine("| " + header.joinToString(" | ") { escape(it) } + " |")
            appendLine("| " + List(width) { "---" }.joinToString(" | ") + " |")
            body.forEach { row ->
                appendLine("| " + row.joinToString(" | ") { escape(it) } + " |")
            }
        }.trimEnd()
    }

    private fun escape(value: String): String =
        value.replace("|", "\\|").replace("\n", "<br>").trim()

    private fun detectDelimiter(csv: String): Char {
        val line = csv.lineSequence().firstOrNull { it.isNotBlank() }.orEmpty()
        var quoted = false
        val counts = mutableMapOf(',' to 0, ';' to 0, '\t' to 0)
        line.forEach { c ->
            if (c == '"') quoted = !quoted
            if (!quoted && counts.containsKey(c)) counts[c] = (counts[c] ?: 0) + 1
        }
        return counts.maxByOrNull { it.value }?.takeIf { it.value > 0 }?.key ?: ','
    }

    private fun parse(csv: String, delimiter: Char): List<List<String>> {
        val rows = mutableListOf<List<String>>()
        val row = mutableListOf<String>()
        val field = StringBuilder()
        var quoted = false
        var i = 0
        val text = csv.replace("\r\n", "\n").replace('\r', '\n')
        while (i < text.length) {
            val c = text[i]
            when {
                c == '"' && quoted && i + 1 < text.length && text[i + 1] == '"' -> {
                    field.append('"'); i++
                }
                c == '"' -> quoted = !quoted
                c == delimiter && !quoted -> {
                    row.add(field.toString()); field.clear()
                }
                c == '\n' && !quoted -> {
                    row.add(field.toString()); field.clear()
                    if (row.any { it.isNotBlank() }) rows.add(row.toList())
                    row.clear()
                }
                else -> field.append(c)
            }
            i++
        }
        row.add(field.toString())
        if (row.any { it.isNotBlank() }) rows.add(row)
        return rows
    }
}
