package dev.ninfenz.mobile.data

import dev.ninfenz.mobile.model.Project
import dev.ninfenz.mobile.model.ProjectModel
import java.io.File

data class ProjectEntry(val project: Project, val file: File)

data class LibrarySnapshot(val projects: List<ProjectEntry>, val errors: List<String>)

/**
 * 本地库（app 私有目录）：projects/ 只读扫描；drafts/ 允许写入。
 * 解析失败逐条登记，不跳过不伪造。
 */
class LibraryStore(private val filesDir: File) {

    fun projectsDir(): File = File(filesDir, "projects").apply { mkdirs() }

    fun draftsDir(): File = File(filesDir, "drafts").apply { mkdirs() }

    fun loadProjects(): LibrarySnapshot {
        val dir = projectsDir()
        val files = dir.listFiles { f -> f.isFile && f.name.endsWith(".nfproject.json") } ?: arrayOf()
        val entries = mutableListOf<ProjectEntry>()
        val errors = mutableListOf<String>()
        for (f in files.sortedBy { it.name }) {
            try {
                val project = ProjectModel.parse(f.readText(Charsets.UTF_8))
                entries.add(ProjectEntry(project, f))
            } catch (e: Exception) {
                errors.add(f.name + "：" + (e.message ?: e.javaClass.simpleName))
            }
        }
        return LibrarySnapshot(entries, errors)
    }

    fun uniqueDraftBase(baseName: String): String {
        val safe = baseName.replace(Regex("[^A-Za-z0-9._-]"), "_").ifBlank { "draft" }
        var candidate = safe
        var index = 2
        while (
            File(draftsDir(), candidate + ".json").exists() ||
            File(draftsDir(), candidate + ".mapping.json").exists()
        ) {
            candidate = "$safe-$index"
            index++
        }
        return candidate
    }

    fun saveDraft(baseName: String, json: String): File {
        val safe = baseName.replace(Regex("[^A-Za-z0-9._-]"), "_").ifBlank { "draft" }
        val file = File(draftsDir(), safe + ".json")
        AtomicFiles.writeText(file, json)
        return file
    }
}
