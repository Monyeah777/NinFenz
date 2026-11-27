package dev.ninfenz.mobile.data

import java.io.File

/**
 * 项目/作者/草稿路径的单一构造点。
 *
 * 审计规则 B-001：UI 层不得直接构造 java.io.File 做持久化路径。UI 一律调用本对象，
 * 路径口径变化时只改一处。
 */
object ProjectPaths {
    fun projectsDir(filesDir: File): File = File(filesDir, "projects")

    fun projectDir(filesDir: File, projectId: String): File = File(projectsDir(filesDir), projectId)

    fun authoringDir(filesDir: File, projectId: String): File = File(projectDir(filesDir, projectId), "authoring")

    fun specOverride(filesDir: File, projectId: String): File = File(authoringDir(filesDir, projectId), "spec-override.json")

    fun templateMd(filesDir: File, projectId: String): File = File(authoringDir(filesDir, projectId), "template.md")

    fun zeroSlice(filesDir: File, projectId: String): File = File(authoringDir(filesDir, projectId), "zero-slice.json")

    fun projectJson(filesDir: File, projectId: String): File = File(projectsDir(filesDir), projectId + ".nfproject.json")

    fun draftsDir(filesDir: File): File = File(filesDir, "drafts")

    fun deliveryDraft(filesDir: File, projectId: String): File = File(draftsDir(filesDir), "delivery-" + projectId + ".json")

    fun packSpec(packDir: File): File = File(packDir, "spec/main.nfspec.json")

    fun templateExportCache(cacheDir: File): File = File(cacheDir, "template-export")
}
