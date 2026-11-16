package dev.ninfenz.mobile.data

import java.io.File

/** HTML 基础结构自检：doctype/html/head/body/title/charset。 */
object HtmlValidator {
    data class Result(val ok: Boolean, val message: String, val issues: List<String>)

    fun inspect(file: File): Result {
        if (!file.isFile) return Result(false, "HTML 不存在", listOf("missing file"))
        val text = try { file.readText(Charsets.UTF_8) } catch (t: Throwable) {
            return Result(false, "HTML 读取失败", listOf(t.javaClass.simpleName))
        }
        val issues = mutableListOf<String>()
        if (!text.trimStart().startsWith("<!DOCTYPE html>", ignoreCase = true)) issues.add("缺少 doctype")
        if (!text.contains("<html", ignoreCase = true)) issues.add("缺少 html")
        if (!text.contains("<head", ignoreCase = true)) issues.add("缺少 head")
        if (!text.contains("<body", ignoreCase = true)) issues.add("缺少 body")
        if (!Regex("<title>[^<]*</title>", RegexOption.IGNORE_CASE).containsMatchIn(text)) issues.add("缺少 title")
        if (!text.contains("charset", ignoreCase = true)) issues.add("缺少 charset")
        return Result(issues.isEmpty(), if (issues.isEmpty()) "HTML 结构校验通过" else issues.first(), issues)
    }
}
