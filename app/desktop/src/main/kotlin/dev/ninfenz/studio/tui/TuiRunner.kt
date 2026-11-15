package dev.ninfenz.studio.tui

import java.io.File
import java.util.concurrent.TimeUnit

data class TuiResult(val commandLine: String, val exit: Int, val output: String, val timedOut: Boolean)

/**
 * TUI 集成（不重写 TUI）：ProcessBuilder 启动 python tui/nf.py 或 nf-app CLI，回放 stdout/stderr。
 * 仓库根从 cwd 向上找 tui/nf.py；找不到返回 null，UI 明确报错。
 */
object TuiRunner {

    fun findRepoRoot(start: File = File(System.getProperty("user.dir"))): File? {
        var dir: File? = start.absoluteFile
        var depth = 0
        while (dir != null && depth < 12) {
            if (File(dir, "tui/nf.py").isFile) return dir
            if (File(dir, "app/core/Cargo.toml").isFile) return dir
            dir = dir.parentFile
            depth++
        }
        return null
    }

    fun pythonCommand(): List<String> {
        for (candidate in listOf("python", "python3", "py")) {
            val ok = try {
                val process = ProcessBuilder(candidate, "--version").redirectErrorStream(true).start()
                process.waitFor(10, TimeUnit.SECONDS)
                true
            } catch (t: Throwable) {
                false
            }
            if (ok) return listOf(candidate)
        }
        return emptyList()
    }

    fun run(command: List<String>, workDir: File, timeoutSeconds: Long = 180): TuiResult {
        if (command.isEmpty()) return TuiResult("", -1, "空命令", false)
        val builder = ProcessBuilder(command)
            .directory(workDir)
            .redirectErrorStream(true)
        return try {
            val process = builder.start()
            val output = process.inputStream.bufferedReader(Charsets.UTF_8).use { it.readText() }
            val finished = process.waitFor(timeoutSeconds, TimeUnit.SECONDS)
            if (!finished) {
                process.destroyForcibly()
                TuiResult(command.joinToString(" "), -1, output + "\n[超时 " + timeoutSeconds + "s，已终止]", true)
            } else {
                TuiResult(command.joinToString(" "), process.exitValue(), output, false)
            }
        } catch (t: Throwable) {
            TuiResult(command.joinToString(" "), -1, "启动失败：" + (t.message ?: t.javaClass.simpleName), false)
        }
    }
}
