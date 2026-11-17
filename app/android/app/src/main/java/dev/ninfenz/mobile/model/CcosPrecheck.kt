package dev.ninfenz.mobile.model

/** 结果导入前预检：不写盘、不评审，只给人工看的结构与回钉问题。 */
object CcosPrecheck {
    data class Finding(val field: String, val message: String)

    private fun isHex64(s: String): Boolean =
        s.length == 64 && s.all { it in '0'..'9' || it in 'a'..'f' || it in 'A'..'F' }

    private fun safeRelPath(path: String): Boolean =
        path.isNotBlank() && !path.startsWith("/") && !path.startsWith("\\\\") &&
            path.split('/').none { it == ".." || it.isEmpty() }

    fun check(result: CcosResult, task: CcosTask?): List<Finding> {
        val findings = mutableListOf<Finding>()
        if (task != null && result.taskId != task.id) {
            findings.add(Finding("task_id", "结果 task_id 与任务不一致：${result.taskId} vs ${task.id}"))
        }
        if (result.taskDigest.isBlank()) {
            findings.add(Finding("task_digest", "结果缺 task_digest，无法回钉任务"))
        }
        result.artifacts.forEachIndexed { i, artifact ->
            if (artifact.name.isBlank()) findings.add(Finding("artifacts[$i].name", "artifact 缺 name"))
            if (!safeRelPath(artifact.path)) findings.add(Finding("artifacts[$i].path", "artifact 路径不安全：${artifact.path}"))
            if (!isHex64(artifact.sha256)) findings.add(Finding("artifacts[$i].sha256", "artifact sha256 非法"))
            if (artifact.bytes < 0) findings.add(Finding("artifacts[$i].bytes", "artifact bytes 为负"))
        }
        result.evidence.forEachIndexed { i, evidence ->
            if (evidence.kind.isBlank()) findings.add(Finding("evidence[$i].kind", "evidence 缺 kind"))
            if (!isHex64(evidence.digest)) findings.add(Finding("evidence[$i].digest", "evidence digest 非法"))
        }
        return findings
    }
}
