package dev.ninfenz.mobile.data

import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/** 输出命名：只做本地字符串替换与清洗，不访问文件系统。 */
object OutputNaming {
    fun resolve(template: String?, projectTitle: String, format: String, date: Date = Date()): String {
        val ext = format.lowercase(Locale.ROOT)
        val raw = template.orEmpty().trim().ifBlank { "result" }
            .replace("{project}", projectTitle)
            .replace("{date}", SimpleDateFormat("yyyyMMdd", Locale.ROOT).format(date))
            .replace("{format}", ext)
        val safe = raw.replace(Regex("[\\\\/:*?\"<>|\\p{Cntrl}]"), "_").trim().trimEnd('.')
        val base = safe.ifBlank { "result" }
        return if (base.lowercase(Locale.ROOT).endsWith("." + ext)) base else base + "." + ext
    }
}
