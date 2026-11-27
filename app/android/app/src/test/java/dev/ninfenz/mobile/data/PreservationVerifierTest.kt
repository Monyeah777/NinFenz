package dev.ninfenz.mobile.data

import java.io.File
import java.nio.file.Files
import java.util.zip.ZipEntry
import java.util.zip.ZipFile
import java.util.zip.ZipOutputStream
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

class PreservationVerifierTest {
    @Test
    fun verifiesExportedBundle() {
        val dir = Files.createTempDirectory("verify").toFile()
        val created = PreservationExporter.export("# 标题\n\n正文", "标题", "p1", dir)
        val result = PreservationVerifier.verify(created.file)
        assertTrue(result.errors.toString(), result.ok)
        assertTrue(result.title == "标题")
        assertTrue(result.grant?.allows(CapabilityGrant.READ, 0) == true)
        assertTrue(PreservationVerifier.extractMarkdown(created.file)!!.contains("正文"))
    }

    @Test
    fun verifiesChain() {
        val dir = Files.createTempDirectory("verify-chain").toFile()
        val first = PreservationExporter.export("# 一\n\n甲", "一", "p1", dir)
        val sha = java.security.MessageDigest.getInstance("SHA-256").digest(first.file.readBytes())
            .joinToString("") { "%02x".format(it.toInt() and 0xff) }
        val second = PreservationExporter.export("# 二\n\n乙", "二", "p1", dir, PreservationOptions(null, null, sha))
        assertTrue(PreservationVerifier.chain(first.file, second.file).errors.toString(), PreservationVerifier.chain(first.file, second.file).ok)
        val bad = PreservationExporter.export("# 三\n\n丙", "三", "p1", dir, PreservationOptions(null, null, "0".repeat(64)))
        assertFalse(PreservationVerifier.chain(first.file, bad.file).ok)
    }

    @Test
    fun rejectsTooManyEntries() {
        val dir = Files.createTempDirectory("verify-many").toFile()
        val bad = File(dir, "many.zip")
        ZipOutputStream(bad.outputStream()).use { out ->
            repeat(40) { i ->
                out.putNextEntry(ZipEntry("f" + i).apply { time = 0L })
                out.write("x".toByteArray())
                out.closeEntry()
            }
        }
        assertFalse(PreservationVerifier.verify(bad).ok)
    }

    @Test
    fun rejectsMissingOais() {
        val dir = Files.createTempDirectory("verify-no-oais").toFile()
        val created = PreservationExporter.export("# 标题\n\n正文", "标题", "p1", dir)
        val bad = File(dir, "no-oais.preserve.zip")
        ZipFile(created.file).use { zip ->
            ZipOutputStream(bad.outputStream()).use { out ->
                zip.entries().asSequence().filter { it.name != "oais.json" }.forEach { entry ->
                    out.putNextEntry(ZipEntry(entry.name).apply { time = 0L })
                    out.write(zip.getInputStream(entry).readBytes())
                    out.closeEntry()
                }
            }
        }
        assertFalse(PreservationVerifier.verify(bad).ok)
    }

    @Test
    fun rejectsTamperedDocument() {
        val dir = Files.createTempDirectory("verify-bad").toFile()
        val created = PreservationExporter.export("# 标题\n\n正文", "标题", "p1", dir)
        val bad = File(dir, "bad.preserve.zip")
        ZipFile(created.file).use { zip ->
            ZipOutputStream(bad.outputStream()).use { out ->
                zip.entries().asSequence().forEach { entry ->
                    out.putNextEntry(ZipEntry(entry.name).apply { time = 0L })
                    val bytes = zip.getInputStream(entry).readBytes()
                    out.write(if (entry.name == "document.md") "tamper".toByteArray() else bytes)
                    out.closeEntry()
                }
            }
        }
        assertFalse(PreservationVerifier.verify(bad).ok)
    }
}
