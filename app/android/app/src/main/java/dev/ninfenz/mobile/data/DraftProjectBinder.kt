package dev.ninfenz.mobile.data

import java.io.File

/** 把导入草稿作为项目来源副本写入 projects/<id>/authoring/，不伪造 core 引用。 */
object DraftProjectBinder {
    fun bindSpec(filesDir: File, projectId: String, specJson: String): File {
        require(projectId.isNotBlank()) { "项目 ID 为空" }
        val projectFile = File(File(filesDir, "projects"), projectId + ".nfproject.json")
        require(projectFile.isFile) { "项目文件不存在：" + projectId }
        val dir = File(File(File(filesDir, "projects"), projectId), "authoring").apply { mkdirs() }
        val target = File(dir, "spec-override.json")
        target.writeText(specJson, Charsets.UTF_8)
        return target
    }

    fun bind(filesDir: File, projectId: String, draft: File): File {
        require(projectId.isNotBlank()) { "项目 ID 为空" }
        require(draft.isFile) { "草稿不存在" }
        val projectFile = File(File(filesDir, "projects"), projectId + ".nfproject.json")
        require(projectFile.isFile) { "项目文件不存在：" + projectId }
        val dir = File(File(File(filesDir, "projects"), projectId), "authoring").apply { mkdirs() }
        val safe = draft.name.replace(Regex("[^A-Za-z0-9._-]"), "_")
        val target = File(dir, "import-" + safe)
        target.writeBytes(draft.readBytes())
        return target
    }
}
