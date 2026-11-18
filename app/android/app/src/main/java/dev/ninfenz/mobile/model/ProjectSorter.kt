package dev.ninfenz.mobile.model

import dev.ninfenz.mobile.data.ProjectEntry

enum class ProjectSort { RECENT, TITLE, STATUS }

/** 项目列表排序：最近修改 / 标题 / 状态。 */
object ProjectSorter {
    fun sort(
        entries: List<ProjectEntry>,
        mode: ProjectSort,
        priorityIds: List<String> = emptyList()
    ): List<ProjectEntry> = when (mode) {
        ProjectSort.RECENT -> {
            val priority = priorityIds.withIndex().associate { (index, id) -> id to index }
            entries.sortedWith(
                compareBy<ProjectEntry> { priority[it.project.id] ?: Int.MAX_VALUE }
                    .thenByDescending { it.file.lastModified() }
            )
        }
        ProjectSort.TITLE -> entries.sortedBy { it.project.title.lowercase() }
        ProjectSort.STATUS -> entries.sortedBy { it.project.status.ordinal }
    }
}
