package dev.ninfenz.mobile.data

import java.io.File
import java.security.MessageDigest
import java.util.zip.ZipFile

/** 把旧 preservation 包升级为当前 OAIS/grant 格式，并接上 predecessor。 */
object PreservationUpgrader {
    data class Result(val file: File, val predecessor: String)

    private fun sha(file: File): String =
        MessageDigest.getInstance("SHA-256").digest(file.readBytes())
            .joinToString("") { "%02x".format(it.toInt() and 0xff) }

    fun upgrade(old: File, outDir: File): Result {
        val markdown = PreservationVerifier.extractMarkdown(old)
            ?: throw IllegalArgumentException("旧包缺 document.md")
        val title = PreservationVerifier.title(old) ?: old.nameWithoutExtension
        val contract = PreservationVerifier.extractEntry(old, "contract.json")
        val predecessor = sha(old)
        val created = PreservationExporter.export(
            markdown,
            title,
            "upgrade-" + predecessor.take(12),
            outDir,
            contract,
            null,
            predecessor
        )
        return Result(created.file, predecessor)
    }
}
