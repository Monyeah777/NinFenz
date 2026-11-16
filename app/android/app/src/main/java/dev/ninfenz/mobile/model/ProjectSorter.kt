package dev.ninfenz.mobile.model

import dev.ninfenz.mobile.data.ProjectEntry

enum class ProjectSort { RECENT, TITLE, STATUS }

/** 项目列表排序：最近修改 / 标题 / 状态。 */
object ProjectSorter {
    fun sort(entries: List<ProjectEntry>, mode: ProjectSort): List<ProjectEntry> = when (mode) {
        ProjectSort.RECENT -> entries.sortedByDescending { it.file.lastModified() }
        ProjectSort.TITLE -> entries.sortedBy { it.project.title.lowercase() }
        ProjectSort.STATUS -> entries.sortedBy { it.project.status.ordinal }
    }
}
